package auth

import (
	"errors"
	"fmt"
	"log/slog"
	"net/http"
	"strings"

	"github.com/golang-jwt/jwt/v5"
	"github.com/labstack/echo/v5"

	"github.com/TuliMyrskyTaivas/guldvegt/internal/metrics"
)

const bearerScheme = "Bearer "

// tokenClaims is the JWT payload the service expects.
type tokenClaims struct {
	Name string `json:"name"`
	Role string `json:"role"`
	jwt.RegisteredClaims
}

// bearerAuth returns middleware that validates an HMAC-signed JWT in the
// Authorization header. Only unexpired tokens with role "reader" are accepted.
func BearerAuth(key []byte) echo.MiddlewareFunc {
	return func(next echo.HandlerFunc) echo.HandlerFunc {
		return func(c *echo.Context) error {
			log := c.Logger()

			header := c.Request().Header.Get(echo.HeaderAuthorization)
			token, ok := strings.CutPrefix(header, bearerScheme)

			if !ok || token == "" {
				metrics.IncAuthMissingToken()
				return echo.NewHTTPError(http.StatusUnauthorized, "authorization failure").
					Wrap(errors.New("missing bearer token"))
			}

			claims := &tokenClaims{}
			_, err := jwt.ParseWithClaims(token, claims, func(*jwt.Token) (any, error) {
				return key, nil
			},
				jwt.WithValidMethods([]string{jwt.SigningMethodHS256.Alg()}),
				jwt.WithExpirationRequired(),
			)
			if err != nil {
				metrics.IncAuthInvalidToken()
				return echo.NewHTTPError(http.StatusUnauthorized, "authorization failure").
					Wrap(fmt.Errorf("invalid token: %w", err))
			}

			if claims.Role != "reader" {
				return echo.NewHTTPError(http.StatusForbidden, "authorization failure").
					Wrap(fmt.Errorf("role not allowed: name=%q role=%q", claims.Name, claims.Role))
			}

			log.Debug("request authorized", slog.String("name", claims.Name), slog.String("role", claims.Role))
			return next(c)
		}
	}
}
