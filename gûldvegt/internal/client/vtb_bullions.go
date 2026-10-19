package client

import (
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"math"
	"net/http"
	"time"
)

// VTBBullionsClient fetches gold bullion quotes from VTB.
type VTBBullionsClient struct {
	httpClient *http.Client
	log        *slog.Logger
}

// NewVTBBullionsClient returns a client for VTB bullion quotes.
func NewVTBBullionsClient(log *slog.Logger) *VTBBullionsClient {
	return &VTBBullionsClient{
		httpClient: &http.Client{
			Timeout: 30 * time.Second,
		},
		log: log,
	}
}

// Ensure VTBBullionsClient satisfies the ClientInterface at compile time.
var _ ClientInterface = (*VTBBullionsClient)(nil)

const (
	// vtbBullionsURL returns gold bullion bid and offer rates per gram.
	vtbBullionsURL = "https://www.vtb.ru/api/currencyrates/gold-bars"
	// vtbBullionsVendor is the vendor name assigned to all VTB bullion quotes.
	vtbBullionsVendor = "ВТБ"
	// vtbBullionsMaxWeight is the maximum bullion weight in grams to include.
	vtbBullionsMaxWeight = 1000
)

// vtbBullionsResponse mirrors the VTB gold bullion response.
type vtbBullionsResponse struct {
	DateFrom string           `json:"dateFrom"`
	Rates    []vtbBullionRate `json:"rates"`
}

// vtbBullionRate is a single bullion rate range in the VTB response.
type vtbBullionRate struct {
	AmountRange vtbBullionAmountRange `json:"amountRange"`
	Bid         float32               `json:"bid"`
	Offer       float32               `json:"offer"`
}

// vtbBullionAmountRange defines the bullion weight range in grams.
type vtbBullionAmountRange struct {
	Min float32 `json:"min"`
}

// GetQuotesInfo fetches gold bullion quotes from VTB. Bullion ranges heavier
// than 1000 grams are ignored.
func (c *VTBBullionsClient) GetQuotesInfo(ctx context.Context) (*QuotesInfo, error) {
	body, err := fetchVTB(ctx, c.httpClient, c.log, http.MethodGet, vtbBullionsURL, nil, "application/json")
	if err != nil {
		return nil, fmt.Errorf("request vtb bullions: %w", err)
	}

	return parseVTBBullions(body)
}

// parseVTBBullions decodes a VTB gold bullion response.
func parseVTBBullions(body []byte) (*QuotesInfo, error) {
	var resp vtbBullionsResponse
	if err := json.Unmarshal(body, &resp); err != nil {
		return nil, fmt.Errorf("decode vtb bullion response: %w", err)
	}

	validAt, err := time.Parse("2006-01-02T15:04:05", resp.DateFrom)
	if err != nil {
		return nil, fmt.Errorf("parse vtb bullion date %q: %w", resp.DateFrom, err)
	}

	quotes := make(Quotes, len(resp.Rates))
	for _, rate := range resp.Rates {
		weight := rate.AmountRange.Min
		if weight > vtbBullionsMaxWeight {
			continue
		}
		buyPrice := roundPrice(rate.Bid * weight)
		sellPrice := roundPrice(rate.Offer * weight)
		quotes[weight] = Quote{
			BuyPrice:  buyPrice,
			SellPrice: sellPrice,
			Spread:    spreadPercent(buyPrice, sellPrice),
		}
	}

	return &QuotesInfo{
		Quotes:  quotes,
		ValidAt: validAt,
		Vendor:  vtbBullionsVendor,
	}, nil
}

// roundPrice rounds a price to kopecks.
func roundPrice(price float32) float32 {
	return float32(math.Round(float64(price)*100) / 100)
}
