package client

import (
	"context"
	"crypto/tls"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strconv"
	"time"
)

// SberBullionsClient fetches gold bullion quotes from Sberbank.
type SberBullionsClient struct {
	httpClient *http.Client
}

// NewSberBullionsClient returns a client for Sberbank bullion quotes.
func NewSberBullionsClient() *SberBullionsClient {
	transport := http.DefaultTransport.(*http.Transport).Clone()
	// certificate verification is disabled for sberbank.ru.
	transport.TLSClientConfig = &tls.Config{InsecureSkipVerify: true} //nolint:gosec

	return &SberBullionsClient{
		httpClient: &http.Client{
			Transport: transport,
			Timeout:   30 * time.Second,
		},
	}
}

// Ensure SberBullionsClient satisfies the ClientInterface at compile time.
var _ ClientInterface = (*SberBullionsClient)(nil)

const sberBullionsURL = "https://www.sberbank.ru/proxy/services/rates/public/v2/historyIngots"

// sberHistoryRatesResponse mirrors the nested structure of the Sberbank
// response: historyRates -> date -> metal -> ISO code -> timestamp -> record.
type sberHistoryRatesResponse struct {
	HistoryRates map[string]map[string]map[string]map[string]sberRecord `json:"historyRates"`
}

type sberRecord struct {
	RangeList []sberRangeItem `json:"rangeList"`
}

type sberRangeItem struct {
	Wrapper   string  `json:"wrapper"`
	Condition string  `json:"condition"`
	Mass      float32 `json:"mass"`
	RateSell  float32 `json:"rateSell"`
	RateBuy   float32 `json:"rateBuy"`
}

// GetQuotesInfo fetches gold bullion quotes for the current day.
func (c *SberBullionsClient) GetQuotesInfo(ctx context.Context) (*QuotesInfo, error) {
	// Request quotes from the beginning of the current day (local time).
	now := time.Now()
	startOfDay := time.Date(now.Year(), now.Month(), now.Day(), 0, 0, 0, 0, now.Location())
	dateMs := startOfDay.UnixMilli()

	u, err := url.Parse(sberBullionsURL)
	if err != nil {
		return nil, fmt.Errorf("parse sberbank URL: %w", err)
	}
	q := u.Query()
	q.Set("rateType", "PMR-1")
	q.Set("isoCode", "A98")
	q.Set("date", strconv.FormatInt(dateMs, 10))
	q.Set("segType", "TRADITIONAL")
	q.Set("id", "38")
	u.RawQuery = q.Encode()

	req, err := http.NewRequestWithContext(ctx, http.MethodGet, u.String(), nil)
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
		return nil, fmt.Errorf("request sberbank quotes: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("sberbank returned status %d", resp.StatusCode)
	}

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("read response body: %w", err)
	}

	var rates sberHistoryRatesResponse
	if err := json.Unmarshal(body, &rates); err != nil {
		return nil, fmt.Errorf("decode sberbank response: %w", err)
	}

	// Select the latest record across all nested maps.
	var latestTs int64
	var latestRecord *sberRecord
	for _, byDate := range rates.HistoryRates {
		for _, byMetal := range byDate {
			for _, byISO := range byMetal {
				for tsStr, record := range byISO {
					ts, err := strconv.ParseInt(tsStr, 10, 64)
					if err != nil {
						continue
					}
					if latestRecord == nil || ts > latestTs {
						latestTs = ts
						latestRecord = &record
					}
				}
			}
		}
	}

	if latestRecord == nil {
		return nil, fmt.Errorf("no quote records in sberbank response")
	}

	// Keep only standard bullions in excellent condition.
	quotes := make(Quotes)
	for _, item := range latestRecord.RangeList {
		if item.Wrapper == "STANDARD" && item.Condition == "EXCELLENT" {
			quotes[item.Mass] = Quote{
				BuyPrice:  item.RateBuy,
				SellPrice: item.RateSell,
			}
		}
	}

	return &QuotesInfo{
		Quotes:  quotes,
		ValidAt: time.UnixMilli(latestTs),
	}, nil
}
