package client

import (
	"bytes"
	"context"
	"crypto/tls"
	"encoding/json"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"strings"
	"time"
)

// SberCoinsClient fetches investment coin quotes from Sberbank.
type SberCoinsClient struct {
	httpClient *http.Client
	log        *slog.Logger
}

// NewSberCoinsClient returns a client for Sberbank coin quotes.
func NewSberCoinsClient(log *slog.Logger) *SberCoinsClient {
	transport := http.DefaultTransport.(*http.Transport).Clone()
	// certificate verification is disabled for sberbank.ru.
	transport.TLSClientConfig = &tls.Config{InsecureSkipVerify: true} //nolint:gosec

	return &SberCoinsClient{
		httpClient: &http.Client{
			Transport: transport,
			Timeout:   30 * time.Second,
		},
		log: log,
	}
}

// Ensure SberCoinsClient satisfies the CoinsClientInterface at compile time.
var _ CoinsClientInterface = (*SberCoinsClient)(nil)

const sberCoinsURL = "https://www.sberbank.ru/proxy/services/coin-catalog/coins"

// sberCoinsBuyoutURL returns the buyback quotes for investment coins.
const sberCoinsBuyoutURL = "https://www.sberbank.ru/proxy/services/coin-catalog/coins/buyout?query=&page=0"

// sberCoinsRequest is the POST payload for the Sberbank coin catalog.
type sberCoinsRequest struct {
	Query        string   `json:"query"`
	PriceSellMin int      `json:"priceSellMin"`
	PriceSellMax int      `json:"priceSellMax"`
	ParMin       int      `json:"parMin"`
	ParMax       int      `json:"parMax"`
	MassMin      int      `json:"massMin"`
	MassMax      int      `json:"massMax"`
	Metals       []string `json:"metals"`
	Sections     []string `json:"sections"`
	Categories   []string `json:"categories"`
	Condition    int      `json:"condition"`
	VspCode      any      `json:"vspCode"`
	InDiscount   bool     `json:"inDiscount"`
	Page         int      `json:"page"`
	PageSize     int      `json:"pageSize"`
	City         string   `json:"city"`
}

// sberCoinsResponse mirrors the Sberbank coin catalog response.
type sberCoinsResponse struct {
	Entities []sberCoin `json:"entities"`
}

// sberCoin is a single entry in the Sberbank coin catalog.
type sberCoin struct {
	ID    string  `json:"id"`
	Name  string  `json:"name"`
	Date  string  `json:"date"`
	Mass1 float32 `json:"mass1"`
	Price float32 `json:"price"`
}

// sberCoinsBuyoutResponse mirrors the Sberbank coin buyout response.
type sberCoinsBuyoutResponse struct {
	Entities []sberCoinBuyout `json:"entities"`
}

// sberCoinBuyout is a single entry in the Sberbank coin buyout catalog.
type sberCoinBuyout struct {
	ID       string  `json:"id"`
	PriceBuy float32 `json:"priceBuy"`
}

// russianMonths maps Russian month abbreviations used by Sberbank to English
// month names understood by time.Parse.
var russianMonths = map[string]string{
	"янв": "Jan",
	"фев": "Feb",
	"мар": "Mar",
	"апр": "Apr",
	"май": "May",
	"июн": "Jun",
	"июл": "Jul",
	"авг": "Aug",
	"сен": "Sep",
	"окт": "Oct",
	"ноя": "Nov",
	"дек": "Dec",
}

// ParseCoinDate parses a Sberbank coin date such as "03 сен 2026".
func ParseCoinDate(s string) (time.Time, error) {
	parts := strings.Fields(s)
	if len(parts) != 3 {
		return time.Time{}, fmt.Errorf("unexpected coin date format %q", s)
	}
	month, ok := russianMonths[parts[1]]
	if !ok {
		return time.Time{}, fmt.Errorf("unknown month in coin date %q", s)
	}
	t, err := time.Parse("_2 Jan 2006", parts[0]+" "+month+" "+parts[2])
	if err != nil {
		return time.Time{}, fmt.Errorf("parse coin date %q: %w", s, err)
	}
	return t, nil
}

