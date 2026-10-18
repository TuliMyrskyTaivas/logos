package client

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"html"
	"io"
	"log/slog"
	"math"
	"net/http"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"time"

	"github.com/andybalholm/brotli"
)

// VTBCoinsClient fetches investment coin quotes from VTB.
type VTBCoinsClient struct {
	httpClient *http.Client
	log        *slog.Logger
}

// NewVTBCoinsClient returns a client for VTB coin quotes.
func NewVTBCoinsClient(log *slog.Logger) *VTBCoinsClient {
	return &VTBCoinsClient{
		httpClient: &http.Client{
			Timeout: 30 * time.Second,
		},
		log: log,
	}
}

// Ensure VTBCoinsClient satisfies the CoinsClientInterface at compile time.
var _ CoinsClientInterface = (*VTBCoinsClient)(nil)

const (
	// vtbCoinsURL returns investment coin sell quotes.
	vtbCoinsURL = "https://www.vtb.ru/api/bff/api/v1/coin/list?page=1"
	// vtbCoinsBuybackURL is the page with coin buyback prices.
	vtbCoinsBuybackURL = "https://www.vtb.ru/personal/vklady-i-scheta/monety-iz-drag-metallov-v/"
	// vtbCoinsDealer is the dealer name assigned to all VTB coin quotes.
	vtbCoinsDealer = "ВТБ"
	vtbUserAgent   = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) " +
		"AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)

// vtbCoinsRequest is the POST payload for the VTB coin catalog.
type vtbCoinsRequest struct {
	Filters []vtbCoinFilter `json:"filters"`
}

type vtbCoinFilter struct {
	ID     string   `json:"id"`
	Values []string `json:"values"`
}

// vtbCoinsResponse mirrors the VTB coin catalog response.
type vtbCoinsResponse struct {
	Coins []vtbCoin `json:"coins"`
}

// vtbCoin is a single sell quote in the VTB coin catalog.
type vtbCoin struct {
	Name   string  `json:"name"`
	Mass   float32 `json:"mass"`
	Price1 float32 `json:"price1"`
}

// vtbBuyback is a single buyback quote parsed from the VTB web page.
type vtbBuyback struct {
	Name  string
	Mass  float32
	Price float32
}

// vtbCardMarker separates coin cards on the buyback page.
const vtbCardMarker = "card-layout-griddesktopstyles__Item"

var (
	// The coin name is the first paragraph of a card.
	vtbNameRE = regexp.MustCompile(`<p[^>]*>([^<]+)</p>`)
	// The weight is rendered as "Масса — 15,55 г".
	vtbMassRE = regexp.MustCompile(`Масса — ([\d\s\x{00A0}]+(?:,\d+)?)\s*г`)
	// The buyback price is the ruble amount immediately preceding the
	// "Цена выкупа" label.
	vtbBuybackRE = regexp.MustCompile(`>\s*([\d\s\x{00A0}]+?)\s*₽\s*</p>\s*</div>\s*<span[^>]*>\s*Цена выкупа`)
)

// vtbNumberSeparators strips the digit-grouping characters from rendered prices.
var vtbNumberSeparators = strings.NewReplacer(" ", "", "\u00a0", "", "\u202f", "")

// vtbCoinKey identifies a coin by name and pure-metal weight in hundredths of
// a gram, since the two sources render the same weight differently.
type vtbCoinKey struct {
	name     string
	massHund int
}

