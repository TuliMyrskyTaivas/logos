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
	coins    client.CoinsClientInterface
	log      *slog.Logger
}

// NewService returns a new Service.
func NewService(log *slog.Logger) *Service {
	return &Service{
		bullions: client.NewSberBullionsClient(log),
		coins:    client.NewSberCoinsClient(log),
		log:      log,
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
	info, err := s.coins.GetCoinsInfo(ctx.Request().Context())
	if err != nil {
		return ctx.JSON(http.StatusInternalServerError, map[string]string{"error": err.Error()})
	}

	coins := make([]openapi.CoinQuote, 0, len(info.Coins))
	for _, c := range info.Coins {
		date, err := client.ParseCoinDate(c.Date)
		if err != nil {
			return ctx.JSON(http.StatusInternalServerError, map[string]string{"error": err.Error()})
		}
		coins = append(coins, openapi.CoinQuote{
			Name:      c.Name,
			Date:      openapi_types.Date{Time: date},
			Dealer:    "Sberbank",
			Weight:    c.Mass,
			BuyPrice:  c.BuyPrice,
			SellPrice: c.Price,
			Spread:    c.Spread,
			Currency:  openapi.CoinQuoteCurrencyRUB,
		})
	}

	return ctx.JSON(http.StatusOK, coins)
}