// GetCoinsInfo fetches investment coin quotes from Sberbank, filtering out
// the "Талисман" (talisman) coins.
func (c *SberCoinsClient) GetCoinsInfo(ctx context.Context) (*CoinsInfo, error) {
	payload := sberCoinsRequest{
		Query:        "",
		PriceSellMin: 0,
		PriceSellMax: 0,
		ParMin:       0,
		ParMax:       0,
		MassMin:      0,
		MassMax:      0,
		Metals:       []string{"Золото"},
		Sections:     []string{"Инвестиционные монеты"},
		Categories:   []string{},
		Condition:    1,
		VspCode:      nil,
		InDiscount:   false,
		Page:         0,
		PageSize:     15,
		City:         "Москва",
	}

	body, err := json.Marshal(payload)
	if err != nil {
		return nil, fmt.Errorf("marshal sberbank coin request: %w", err)
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, sberCoinsURL, bytes.NewReader(body))
	if err != nil {
		return nil, fmt.Errorf("create request: %w", err)
	}
	req.Header.Set("Accept-Language", "ru,en;q=0.9,en-GB;q=0.8,en-US;q=0.7,fr-FR;q=0.6,fr;q=0.5")
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Dnt", "1")
	req.Header.Set("Priority", "u=1, i")
	req.Header.Set("Referer", "https://www.sberbank.ru/ru/person/metall")
	req.Header.Set("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0")

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("request sberbank coins: %w", err)
	}
	defer func() {
		if err := resp.Body.Close(); err != nil {
			c.log.Error("close response body", slog.Any("error", err))
		}
	}()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("sberbank returned status %d", resp.StatusCode)
	}

	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("read response body: %w", err)
	}

	var coinsResp sberCoinsResponse
	if err := json.Unmarshal(respBody, &coinsResp); err != nil {
		return nil, fmt.Errorf("decode sberbank response: %w", err)
	}

	buyoutPrices, err := c.fetchBuyoutPrices(ctx)
	if err != nil {
		return nil, err
	}

	coins := make([]CoinInfo, 0, len(coinsResp.Entities))
	for _, entity := range coinsResp.Entities {
		if strings.Contains(entity.Name, "Талисман") {
			continue
		}
		coins = append(coins, CoinInfo{
			Name:     entity.Name,
			Date:     entity.Date,
			Mass:     entity.Mass1,
			Price:    entity.Price,
			BuyPrice: buyoutPrices[entity.ID],
			Spread:   spreadPercent(buyoutPrices[entity.ID], entity.Price),
		})
	}

	return &CoinsInfo{Coins: coins}, nil
}

// fetchBuyoutPrices fetches Sberbank coin buyback quotes and returns them
// keyed by coin ID.
func (c *SberCoinsClient) fetchBuyoutPrices(ctx context.Context) (map[string]float32, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, sberCoinsBuyoutURL, nil)
	if err != nil {
		return nil, fmt.Errorf("create request: %w", err)
	}
	req.Header.Set("Accept-Language", "ru,en;q=0.9,en-GB;q=0.8,en-US;q=0.7,fr-FR;q=0.6,fr;q=0.5")
	req.Header.Set("Dnt", "1")
	req.Header.Set("Priority", "u=1, i")
	req.Header.Set("Referer", "https://www.sberbank.ru/ru/person/metall")
	req.Header.Set("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0")

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("request sberbank coin buyout: %w", err)
	}
	defer func() {
		if err := resp.Body.Close(); err != nil {
			c.log.Error("close response body", slog.Any("error", err))
		}
	}()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("sberbank returned status %d", resp.StatusCode)
	}

	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("read response body: %w", err)
	}

	var buyoutResp sberCoinsBuyoutResponse
	if err := json.Unmarshal(respBody, &buyoutResp); err != nil {
		return nil, fmt.Errorf("decode sberbank buyout response: %w", err)
	}

	prices := make(map[string]float32, len(buyoutResp.Entities))
	for _, entity := range buyoutResp.Entities {
		prices[entity.ID] = entity.PriceBuy
	}

	return prices, nil
}
