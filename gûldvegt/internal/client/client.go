package client

import (
	"context"
	"time"
)

// Single quote for some coin or bullion
type Quote struct {
	BuyPrice  float32
	SellPrice float32
	Spread    float32
}

// Quotes for the different weights
type Quotes map[float32]Quote

type QuotesInfo struct {
	Quotes  Quotes
	ValidAt time.Time
}

type ClientInterface interface {
	GetQuotesInfo(ctx context.Context) (*QuotesInfo, error)
}

// CoinInfo is a single investment coin quote.
type CoinInfo struct {
	Name     string
	Date     string
	Mass     float32
	Price    float32
	BuyPrice float32
	Spread   float32
}

// CoinsInfo holds the list of investment coin quotes.
type CoinsInfo struct {
	Coins []CoinInfo
}

// CoinsClientInterface fetches investment coin quotes.
type CoinsClientInterface interface {
	GetCoinsInfo(ctx context.Context) (*CoinsInfo, error)
}

// spreadPercent returns the difference between the sell and buy prices as a
// percentage of the sell price. It returns 0 when either sell price or by price is zero.
func spreadPercent(buyPrice, sellPrice float32) float32 {
	if sellPrice == 0 || buyPrice == 0 {
		return 0
	}
	return (sellPrice - buyPrice) / sellPrice * 100
}
