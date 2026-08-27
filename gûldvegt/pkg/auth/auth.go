package auth

import (
	"log/slog"
	"net/http"
	"strings"

	"github.com/golang-jwt/jwt/v5"
	"github.com/labstack/echo/v5"
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
				log.Info("authorization failure", slog.String("reason", "missing bearer token"))
				return echo.NewHTTPError(http.StatusUnauthorized, "authorization failure")
			}

			claims := &tokenClaims{}
			_, err := jwt.ParseWithClaims(token, claims, func(*jwt.Token) (any, error) {
				return key, nil
			},
				jwt.WithValidMethods([]string{jwt.SigningMethodHS256.Alg()}),
				jwt.WithExpirationRequired(),
			)
			if err != nil {
				log.Info("authorization failure", slog.String("reason", "invalid token"), slog.String("error", err.Error()))
				return echo.NewHTTPError(http.StatusUnauthorized, "authorization failure")
			}

			if claims.Role != "reader" {
				log.Info("authorization failure",
					slog.String("reason", "role not allowed"),
					slog.String("name", claims.Name),
					slog.String("role", claims.Role),
				)
				return echo.NewHTTPError(http.StatusForbidden, "authorization failure")
			}

			log.Debug("request authorized", slog.String("name", claims.Name), slog.String("role", claims.Role))
			return next(c)
		}
	}
}
