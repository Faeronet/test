package jobs

import (
	"context"

	"github.com/drawing2dxf/api/internal/kafka"
	"go.uber.org/zap"
)

// Tap consumes every Kafka topic and republishes envelopes through the
// EventHub. This is a lightweight progress aggregator used by the UI.
func Tap(ctx context.Context, brokers []string, group, clientID string, hub *EventHub, logger *zap.Logger) error {
	cons, err := kafka.NewConsumer(brokers, group, clientID, kafka.AllTopics, logger)
	if err != nil {
		return err
	}
	go func() {
		_ = cons.Run(ctx, func(_ context.Context, _ string, env *kafka.Envelope) error {
			hub.Publish(env)
			return nil
		}, 5)
	}()
	return nil
}
