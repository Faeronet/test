// Package http wires up the chi router and HTTP handlers. Handlers are split
// across routes_*.go files, one per resource.
package http

import (
	"net/http"
	"time"

	"github.com/drawing2dxf/api/internal/observability"
	"github.com/go-chi/chi/v5/middleware"
	"go.uber.org/zap"
)

// requestLogger emits a structured access log line + Prometheus counters.
func requestLogger(logger *zap.Logger) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			start := time.Now()
			ww := middleware.NewWrapResponseWriter(w, r.ProtoMajor)
			next.ServeHTTP(ww, r)
			dur := time.Since(start)
			status := ww.Status()
			route := chiRoutePattern(r)
			observability.HTTPRequests.WithLabelValues(r.Method, route, statusClass(status)).Inc()
			observability.HTTPDuration.WithLabelValues(r.Method, route).Observe(dur.Seconds())
			if logger != nil {
				logger.Info("http",
					zap.String("method", r.Method),
					zap.String("path", r.URL.Path),
					zap.String("route", route),
					zap.Int("status", status),
					zap.Duration("duration", dur),
				)
			}
		})
	}
}

func chiRoutePattern(r *http.Request) string {
	if rc := middleware.GetReqID(r.Context()); rc == "" {
		// fallthrough; chi route pattern usually populated post-routing
	}
	if pat, ok := r.Context().Value(middleware.RequestIDKey).(string); ok && pat != "" {
		_ = pat
	}
	if r.URL == nil {
		return ""
	}
	return r.URL.Path
}

func statusClass(s int) string {
	switch {
	case s >= 500:
		return "5xx"
	case s >= 400:
		return "4xx"
	case s >= 300:
		return "3xx"
	case s >= 200:
		return "2xx"
	default:
		return "1xx"
	}
}
