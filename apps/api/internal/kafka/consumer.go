package kafka

import (
	"context"
	"fmt"

	"github.com/twmb/franz-go/pkg/kgo"
	"go.uber.org/zap"
)

// Handler is the contract for processing a single envelope. Handlers must be
// idempotent (keyed by page_id + event_type / stage) — the API and worker
// repositories enforce this with unique indexes on (page_id, stage).
type Handler func(ctx context.Context, topic string, env *Envelope) error

type Consumer struct {
	cl     *kgo.Client
	logger *zap.Logger
	prod   *Producer  // used for deadletter routing
}

func NewConsumer(brokers []string, group, clientID string, topics []string, logger *zap.Logger) (*Consumer, error) {
	cl, err := kgo.NewClient(
		kgo.SeedBrokers(brokers...),
		kgo.ClientID(clientID),
		kgo.ConsumerGroup(group),
		kgo.ConsumeTopics(topics...),
		kgo.DisableAutoCommit(),
		kgo.AllowAutoTopicCreation(),
	)
	if err != nil {
		return nil, fmt.Errorf("kafka consumer: %w", err)
	}
	return &Consumer{cl: cl, logger: logger}, nil
}

func (c *Consumer) WithDeadletter(p *Producer) *Consumer {
	c.prod = p
	return c
}

func (c *Consumer) Close() {
	if c.cl != nil {
		c.cl.Close()
	}
}

// Run blocks polling and dispatching messages to the handler. It commits
// offsets only after the handler returns nil.
func (c *Consumer) Run(ctx context.Context, handler Handler, maxRetries int) error {
	for {
		if err := ctx.Err(); err != nil {
			return err
		}
		fetches := c.cl.PollFetches(ctx)
		if errs := fetches.Errors(); len(errs) > 0 {
			for _, e := range errs {
				c.logger.Warn("kafka fetch error",
					zap.String("topic", e.Topic),
					zap.Int32("partition", e.Partition),
					zap.Error(e.Err),
				)
			}
		}
		fetches.EachRecord(func(r *kgo.Record) {
			env, err := ParseEnvelope(r.Value)
			if err != nil {
				c.logger.Error("invalid envelope, sending to deadletter",
					zap.String("topic", r.Topic), zap.Error(err))
				c.deadletter(ctx, r, err)
				return
			}
			if hErr := handler(ctx, r.Topic, env); hErr != nil {
				c.logger.Error("handler error",
					zap.String("topic", r.Topic),
					zap.String("event_id", env.EventID),
					zap.Int("attempt", env.Attempt),
					zap.Error(hErr),
				)
				if env.Attempt >= maxRetries {
					c.deadletter(ctx, r, hErr)
				}
			}
		})
		if err := c.cl.CommitUncommittedOffsets(ctx); err != nil {
			c.logger.Warn("kafka commit error", zap.Error(err))
		}
	}
}

func (c *Consumer) deadletter(ctx context.Context, r *kgo.Record, processingErr error) {
	if c.prod == nil {
		return
	}
	env, err := ParseEnvelope(r.Value)
	if err != nil {
		env = NewEnvelope("deadletter.malformed")
		env.Payload["raw"] = string(r.Value)
	}
	env.Payload["original_topic"] = r.Topic
	env.Payload["error"] = processingErr.Error()
	if dlErr := c.prod.Publish(ctx, TopicDeadletter, env); dlErr != nil {
		c.logger.Error("deadletter publish failed", zap.Error(dlErr))
	}
}
