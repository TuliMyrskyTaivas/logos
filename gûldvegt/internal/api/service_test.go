package api

import (
	"context"
	"encoding/json"
	"errors"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/labstack/echo/v5"

	"github.com/TuliMyrskyTaivas/guldvegt/internal/client"
	"github.com/TuliMyrskyTaivas/guldvegt/internal/generated/openapi"
)

// stubBullionsClient is a client.ClientInterface stub.
type stubBullionsClient struct {
	info *client.QuotesInfo
	err  error
}

// GetQuotesInfo returns the configured result.
func (c stubBullionsClient) GetQuotesInfo(context.Context) (*client.QuotesInfo, error) {
	return c.info, c.err
}

// stubCoinsClient is a client.CoinsClientInterface stub.
type stubCoinsClient struct {
	info *client.CoinsInfo
	err  error
}

// GetCoinsInfo returns the configured result.
func (c stubCoinsClient) GetCoinsInfo(context.Context) (*client.CoinsInfo, error) {
	return c.info, c.err
}

// newTestService returns a Service with the given providers and a silent logger.
func newTestService(bullions []bullionProvider, coins []coinsProvider) *Service {
	return &Service{
		bullions: bullions,
		coins:    coins,
		log:      slog.New(slog.DiscardHandler),
	}
}

// newTestContext returns an Echo context writing to a response recorder.
func newTestContext(t *testing.T) (*echo.Context, *httptest.ResponseRecorder) {
	t.Helper()

	req := httptest.NewRequest(http.MethodGet, "/", nil)
	rec := httptest.NewRecorder()
	return echo.NewContext(req, rec, echo.New()), rec
}

// TestGetBullionQuotesPartialFailure checks that a failing provider does not
// fail the whole request when another provider returned quotes.
func TestGetBullionQuotesPartialFailure(t *testing.T) {
	validAt := time.Date(2026, 10, 20, 0, 0, 0, 0, time.UTC)
	svc := newTestService([]bullionProvider{
		{name: providerVTB, client: stubBullionsClient{err: errors.New("vtb unavailable")}},
		{name: providerSberbank, client: stubBullionsClient{info: &client.QuotesInfo{
			ValidAt: validAt,
			Vendor:  "Sberbank",
			Quotes:  client.Quotes{1: client.Quote{BuyPrice: 100, SellPrice: 110, Spread: 9.09}},
		}}},
	}, nil)

	ctx, rec := newTestContext(t)
	if err := svc.GetBullionQuotes(ctx); err != nil {
		t.Fatalf("GetBullionQuotes() error = %v, want nil", err)
	}
	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d, want %d", rec.Code, http.StatusOK)
	}

	var quotes []openapi.BullionQuote
	if err := json.Unmarshal(rec.Body.Bytes(), &quotes); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if len(quotes) != 1 {
		t.Fatalf("len(quotes) = %d, want 1", len(quotes))
	}
	if quotes[0].Vendor != "Sberbank" {
		t.Errorf("vendor = %q, want %q", quotes[0].Vendor, "Sberbank")
	}
}

// TestGetBullionQuotesAllProvidersFailed checks the all-failed response.
func TestGetBullionQuotesAllProvidersFailed(t *testing.T) {
	svc := newTestService([]bullionProvider{
		{name: providerSberbank, client: stubBullionsClient{err: errors.New("sberbank unavailable")}},
		{name: providerVTB, client: stubBullionsClient{err: errors.New("vtb unavailable")}},
	}, nil)

	ctx, rec := newTestContext(t)
	if err := svc.GetBullionQuotes(ctx); err == nil {
		t.Fatal("GetBullionQuotes() error = nil, want failure reason")
	}
	if rec.Code != http.StatusServiceUnavailable {
		t.Fatalf("status = %d, want %d", rec.Code, http.StatusServiceUnavailable)
	}
}

