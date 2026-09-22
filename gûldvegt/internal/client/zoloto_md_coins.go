package client

import (
	"context"
	"fmt"
	"html"
	"io"
	"log/slog"
	"net/http"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"time"
)

// ZolotoMDCoinsClient fetches investment coin quotes from Zoloto MD
// ("Золотой монетный дом").
type ZolotoMDCoinsClient struct {
	httpClient *http.Client
	log        *slog.Logger
}

// NewZolotoMDCoinsClient returns a client for Zoloto MD coin quotes.
func NewZolotoMDCoinsClient(log *slog.Logger) *ZolotoMDCoinsClient {
	return &ZolotoMDCoinsClient{
		httpClient: &http.Client{
			Timeout: 30 * time.Second,
		},
		log: log,
	}
}

// Ensure ZolotoMDCoinsClient satisfies the CoinsClientInterface at compile time.
var _ CoinsClientInterface = (*ZolotoMDCoinsClient)(nil)

// zolotoMDDealer is the dealer name assigned to all Zoloto MD coin quotes.
const zolotoMDDealer = "Золотой монетный дом"

// zolotoMDURLs are the category pages to fetch: Russian coins and foreign
// (Austrian) coins.
var zolotoMDURLs = []string{
	"https://zoloto-md.ru/bullion-coins/i-rossiya-i-sssr" +
		"?available=1" +
		"&metal=%D0%97%D0%BE%D0%BB%D0%BE%D1%82%D0%BE" +
		"&coincategory=%D0%9C%D0%B8%D1%84%D1%8B;%20%D0%BB%D0%B5%D0%B3%D0%B5%D0%BD%D0%B4%D1%8B;%20%D0%B3%D0%B5%D1%80%D0%B0%D0%BB%D1%8C%D0%B4%D0%B8%D0%BA%D0%B0" +
		"&country=%D0%A0%D0%BE%D1%81%D1%81%D0%B8%D1%8F",
	"https://zoloto-md.ru/bullion-coins/i-inostrannyye" +
		"?available=1" +
		"&metal=%D0%97%D0%BE%D0%BB%D0%BE%D1%82%D0%BE" +
		"&country=%D0%90%D0%B2%D1%81%D1%82%D1%80%D0%B8%D1%8F",
}

// One coin card, from the product-list_item wrapper up to its closing comment.
var zmdProductRE = regexp.MustCompile(`(?s)<div class="js-product product-list_item"[^>]*>(.*?)<!-- /\.product -->`)

// The coin name sits in a <p> inside an <a class="pi-link-dark"> link.
var zmdNameRE = regexp.MustCompile(`(?s)<a class="pi-link-dark"[^>]*>.*?<p>(.*?)</p>`)

// Standard sell and buy-back prices. The buy-back span is absent when the
// dealer only quotes on request, so no match means "no buy price".
var zmdSellPriceRE = regexp.MustCompile(`<span class="js-price">([^<]+)</span>`)
var zmdBuyPriceRE = regexp.MustCompile(`<span class="js-price-buyout">([^<]+)</span>`)

// Pure-metal weight in grams, embedded in the coin name as "15.55 г" or
// "7.78 гр". The trailing character class skips years such as "2026 г.в.".
var zmdWeightRE = regexp.MustCompile(`(\d+(?:[.,]\d+)?)\s*г(?:р)?(?:[\s,(]|$)`)

// zmdPriceSeparators strips the digit-grouping characters from rendered prices.
var zmdPriceSeparators = strings.NewReplacer(" ", "", "\u00a0", "", "\u202f", "")

