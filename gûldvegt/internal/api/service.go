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
)

// Service implements the generated openapi.ServerInterface.
type Service struct {
	bullions client.ClientInterface
	coins    []client.CoinsClientInterface
	log      *slog.Logger
}

// NewService returns a new Service.
func NewService(log *slog.Logger) *Service {
	return &Service{
		bullions: client.NewSberBullionsClient(log),
		coins: []client.CoinsClientInterface{
			client.NewSberCoinsClient(log),
			client.NewZolotoyZapasCoinsClient(log),
		},
		log: log,
	}
}

// Ensure Service satisfies the generated server interface at compile time.
var _ openapi.ServerInterface = (*Service)(nil)

// GetBullionQuotes returns a list of precious metals bullion quotes.
func (s *Service) GetBullionQuotes(ctx *echo.Context) error {
	info, err := s.bullions.GetQuotesInfo(ctx.Request().Context())
	if err != nil {
		return ctx.JSON(http.StatusInternalServerError, map[string]string{"error": err.Error()})
	}

	weights := make([]float32, 0, len(info.Quotes))
	for weight := range info.Quotes {
		weights = append(weights, weight)
	}
	sort.Slice(weights, func(i, j int) bool { return weights[i] < weights[j] })

	quotes := make([]openapi.BullionQuote, 0, len(weights))
	for _, weight := range weights {
		q := info.Quotes[weight]
		quotes = append(quotes, openapi.BullionQuote{
			Date:      openapi_types.Date{Time: info.ValidAt},
			Vendor:    "Sberbank",
			Metal:     openapi.Gold,
			Weight:    weight,
			BuyPrice:  q.BuyPrice,
			SellPrice: q.SellPrice,
			Spread:    q.Spread,
			Currency:  openapi.BullionQuoteCurrencyRUB,
		})
	}

	return ctx.JSON(http.StatusOK, quotes)
}

// GetCoinQuotes returns a list of investment coin quotes.
func (s *Service) GetCoinQuotes(ctx *echo.Context) error {
	var all []client.CoinInfo
	for _, coinsClient := range s.coins {
		info, err := coinsClient.GetCoinsInfo(ctx.Request().Context())
		if err != nil {
			return ctx.JSON(http.StatusInternalServerError, map[string]string{"error": err.Error()})
		}
		all = append(all, info.Coins...)
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

	return ctx.JSON(http.StatusOK, coins)
}