// TestGetBullionQuotesNoQuotes checks that providers without quotes do not
// count as a successful response.
func TestGetBullionQuotesNoQuotes(t *testing.T) {
	svc := newTestService([]bullionProvider{
		{name: providerSberbank, client: stubBullionsClient{info: &client.QuotesInfo{}}},
	}, nil)

	ctx, rec := newTestContext(t)
	if err := svc.GetBullionQuotes(ctx); err == nil {
		t.Fatal("GetBullionQuotes() error = nil, want failure reason")
	}
	if rec.Code != http.StatusServiceUnavailable {
		t.Fatalf("status = %d, want %d", rec.Code, http.StatusServiceUnavailable)
	}
}

// TestGetCoinQuotesPartialFailure checks that a failing provider does not fail
// the whole request when another provider returned quotes.
func TestGetCoinQuotesPartialFailure(t *testing.T) {
	date := time.Date(2026, 10, 20, 0, 0, 0, 0, time.UTC)
	svc := newTestService(nil, []coinsProvider{
		{name: providerVTB, client: stubCoinsClient{err: errors.New("vtb unavailable")}},
		{name: providerSberbank, client: stubCoinsClient{info: &client.CoinsInfo{
			Coins: []client.CoinInfo{{
				Dealer:   "Sberbank",
				Name:     "Георгий Победоносец",
				Date:     date,
				Mass:     7.78,
				Price:    50000,
				BuyPrice: 45000,
				Spread:   10,
			}},
		}}},
	})

	ctx, rec := newTestContext(t)
	if err := svc.GetCoinQuotes(ctx); err != nil {
		t.Fatalf("GetCoinQuotes() error = %v, want nil", err)
	}
	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d, want %d", rec.Code, http.StatusOK)
	}

	var coins []openapi.CoinQuote
	if err := json.Unmarshal(rec.Body.Bytes(), &coins); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if len(coins) != 1 {
		t.Fatalf("len(coins) = %d, want 1", len(coins))
	}
	if coins[0].Dealer != "Sberbank" {
		t.Errorf("dealer = %q, want %q", coins[0].Dealer, "Sberbank")
	}
}

// TestGetCoinQuotesAllProvidersFailed checks the all-failed response.
func TestGetCoinQuotesAllProvidersFailed(t *testing.T) {
	svc := newTestService(nil, []coinsProvider{
		{name: providerSberbank, client: stubCoinsClient{err: errors.New("sberbank unavailable")}},
		{name: providerVTB, client: stubCoinsClient{err: errors.New("vtb unavailable")}},
	})

	ctx, rec := newTestContext(t)
	if err := svc.GetCoinQuotes(ctx); err == nil {
		t.Fatal("GetCoinQuotes() error = nil, want failure reason")
	}
	if rec.Code != http.StatusServiceUnavailable {
		t.Fatalf("status = %d, want %d", rec.Code, http.StatusServiceUnavailable)
	}
}

// TestGetCoinQuotesEmptyResult checks that empty provider responses do not
// count as a successful response.
func TestGetCoinQuotesEmptyResult(t *testing.T) {
	svc := newTestService(nil, []coinsProvider{
		{name: providerSberbank, client: stubCoinsClient{info: &client.CoinsInfo{}}},
		{name: providerVTB, client: stubCoinsClient{err: errors.New("vtb unavailable")}},
	})

	ctx, rec := newTestContext(t)
	if err := svc.GetCoinQuotes(ctx); err == nil {
		t.Fatal("GetCoinQuotes() error = nil, want failure reason")
	}
	if rec.Code != http.StatusServiceUnavailable {
		t.Fatalf("status = %d, want %d", rec.Code, http.StatusServiceUnavailable)
	}
}

// TestHealth checks the health endpoint response.
func TestHealth(t *testing.T) {
	ctx, rec := newTestContext(t)
	if err := Health(ctx); err != nil {
		t.Fatalf("Health() error = %v, want nil", err)
	}
	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d, want %d", rec.Code, http.StatusOK)
	}

	var body map[string]string
	if err := json.Unmarshal(rec.Body.Bytes(), &body); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if body["status"] != "ok" {
		t.Errorf("status = %q, want %q", body["status"], "ok")
	}
}
