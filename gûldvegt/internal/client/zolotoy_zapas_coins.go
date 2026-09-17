package client

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"regexp"
	"sort"
	"strings"
	"time"
)

// Fetches investment coin quotes from Zolotoy Zapas.
type ZolotoyZapasCoinsClient struct {
	httpClient *http.Client
	log        *slog.Logger
}

// Returns a client for Zolotoy Zapas coin quotes.
func NewZolotoyZapasCoinsClient(log *slog.Logger) *ZolotoyZapasCoinsClient {
	return &ZolotoyZapasCoinsClient{
		httpClient: &http.Client{
			Timeout: 30 * time.Second,
		},
		log: log,
	}
}

// Ensure ZolotoyZapasCoinsClient satisfies the CoinsClientInterface at compile time.
var _ CoinsClientInterface = (*ZolotoyZapasCoinsClient)(nil)

const zolotoyZapasCoinsURL = "https://www.zolotoy-zapas.ru/coins-price/most-popular/georgiy-pobedonosets/?NAME=&arrFilter_119_980181419=Y&arrFilter_112_2366072709=Y&set_filter=%D0%9F%D0%BE%D0%BA%D0%B0%D0%B7%D0%B0%D1%82%D1%8C&section_id=200&SORT=sort"

// Dealer name assigned to all Zolotoy Zapas coin quotes.
const zolotoyZapasDealer = "Золотой Запас"

// Mirrors the JSON-LD ItemList block embedded in the page.
type zolotoyZapasJSONLD struct {
	Type            string             `json:"@type"`
	ItemListElement []zolotoyZapasItem `json:"itemListElement"`
}

type zolotoyZapasItem struct {
	Item zolotoyZapasProduct `json:"item"`
}

type zolotoyZapasProduct struct {
	Name               string                 `json:"name"`
	AdditionalProperty []zolotoyZapasProperty `json:"additionalProperty"`
	Offers             []zolotoyZapasOffer    `json:"offers"`
}

type zolotoyZapasProperty struct {
	Name  string `json:"name"`
	Value any    `json:"value"`
}

type zolotoyZapasOffer struct {
	Name  string  `json:"name"`
	Price float32 `json:"price"`
}

// Matches JSON-LD script blocks on the page.
var zzJSONLDRE = regexp.MustCompile(`(?s)<script[^>]*type\s*=\s*['"]application/ld\+json['"][^>]*>(.*?)</script>`)

// Fetches investment coin quotes from Zolotoy Zapas. The page
// embeds its price list as a JSON-LD ItemList block.
func (c *ZolotoyZapasCoinsClient) GetCoinsInfo(ctx context.Context) (*CoinsInfo, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, zolotoyZapasCoinsURL, nil)
	if err != nil {
		return nil, fmt.Errorf("create request: %w", err)
	}
	req.Header.Set("Accept-Language", "ru-RU,ru;q=0.9,en;q=0.8")
	req.Header.Set("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36")

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("request zolotoy zapas coins: %w", err)
	}
	defer func() {
		if err := resp.Body.Close(); err != nil {
			c.log.Error("close response body", slog.Any("error", err))
		}
	}()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("zolotoy zapas returned status %d", resp.StatusCode)
	}

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("read response body: %w", err)
	}

	itemList, err := findZolotoyZapasItemList(string(body))
	if err != nil {
		return nil, err
	}

	now := time.Now()
	coins := make([]CoinInfo, 0, len(itemList.ItemListElement))
	for _, element := range itemList.ItemListElement {
		weight, err := zolotoyZapasWeight(element.Item.AdditionalProperty)
		if err != nil {
			return nil, fmt.Errorf("coin %q: %w", element.Item.Name, err)
		}
		buyPrice, err := zolotoyZapasOfferPrice(element.Item.Offers, "покупки")
		if err != nil {
			return nil, fmt.Errorf("coin %q: %w", element.Item.Name, err)
		}
		sellPrice, err := zolotoyZapasOfferPrice(element.Item.Offers, "продажи")
		if err != nil {
			return nil, fmt.Errorf("coin %q: %w", element.Item.Name, err)
		}
		coins = append(coins, CoinInfo{
			Dealer:   zolotoyZapasDealer,
			Name:     element.Item.Name,
			Date:     now,
			Mass:     weight,
			Price:    sellPrice,
			BuyPrice: buyPrice,
			Spread:   spreadPercent(buyPrice, sellPrice),
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

// Locates and decodes the JSON-LD ItemList block.
func findZolotoyZapasItemList(html string) (*zolotoyZapasJSONLD, error) {
	for _, match := range zzJSONLDRE.FindAllStringSubmatch(html, -1) {
		if len(match) < 2 {
			continue
		}
		var itemList zolotoyZapasJSONLD
		if err := json.Unmarshal([]byte(match[1]), &itemList); err != nil {
			continue
		}
		if itemList.Type == "ItemList" {
			return &itemList, nil
		}
	}
	return nil, fmt.Errorf("zolotoy zapas ItemList not found on the page")
}

// Returns the weight_g property value in grams.
func zolotoyZapasWeight(props []zolotoyZapasProperty) (float32, error) {
	for _, prop := range props {
		if prop.Name == "weight_g" {
			return zolotoyZapasNumber(prop.Value)
		}
	}
	return 0, fmt.Errorf("weight_g property not found")
}

// Converts a JSON number of any representation to float32.
func zolotoyZapasNumber(value any) (float32, error) {
	switch v := value.(type) {
	case float64:
		return float32(v), nil
	case float32:
		return v, nil
	case int:
		return float32(v), nil
	case int64:
		return float32(v), nil
	case json.Number:
		f, err := v.Float64()
		if err != nil {
			return 0, fmt.Errorf("invalid numeric value %q: %w", v, err)
		}
		return float32(f), nil
	default:
		return 0, fmt.Errorf("unexpected numeric value %v", value)
	}
}

// Returns the price of the offer whose name contains
// the given substring, e.g. "покупки" (buy) or "продажи" (sell).
func zolotoyZapasOfferPrice(offers []zolotoyZapasOffer, contains string) (float32, error) {
	for _, offer := range offers {
		if strings.Contains(offer.Name, contains) {
			return offer.Price, nil
		}
	}
	return 0, fmt.Errorf("offer %q not found", contains)
}
