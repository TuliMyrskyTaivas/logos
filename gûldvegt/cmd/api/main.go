package main

import (
	"errors"
	"log/slog"
	"net/http"
	"os"

	"github.com/labstack/echo/v5"
	"github.com/labstack/echo/v5/middleware"

	"github.com/TuliMyrskyTaivas/guldvegt/internal/api"
	"github.com/TuliMyrskyTaivas/guldvegt/internal/generated/openapi"
	"github.com/TuliMyrskyTaivas/guldvegt/pkg/auth"
	"github.com/TuliMyrskyTaivas/guldvegt/pkg/logger"
)

func main() {
	log := logger.SetupLogger()

	key := os.Getenv("BEARER_KEY")
	if key == "" {
		log.Error("BEARER_KEY environment variable is not set; refusing to start")
		os.Exit(1)
	}

	log.Debug("JWT", slog.String("value", key))

	server := echo.New()
	server.Logger = log
	server.Use(middleware.RequestLogger())
	server.Use(auth.BearerAuth([]byte(key)))

	service := api.NewService(log)
	openapi.RegisterHandlers(server, service)

	if err := server.Start(":8080"); err != nil && !errors.Is(err, http.ErrServerClosed) {
		log.Error("server error", slog.Any("error", err))
		os.Exit(1)
	}
}
