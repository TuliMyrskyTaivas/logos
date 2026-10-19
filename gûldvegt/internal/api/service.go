// Package api implements the Gûldvegt quotes HTTP service.
package api

import (
	"log/slog"
	"net/http"
	"sort"

	"github.com/labstack/echo/v5"
	openapi_types "github.com/oapi-codegen/runtime/types"

	"github.com/TuliMyrskyTaivas/guldvegt/internal/client"
	"github.com/TuliMyrskyTaivas/guldvegt/internal/generated/openapi"
	"github.com/TuliMyrskyTaivas/guldvegt/internal/metrics"
)

// Service implements the generated openapi.ServerInterface.
type Service struct {
	bullions []client.ClientInterface
	coins    []client.CoinsClientInterface
	log      *slog.Logger
}

// NewService returns a new Service.
func NewService(log *slog.Logger) *Service {
	return &Service{
		bullions: []client.ClientInterface{
			client.NewSberBullionsClient(log),
			client.NewVTBBullionsClient(log),
		},
		coins: []client.CoinsClientInterface{
			client.NewSberCoinsClient(log),
			client.NewZolotoyZapasCoinsClient(log),
			client.NewZolotoMDCoinsClient(log),
			client.NewVTBCoinsClient(log),
		},
		log: log,
	}
}

// Ensure Service satisfies the generated server interface at compile time.
var _ openapi.ServerInterface = (*Service)(nil)

// GetBullionQuotes returns a list of precious metals bullion quotes.
func (s *Service) GetBullionQuotes(ctx *echo.Context) error {
	type result struct {
		info *client.QuotesInfo
		err  error
	}

	results := make(chan result, len(s.bullions))
	for _, bullionsClient := range s.bullions {
		go func(c client.ClientInterface) {
			info, err := c.GetQuotesInfo(ctx.Request().Context())
			results <- result{info: info, err: err}
		}(bullionsClient)
	}

	quotes := make([]openapi.BullionQuote, 0)
	for range s.bullions {
		res := <-results
		if res.err != nil {
			metrics.IncBullionsFailed()
			return ctx.JSON(http.StatusInternalServerError, map[string]string{"error": res.err.Error()})
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
func (s *Service) GetCoinQuotes(ctx *echo.Context) error {
	type result struct {
		coins []client.CoinInfo
		err   error
	}

	results := make(chan result, len(s.coins))
	for _, coinsClient := range s.coins {
		go func(c client.CoinsClientInterface) {
			info, err := c.GetCoinsInfo(ctx.Request().Context())
			if err != nil {
				results <- result{err: err}
				return
			}
			results <- result{coins: info.Coins}
		}(coinsClient)
	}

	var all []client.CoinInfo
	for range s.coins {
		res := <-results
		if res.err != nil {
			metrics.IncCoinsFailed()
			return ctx.JSON(http.StatusInternalServerError, map[string]string{"error": res.err.Error()})
		}
		all = append(all, res.coins...)
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
