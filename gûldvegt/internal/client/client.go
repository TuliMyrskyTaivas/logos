package client

import (
	"context"
	"time"
)

// Single quote for some coin or bullion
type Quote struct {
	BuyPrice  float32
	SellPrice float32
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
}

// CoinsInfo holds the list of investment coin quotes.
type CoinsInfo struct {
	Coins []CoinInfo
}

// CoinsClientInterface fetches investment coin quotes.
type CoinsClientInterface interface {
	GetCoinsInfo(ctx context.Context) (*CoinsInfo, error)
}
