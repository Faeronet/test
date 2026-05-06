package observability

import (
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
)

var (
	HTTPRequests = promauto.NewCounterVec(prometheus.CounterOpts{
		Name: "d2d_http_requests_total",
		Help: "HTTP requests served by the API.",
	}, []string{"method", "route", "status"})

	HTTPDuration = promauto.NewHistogramVec(prometheus.HistogramOpts{
		Name:    "d2d_http_request_duration_seconds",
		Help:    "HTTP request latency.",
		Buckets: prometheus.DefBuckets,
	}, []string{"method", "route"})

	KafkaProduced = promauto.NewCounterVec(prometheus.CounterOpts{
		Name: "d2d_kafka_produced_total",
		Help: "Events produced to Kafka.",
	}, []string{"topic"})

	KafkaErrors = promauto.NewCounterVec(prometheus.CounterOpts{
		Name: "d2d_kafka_errors_total",
		Help: "Errors interacting with Kafka.",
	}, []string{"op"})

	UploadsBytes = promauto.NewCounter(prometheus.CounterOpts{
		Name: "d2d_uploaded_bytes_total",
		Help: "Total bytes uploaded by users.",
	})
)
