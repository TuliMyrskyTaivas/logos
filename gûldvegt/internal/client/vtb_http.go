package client

import (
	"bytes"
	"context"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"strings"

	"github.com/andybalholm/brotli"
)

// fetchVTB performs an HTTP request to VTB and returns the decoded response
// body. VTB always responds with brotli-compressed data, so it is decoded
// here instead of relying on the transport.
func fetchVTB(ctx context.Context, httpClient *http.Client, log *slog.Logger, method, url string, body []byte, accept string) ([]byte, error) {
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

	resp, err := httpClient.Do(req)
	if err != nil {
		return nil, err
	}
	defer func() {
		if err := resp.Body.Close(); err != nil {
			log.Error("close response body", slog.Any("error", err))
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
