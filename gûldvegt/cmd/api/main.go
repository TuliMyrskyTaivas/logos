package main

import (
	"context"
	"errors"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"sync"
	"syscall"
	"time"

	"github.com/labstack/echo/v5"
	"github.com/labstack/echo/v5/middleware"

	"github.com/TuliMyrskyTaivas/guldvegt/internal/api"
	"github.com/TuliMyrskyTaivas/guldvegt/internal/generated/openapi"
	"github.com/TuliMyrskyTaivas/guldvegt/internal/metrics"
	"github.com/TuliMyrskyTaivas/guldvegt/pkg/auth"
	"github.com/TuliMyrskyTaivas/guldvegt/pkg/logger"
)

const shutdownTimeout = 10 * time.Second

func startMetrics(ctx context.Context, wg *sync.WaitGroup, cancel context.CancelFunc, log *slog.Logger, url string) {
	defer wg.Done()

	metricsServer, err := metrics.NewServer(url)
	if err != nil {
		log.Error("invalid url for metrics publication", slog.Any("error", err))
		cancel()
		return
	}

	errCh := make(chan error, 1)
	go func() {
		log.Info("metrics server listening", slog.String("address", metricsServer.Addr))
		errCh <- metricsServer.ListenAndServe()
	}()

	select {
	case <-ctx.Done():
		shutdownCtx, cancel := context.WithTimeout(context.Background(), shutdownTimeout)
		defer cancel()
		if err := metricsServer.Shutdown(shutdownCtx); err != nil && !errors.Is(err, http.ErrServerClosed) {
			log.Error("metrics server shutdown error", slog.Any("error", err))
		}
		if err := <-errCh; err != nil && !errors.Is(err, http.ErrServerClosed) {
			log.Error("metrics server error", slog.Any("error", err))
		}

	case err := <-errCh:
		if err != nil && !errors.Is(err, http.ErrServerClosed) {
			log.Error("metrics server error", slog.Any("error", err))
		}
		cancel()
	}
}

func startService(ctx context.Context, wg *sync.WaitGroup, cancel context.CancelFunc, log *slog.Logger, bearer string) {
	defer wg.Done()

	server := echo.New()
	server.Logger = log
	server.Use(middleware.RequestLogger())
	server.Use(auth.BearerAuth([]byte(bearer)))

	service := api.NewService(log)
	openapi.RegisterHandlers(server, service)

	log.Info("server listening", slog.String("address", ":9080"))
	startErr := echo.StartConfig{
		Address:         ":9080",
		HideBanner:      true,
		HidePort:        true,
		GracefulTimeout: shutdownTimeout,
	}.Start(ctx, server)
	if startErr != nil && !errors.Is(startErr, http.ErrServerClosed) {
		log.Error("server error", slog.Any("error", startErr))
		cancel()
	}
}

func main() {
	log := logger.SetupLogger()

	key := os.Getenv("BEARER_KEY")
	if key == "" {
		log.Error("BEARER_KEY environment variable is not set; refusing to start")
		os.Exit(1)
	}

	metricsURL := os.Getenv("METRICS_URL")
	if metricsURL == "" {
		log.Error("METRICS_URL environment variable is not set; refusing to start")
		os.Exit(1)
	}

	// Create a context that will be canceled on interrupt/termination
	signalCtx, stop := signal.NotifyContext(context.Background(),
		os.Interrupt,    // SIGINT (Ctrl+C)
		syscall.SIGTERM, // Kubernetes/Systemd termination
		syscall.SIGQUIT, // Graceful shutdown
	)
	defer stop() // Release signal resources when main exits

	// Create a cancellation context for webserver
	ctx, cancel := context.WithCancel(signalCtx)
	defer cancel() // Release resources

	var wg sync.WaitGroup
	wg.Add(2)

	// Start metrics server
	go startMetrics(ctx, &wg, cancel, log, metricsURL)
	// Start main service
	go startService(ctx, &wg, cancel, log, key)

	// Wait for a signal to stop
	<-ctx.Done()
	log.Info("shutdown signal received")
	wg.Wait()
	log.Info("graceful shutdown complete")
}
