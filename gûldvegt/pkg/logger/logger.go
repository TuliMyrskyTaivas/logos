package logger

import (
	"log/slog"
	"os"
	"time"

	slogformatter "github.com/samber/slog-formatter"
)

func SetupLogger() *slog.Logger {
	var log *slog.Logger
	var logOptions slog.HandlerOptions

	logLevel := os.Getenv("LOGOS_LOG_LEVEL")
	switch logLevel {
	case "debug":
		logOptions.Level = slog.LevelDebug
	case "info":
		logOptions.Level = slog.LevelInfo
	case "warning":
		logOptions.Level = slog.LevelWarn
	case "error":
		logOptions.Level = slog.LevelError
	default:
		logOptions.Level = slog.LevelInfo
	}

	log = slog.New(slogformatter.NewFormatterHandler(
		slogformatter.TimezoneConverter(time.UTC),
		slogformatter.TimeFormatter(time.RFC3339, nil),
	)(
		slog.NewTextHandler(os.Stdout, &logOptions),
	))

	slog.SetDefault(log)
	return log
}
