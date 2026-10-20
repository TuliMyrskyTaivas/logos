package auth

import (
	"errors"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/labstack/echo/v5"
)

// TestBearerAuthSkipsPublicPaths checks that public paths are not authenticated.
func TestBearerAuthSkipsPublicPaths(t *testing.T) {
	called := false
	handler := BearerAuth([]byte("secret"), "/health")(func(*echo.Context) error {
		called = true
		return nil
	})

	req := httptest.NewRequest(http.MethodGet, "/health", nil)
	ctx := echo.NewContext(req, httptest.NewRecorder(), echo.New())

	if err := handler(ctx); err != nil {
		t.Fatalf("middleware returned error = %v, want nil", err)
	}
	if !called {
		t.Fatal("next handler was not called for a public path")
	}
}

// TestBearerAuthRejectsMissingToken checks that other paths still require a token.
func TestBearerAuthRejectsMissingToken(t *testing.T) {
	called := false
	handler := BearerAuth([]byte("secret"), "/health")(func(*echo.Context) error {
		called = true
		return nil
	})

	req := httptest.NewRequest(http.MethodGet, "/quotes/coins", nil)
	ctx := echo.NewContext(req, httptest.NewRecorder(), echo.New())

	err := handler(ctx)
	if err == nil {
		t.Fatal("middleware returned nil, want authorization error")
	}
	var httpErr *echo.HTTPError
	if !errors.As(err, &httpErr) || httpErr.Code != http.StatusUnauthorized {
		t.Fatalf("middleware error = %v, want HTTP 401", err)
	}
	if called {
		t.Fatal("next handler was called without a token")
	}
}
