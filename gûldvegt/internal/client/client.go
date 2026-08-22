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
