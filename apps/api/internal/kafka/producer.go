package kafka

import (
	"context"
	"fmt"

	"github.com/drawing2dxf/api/internal/observability"
	"github.com/twmb/franz-go/pkg/kgo"
	"go.uber.org/zap"
)

type Producer struct {
	cl     *kgo.Client
	logger *zap.Logger
}

func NewProducer(brokers []string, clientID string, logger *zap.Logger) (*Producer, error) {
	cl, err := kgo.NewClient(
		kgo.SeedBrokers(brokers...),
		kgo.ClientID(clientID),
		kgo.AllowAutoTopicCreation(),
		kgo.ProducerLinger(0),
	)
	if err != nil {
		return nil, fmt.Errorf("kafka producer: %w", err)
	}
	return &Producer{cl: cl, logger: logger}, nil
}

func (p *Producer) Close() {
	if p.cl != nil {
		p.cl.Close()
	}
}

// Publish synchronously delivers an envelope to a topic.
func (p *Producer) Publish(ctx context.Context, topic string, env *Envelope) error {
	body, err := env.Marshal()
	if err != nil {
		return err
	}
	rec := &kgo.Record{
		Topic: topic,
		Key:   []byte(env.Key()),
		Value: body,
	}
	res := p.cl.ProduceSync(ctx, rec)
	if err := res.FirstErr(); err != nil {
		observability.KafkaErrors.WithLabelValues("produce").Inc()
		return fmt.Errorf("kafka produce %s: %w", topic, err)
	}
	observability.KafkaProduced.WithLabelValues(topic).Inc()
	if p.logger != nil {
		p.logger.Debug("kafka produced",
			zap.String("topic", topic),
			zap.String("event_type", env.EventType),
			zap.String("event_id", env.EventID),
		)
	}
	return nil
}
