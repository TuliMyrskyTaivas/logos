// Package api implements the Gûldvegt quotes HTTP service.
package api

import (
	"log/slog"
	"net/http"
	"sort"
	"time"

	"github.com/labstack/echo/v5"
	openapi_types "github.com/oapi-codegen/runtime/types"

	"github.com/TuliMyrskyTaivas/guldvegt/internal/client"
	"github.com/TuliMyrskyTaivas/guldvegt/internal/generated/openapi"
)

// Service implements the generated openapi.ServerInterface.
type Service struct {
	bullions client.ClientInterface
	log      *slog.Logger
}

// NewService returns a new Service.
func NewService(log *slog.Logger) *Service {
	return &Service{
		bullions: client.NewSberBullionsClient(log),
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
			Currency:  openapi.BullionQuoteCurrencyRUB,
		})
	}

	return ctx.JSON(http.StatusOK, quotes)
}

// GetCoinQuotes returns a list of investment coin quotes.
func (s *Service) GetCoinQuotes(ctx *echo.Context) error {
	coins := []openapi.CoinQuote{
		{
			Date:      openapi_types.Date{Time: time.Date(2026, time.August, 22, 0, 0, 0, 0, time.UTC)},
			Dealer:    "Sberbank",
			Weight:    7.78,
			BuyPrice:  50000,
			SellPrice: 52000,
			Currency:  openapi.CoinQuoteCurrencyRUB,
		},
		{
			Date:      openapi_types.Date{Time: time.Date(2026, time.August, 22, 0, 0, 0, 0, time.UTC)},
			Dealer:    "Sberbank",
			Weight:    31.1,
			BuyPrice:  190000,
			SellPrice: 195000,
			Currency:  openapi.CoinQuoteCurrencyRUB,
		},
	}
	return ctx.JSON(http.StatusOK, coins)
}