// GetCoinsInfo fetches coin quotes from all Zoloto MD category pages and
// returns them as a single combined list. A page that fails to load is
// skipped with a warning; the error is only returned when every page fails.
func (c *ZolotoMDCoinsClient) GetCoinsInfo(ctx context.Context) (*CoinsInfo, error) {
	now := time.Now()

	var coins []CoinInfo
	var firstErr error
	for _, u := range zolotoMDURLs {
		pageCoins, err := c.fetchPage(ctx, u, now)
		if err != nil {
			if firstErr == nil {
				firstErr = err
			}
			c.log.Warn("skip zoloto-md page", slog.String("url", u), slog.Any("error", err))
			continue
		}
		coins = append(coins, pageCoins...)
	}

	if len(coins) == 0 && firstErr != nil {
		return nil, firstErr
	}

	sort.SliceStable(coins, func(i, j int) bool {
		if coins[i].Name != coins[j].Name {
			return coins[i].Name < coins[j].Name
		}
		return coins[i].Mass < coins[j].Mass
	})

	return &CoinsInfo{Coins: coins}, nil
}

// fetchPage downloads and parses a single category page.
func (c *ZolotoMDCoinsClient) fetchPage(ctx context.Context, url string, now time.Time) ([]CoinInfo, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
	if err != nil {
		return nil, fmt.Errorf("create request: %w", err)
	}
	req.Header.Set("Accept-Language", "ru-RU,ru;q=0.9,en;q=0.8")
	req.Header.Set("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36")

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("request zoloto-md coins: %w", err)
	}
	defer func() {
		if err := resp.Body.Close(); err != nil {
			c.log.Error("close response body", slog.Any("error", err))
		}
	}()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("zoloto-md returned status %d", resp.StatusCode)
	}

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("read response body: %w", err)
	}

	return parseZolotoMDPage(string(body), now), nil
}

// parseZolotoMDPage extracts coin cards from the filtered results section of
// a page, ignoring the "showcase" slider with other products.
func parseZolotoMDPage(pageHTML string, now time.Time) []CoinInfo {
	section := pageHTML
	if start := strings.Index(pageHTML, `id="coin-filter-results"`); start != -1 {
		if end := strings.Index(pageHTML, `id="showcase-filter-target"`); end != -1 {
			section = pageHTML[start:end]
		}
	}

	coins := make([]CoinInfo, 0)
	for _, card := range zmdProductRE.FindAllStringSubmatch(section, -1) {
		if len(card) < 2 {
			continue
		}
		name := zmdCoinName(card[1])
		if name == "" {
			continue
		}
		sellPrice := zmdParsePrice(zmdFirstGroup(zmdSellPriceRE.FindStringSubmatch(card[1])))
		buyPrice := zmdParsePrice(zmdFirstGroup(zmdBuyPriceRE.FindStringSubmatch(card[1])))
		coins = append(coins, CoinInfo{
			Dealer:   zolotoMDDealer,
			Name:     name,
			Date:     now,
			Mass:     zmdParseWeight(name),
			Price:    sellPrice,
			BuyPrice: buyPrice,
			Spread:   spreadPercent(buyPrice, sellPrice),
		})
	}
	return coins
}

// zmdCoinName extracts and unescapes the coin name from a card.
func zmdCoinName(card string) string {
	name := zmdFirstGroup(zmdNameRE.FindStringSubmatch(card))
	return strings.TrimSpace(html.UnescapeString(name))
}

// zmdFirstGroup returns the first capture group of a match, or "".
func zmdFirstGroup(match []string) string {
	if len(match) >= 2 {
		return match[1]
	}
	return ""
}

// zmdParsePrice converts a rendered price such as "216 469" to float32.
func zmdParsePrice(s string) float32 {
	s = zmdPriceSeparators.Replace(s)
	if s == "" {
		return 0
	}
	v, err := strconv.ParseFloat(s, 32)
	if err != nil {
		return 0
	}
	return float32(v)
}

// zmdParseWeight extracts the pure-metal weight in grams from the coin name.
func zmdParseWeight(name string) float32 {
	raw := zmdFirstGroup(zmdWeightRE.FindStringSubmatch(name))
	if raw == "" {
		return 0
	}
	v, err := strconv.ParseFloat(strings.Replace(raw, ",", ".", 1), 32)
	if err != nil {
		return 0
	}
	return float32(v)
}