// GetCoinsInfo fetches investment coin sell prices from the VTB API and
// buyback prices from the VTB coins page.
func (c *VTBCoinsClient) GetCoinsInfo(ctx context.Context) (*CoinsInfo, error) {
	payload, err := json.Marshal(vtbCoinsRequest{
		Filters: []vtbCoinFilter{
			{ID: "coinCountry", Values: []string{"Российские"}},
			{ID: "coinKind", Values: []string{"Инвестиционные"}},
			{ID: "coinMetal", Values: []string{"Золото"}},
		},
	})
	if err != nil {
		return nil, fmt.Errorf("marshal vtb coin request: %w", err)
	}

	body, err := c.fetch(ctx, http.MethodPost, vtbCoinsURL, payload, "application/json")
	if err != nil {
		return nil, fmt.Errorf("request vtb coins: %w", err)
	}

	var coinsResp vtbCoinsResponse
	if err := json.Unmarshal(body, &coinsResp); err != nil {
		return nil, fmt.Errorf("decode vtb response: %w", err)
	}

	page, err := c.fetch(ctx, http.MethodGet, vtbCoinsBuybackURL, nil, "text/html,application/xhtml+xml")
	if err != nil {
		return nil, fmt.Errorf("request vtb coin buyback: %w", err)
	}

	buybacks := parseVTBBuybacks(string(page))
	if len(buybacks) == 0 {
		c.log.Warn("no vtb coin buyback prices found on the page")
	}

	prices := make(map[vtbCoinKey][]float32, len(buybacks))
	for _, buyback := range buybacks {
		key := vtbCoinKeyOf(buyback.Name, buyback.Mass)
		prices[key] = append(prices[key], buyback.Price)
	}

	now := time.Now()
	coins := make([]CoinInfo, 0, len(coinsResp.Coins))
	for _, coin := range coinsResp.Coins {
		var buyPrice float32
		key := vtbCoinKeyOf(coin.Name, coin.Mass)
		if available := prices[key]; len(available) > 0 {
			buyPrice = available[0]
			prices[key] = available[1:]
		}
		coins = append(coins, CoinInfo{
			Dealer:   vtbCoinsDealer,
			Name:     coin.Name,
			Date:     now,
			Mass:     coin.Mass,
			Price:    coin.Price1,
			BuyPrice: buyPrice,
			Spread:   spreadPercent(buyPrice, coin.Price1),
		})
	}

	sort.SliceStable(coins, func(i, j int) bool {
		if coins[i].Name != coins[j].Name {
			return coins[i].Name < coins[j].Name
		}
		return coins[i].Mass < coins[j].Mass
	})

	return &CoinsInfo{Coins: coins}, nil
}

// fetch performs an HTTP request and returns the decoded response body.
// VTB always responds with brotli-compressed data, so it is decoded here
// instead of relying on the transport.
func (c *VTBCoinsClient) fetch(ctx context.Context, method, url string, body []byte, accept string) ([]byte, error) {
	var reader io.Reader
	if body != nil {
		reader = bytes.NewReader(body)
	}

	req, err := http.NewRequestWithContext(ctx, method, url, reader)
	if err != nil {
		return nil, fmt.Errorf("create request: %w", err)
	}
	req.Header.Set("Accept", accept)
	req.Header.Set("Accept-Language", "ru-RU,ru;q=0.9,en;q=0.8")
	req.Header.Set("User-Agent", vtbUserAgent)
	if body != nil {
		req.Header.Set("Content-Type", "application/json")
	}

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, err
	}
	defer func() {
		if err := resp.Body.Close(); err != nil {
			c.log.Error("close response body", slog.Any("error", err))
		}
	}()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("vtb returned status %d", resp.StatusCode)
	}

	var respBody io.Reader = resp.Body
	if strings.EqualFold(resp.Header.Get("Content-Encoding"), "br") {
		respBody = brotli.NewReader(resp.Body)
	}

	data, err := io.ReadAll(respBody)
	if err != nil {
		return nil, fmt.Errorf("read response body: %w", err)
	}

	return data, nil
}

// parseVTBBuybacks extracts coin names, weights, and buyback prices from the
// VTB coins page.
func parseVTBBuybacks(page string) []vtbBuyback {
	cards := strings.Split(page, vtbCardMarker)
	buybacks := make([]vtbBuyback, 0, len(cards))
	for _, card := range cards[1:] {
		nameMatch := vtbNameRE.FindStringSubmatch(card)
		massMatch := vtbMassRE.FindStringSubmatch(card)
		priceMatch := vtbBuybackRE.FindStringSubmatch(card)
		if nameMatch == nil || massMatch == nil || priceMatch == nil {
			continue
		}
		buybacks = append(buybacks, vtbBuyback{
			Name:  strings.TrimSpace(html.UnescapeString(nameMatch[1])),
			Mass:  vtbParseNumber(massMatch[1]),
			Price: vtbParseNumber(priceMatch[1]),
		})
	}
	return buybacks
}

// vtbCoinKeyOf builds a lookup key from a coin name and weight.
func vtbCoinKeyOf(name string, mass float32) vtbCoinKey {
	return vtbCoinKey{
		name:     name,
		massHund: int(math.Round(float64(mass) * 100)),
	}
}

// vtbParseNumber converts a rendered number such as "12 800 000" or "15,55"
// to float32.
func vtbParseNumber(s string) float32 {
	s = vtbNumberSeparators.Replace(s)
	v, err := strconv.ParseFloat(strings.Replace(s, ",", ".", 1), 32)
	if err != nil {
		return 0
	}
	return float32(v)
}
