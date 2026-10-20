package logger

import (
	"context"
	"log/slog"
	"net/http"

	"github.com/labstack/echo/v5"
	"github.com/labstack/echo/v5/middleware"
)

// RequestLogger returns middleware that logs every handled request. Requests
// answered with 200 OK are logged at info level; any other response is logged
// at error level together with the reason of the failure. Requests to the
// given paths are not logged, e.g. frequent container health probes.
//
// Register the middleware with Echo.Pre so that requests rejected before they
// reach a handler (404, 405) are logged as well.
func RequestLogger(skipPaths ...string) echo.MiddlewareFunc {
	skipped := make(map[string]struct{}, len(skipPaths))
	for _, path := range skipPaths {
		skipped[path] = struct{}{}
	}

	return middleware.RequestLoggerWithConfig(middleware.RequestLoggerConfig{
		Skipper: func(c *echo.Context) bool {
			_, ok := skipped[c.Request().URL.Path]
			return ok
		},
		LogLatency:       true,
		LogRemoteIP:      true,
		LogHost:          true,
		LogMethod:        true,
		LogURI:           true,
		LogRequestID:     true,
		LogUserAgent:     true,
		LogStatus:        true,
		LogContentLength: true,
		LogResponseSize:  true,
		HandleError:      true,
		LogValuesFunc: func(c *echo.Context, v middleware.RequestLoggerValues) error {
			attrs := make([]slog.Attr, 0, 11)
			attrs = append(attrs,
				slog.String("method", v.Method),
				slog.String("uri", v.URI),
				slog.Int("status", v.Status),
				slog.Duration("latency", v.Latency),
				slog.String("host", v.Host),
				slog.String("bytes_in", v.ContentLength),
				slog.Int64("bytes_out", v.ResponseSize),
				slog.String("user_agent", v.UserAgent),
				slog.String("remote_ip", v.RemoteIP),
				slog.String("request_id", v.RequestID),
			)

			if v.Error == nil && v.Status == http.StatusOK {
				c.Logger().LogAttrs(context.Background(), slog.LevelInfo, "REQUEST", attrs...)
				return nil
			}

			reason := http.StatusText(v.Status)
			if v.Error != nil {
				reason = v.Error.Error()
			}
			c.Logger().LogAttrs(context.Background(), slog.LevelError, "REQUEST_ERROR",
				append(attrs, slog.String("reason", reason))...)
			return nil
		},
	})
}
