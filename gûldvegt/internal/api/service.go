// Package api implements the Gûldvegt quotes HTTP service.
package api

import (
	"errors"
	"log/slog"
	"net/http"
	"sort"

	"github.com/labstack/echo/v5"
	openapi_types "github.com/oapi-codegen/runtime/types"

	"github.com/TuliMyrskyTaivas/guldvegt/internal/client"
	"github.com/TuliMyrskyTaivas/guldvegt/internal/generated/openapi"
	"github.com/TuliMyrskyTaivas/guldvegt/internal/metrics"
)

const (
	// endpointBullions is the endpoint label used for bullion quotes.
	endpointBullions = "bullions"
	// endpointCoins is the endpoint label used for coin quotes.
	endpointCoins = "coins"

	// Provider names used in logs and metrics.
	providerSberbank     = "sberbank"
	providerVTB          = "vtb"
	providerZolotoyZapas = "zolotoy_zapas"
	providerZolotoMD     = "zoloto_md"
)

var (
	// errNoBullionQuotes is returned when no provider delivered bullion quotes.
	errNoBullionQuotes = errors.New("no bullion quotes received from providers")
	// errNoCoinQuotes is returned when no provider delivered coin quotes.
	errNoCoinQuotes = errors.New("no coin quotes received from providers")
)

// Service implements the generated openapi.ServerInterface.
type Service struct {
	bullions []bullionProvider
	coins    []coinsProvider
	log      *slog.Logger
}

// bullionProvider couples a bullion quotes client with the name used in logs
// and metrics.
type bullionProvider struct {
	name   string
	client client.ClientInterface
}

// coinsProvider couples a coin quotes client with the name used in logs and
// metrics.
type coinsProvider struct {
	name   string
	client client.CoinsClientInterface
}

// NewService returns a new Service.
func NewService(log *slog.Logger) *Service {
	return &Service{
		bullions: []bullionProvider{
			{name: providerSberbank, client: client.NewSberBullionsClient(log)},
			{name: providerVTB, client: client.NewVTBBullionsClient(log)},
		},
		coins: []coinsProvider{
			{name: providerSberbank, client: client.NewSberCoinsClient(log)},
			{name: providerZolotoyZapas, client: client.NewZolotoyZapasCoinsClient(log)},
			{name: providerZolotoMD, client: client.NewZolotoMDCoinsClient(log)},
			{name: providerVTB, client: client.NewVTBCoinsClient(log)},
		},
		log: log,
	}
}

// Ensure Service satisfies the generated server interface at compile time.
var _ openapi.ServerInterface = (*Service)(nil)

// writeErrorResponse sends the failure reason to the client and returns it, so
// that the request logger records why the request was rejected.
func writeErrorResponse(ctx *echo.Context, status int, reason error) error {
	if err := ctx.JSON(status, map[string]string{"error": reason.Error()}); err != nil {
		return err
	}
	return reason
}

// logProviderError records a failed request to a single upstream provider. The
// failure is not fatal for the whole request as long as another provider
// returned quotes.
func (s *Service) logProviderError(endpoint, provider string, err error) {
	s.log.Error("provider request failed",
		slog.String("endpoint", endpoint),
		slog.String("provider", provider),
		slog.Any("error", err),
	)
}

