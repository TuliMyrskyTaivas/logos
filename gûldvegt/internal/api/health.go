package api

import (
	"net/http"

	"github.com/labstack/echo/v5"
)

// HealthPath is the path of the service health endpoint. The endpoint is not
// part of the OpenAPI specification and is served without authentication.
const HealthPath = "/health"

// Health reports that the service is running. It is used by the container
// health check and returns 200 OK as long as the HTTP server accepts requests.
func Health(ctx *echo.Context) error {
	return ctx.JSON(http.StatusOK, map[string]string{"status": "ok"})
}
