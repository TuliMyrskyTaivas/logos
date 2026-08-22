// Package api implements the Gûldvegt quotes HTTP service.
package api

import (
	"net/http"
	"time"

	"github.com/labstack/echo/v5"
	openapi_types "github.com/oapi-codegen/runtime/types"

	"github.com/TuliMyrskyTaivas/guldvegt/internal/generated/openapi"
)

// Service implements the generated openapi.ServerInterface.
type Service struct{}

// NewService returns a new Service.
func NewService() *Service {
	return &Service{}
}

// Ensure Service satisfies the generated server interface at compile time.
var _ openapi.ServerInterface = (*Service)(nil)

// GetBullionQuotes returns a list of precious metals bullion quotes.
func (s *Service) GetBullionQuotes(ctx *echo.Context) error {
	quotes := []openapi.BullionQuote{
		{
			Date:      openapi_types.Date{Time: time.Date(2026, time.August, 22, 0, 0, 0, 0, time.UTC)},
			Vendor:    "Sberbank",
			Metal:     openapi.Gold,
			Weight:    100,
			BuyPrice:  650000,
			SellPrice: 660000,
			Currency:  openapi.BullionQuoteCurrencyRUB,
		},
		{
			Date:      openapi_types.Date{Time: time.Date(2026, time.August, 22, 0, 0, 0, 0, time.UTC)},
			Vendor:    "Sberbank",
			Metal:     openapi.Silver,
			Weight:    1000,
			BuyPrice:  80000,
			SellPrice: 83000,
			Currency:  openapi.BullionQuoteCurrencyRUB,
		},
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