// GetBullionQuotes returns a list of precious metals bullion quotes.
//
// Providers are queried concurrently. A failed provider is logged and counted
// in metrics but does not fail the whole request: the response is 200 OK with
// the quotes of the remaining providers. The request fails with
// 503 Service Unavailable only when no provider returned any quote.
func (s *Service) GetBullionQuotes(ctx *echo.Context) error {
	type result struct {
		provider bullionProvider
		info     *client.QuotesInfo
		err      error
	}

	results := make(chan result, len(s.bullions))
	for _, provider := range s.bullions {
		go func(p bullionProvider) {
			info, err := p.client.GetQuotesInfo(ctx.Request().Context())
			results <- result{provider: p, info: info, err: err}
		}(provider)
	}

	quotes := make([]openapi.BullionQuote, 0)
	var providerErr error
	for range s.bullions {
		res := <-results
		if res.err != nil {
			s.logProviderError(endpointBullions, res.provider.name, res.err)
			metrics.IncBullionsProviderError(res.provider.name)
			if providerErr == nil {
				providerErr = res.err
			}
			continue
		}
		if res.info == nil {
			continue
		}
		for weight, q := range res.info.Quotes {
			quotes = append(quotes, openapi.BullionQuote{
				Date:      openapi_types.Date{Time: res.info.ValidAt},
				Vendor:    res.info.Vendor,
				Metal:     openapi.Gold,
				Weight:    weight,
				BuyPrice:  q.BuyPrice,
				SellPrice: q.SellPrice,
				Spread:    q.Spread,
				Currency:  openapi.BullionQuoteCurrencyRUB,
			})
		}
	}

	if len(quotes) == 0 {
		metrics.IncBullionsFailed()
		if providerErr == nil {
			providerErr = errNoBullionQuotes
		}
		return writeErrorResponse(ctx, http.StatusServiceUnavailable, providerErr)
	}

	sort.SliceStable(quotes, func(i, j int) bool {
		if quotes[i].Vendor != quotes[j].Vendor {
			return quotes[i].Vendor < quotes[j].Vendor
		}
		return quotes[i].Weight < quotes[j].Weight
	})

	metrics.IncBullionsSuccess()
	return ctx.JSON(http.StatusOK, quotes)
}

// GetCoinQuotes returns a list of investment coin quotes.
//
// Providers are queried concurrently. A failed provider is logged and counted
// in metrics but does not fail the whole request: the response is 200 OK with
// the quotes of the remaining providers. The request fails with
// 503 Service Unavailable only when no provider returned any quote.
func (s *Service) GetCoinQuotes(ctx *echo.Context) error {
	type result struct {
		provider coinsProvider
		coins    []client.CoinInfo
		err      error
	}

	results := make(chan result, len(s.coins))
	for _, provider := range s.coins {
		go func(p coinsProvider) {
			info, err := p.client.GetCoinsInfo(ctx.Request().Context())
			if err != nil {
				results <- result{provider: p, err: err}
				return
			}
			results <- result{provider: p, coins: info.Coins}
		}(provider)
	}

	var all []client.CoinInfo
	var providerErr error
	for range s.coins {
		res := <-results
		if res.err != nil {
			s.logProviderError(endpointCoins, res.provider.name, res.err)
			metrics.IncCoinsProviderError(res.provider.name)
			if providerErr == nil {
				providerErr = res.err
			}
			continue
		}
		all = append(all, res.coins...)
	}

	if len(all) == 0 {
		metrics.IncCoinsFailed()
		if providerErr == nil {
			providerErr = errNoCoinQuotes
		}
		return writeErrorResponse(ctx, http.StatusServiceUnavailable, providerErr)
	}

	sort.SliceStable(all, func(i, j int) bool {
		if all[i].Dealer != all[j].Dealer {
			return all[i].Dealer < all[j].Dealer
		}
		if all[i].Name != all[j].Name {
			return all[i].Name < all[j].Name
		}
		return all[i].Mass < all[j].Mass
	})

	coins := make([]openapi.CoinQuote, 0, len(all))
	for _, c := range all {
		coins = append(coins, openapi.CoinQuote{
			Name:      c.Name,
			Date:      openapi_types.Date{Time: c.Date},
			Dealer:    c.Dealer,
			Weight:    c.Mass,
			BuyPrice:  c.BuyPrice,
			SellPrice: c.Price,
			Spread:    c.Spread,
			Currency:  openapi.CoinQuoteCurrencyRUB,
		})
	}

	metrics.IncCoinsSuccess()
	return ctx.JSON(http.StatusOK, coins)
}
