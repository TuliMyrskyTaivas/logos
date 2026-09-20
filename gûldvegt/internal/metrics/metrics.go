// Package metrics exposes Prometheus metrics for the Gûldvegt service.
package metrics

import (
	"fmt"
	"net/http"
	"strings"
	"time"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promhttp"
)

const (
	endpointCoins    = "coins"
	endpointBullions = "bullions"

	authReasonMissingToken = "missing_token"
	authReasonInvalidToken = "invalid_token"
)

var (
	requestsSuccess = prometheus.NewCounterVec(
		prometheus.CounterOpts{
			Namespace: "guldvegt",
			Name:      "requests_success_total",
			Help:      "Number of successfully processed requests.",
		},
		[]string{"endpoint"},
	)

	requestsFailed = prometheus.NewCounterVec(
		prometheus.CounterOpts{
			Namespace: "guldvegt",
			Name:      "requests_failed_total",
			Help:      "Number of requests that ended with a processing error.",
		},
		[]string{"endpoint"},
	)

	authFailed = prometheus.NewCounterVec(
		prometheus.CounterOpts{
			Namespace: "guldvegt",
			Name:      "auth_failed_total",
			Help:      "Number of requests rejected due to authentication failure.",
		},
		[]string{"reason"},
	)
)

func init() {
	prometheus.MustRegister(requestsSuccess, requestsFailed, authFailed)
}

// IncCoinsSuccess increments the counter of successfully processed coin requests.
func IncCoinsSuccess() { requestsSuccess.WithLabelValues(endpointCoins).Inc() }

// IncCoinsFailed increments the counter of failed coin requests.
func IncCoinsFailed() { requestsFailed.WithLabelValues(endpointCoins).Inc() }

// IncBullionsSuccess increments the counter of successfully processed bullion requests.
func IncBullionsSuccess() { requestsSuccess.WithLabelValues(endpointBullions).Inc() }

// IncBullionsFailed increments the counter of failed bullion requests.
func IncBullionsFailed() { requestsFailed.WithLabelValues(endpointBullions).Inc() }

// IncAuthMissingToken increments the counter of requests rejected due to a missing token.
func IncAuthMissingToken() { authFailed.WithLabelValues(authReasonMissingToken).Inc() }

// IncAuthInvalidToken increments the counter of requests rejected due to an invalid token.
func IncAuthInvalidToken() { authFailed.WithLabelValues(authReasonInvalidToken).Inc() }

// NewServer returns an HTTP server that exposes Prometheus metrics at the
// address and path given in metricsURL, e.g. "127.0.0.1:9080/metrics".
func NewServer(metricsURL string) (*http.Server, error) {
	addr, path := splitMetricsURL(metricsURL)
	if addr == "" {
		return nil, fmt.Errorf("METRICS_URL %q does not contain a host:port", metricsURL)
	}

	mux := http.NewServeMux()
	mux.Handle(path, promhttp.Handler())

	return &http.Server{
		Addr:    addr,
		Handler: mux,
		ReadHeaderTimeout: 3 * time.Second, // Protection against Slowloris attack
	}, nil
}

// splitMetricsURL splits a metrics URL into a listen address and a path.
// An optional scheme prefix is stripped, and a missing path defaults to "/metrics".
func splitMetricsURL(raw string) (addr, path string) {
	u := raw
	if idx := strings.Index(u, "://"); idx >= 0 {
		u = u[idx+len("://"):]
	}

	if idx := strings.IndexByte(u, '/'); idx >= 0 {
		return u[:idx], u[idx:]
	}
	return u, "/metrics"
}
