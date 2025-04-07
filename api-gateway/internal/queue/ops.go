package queue

import (
	"context"
	"time"

	amqp "github.com/rabbitmq/amqp091-go"
	"github.com/rs/zerolog/log"
)

func (client *QueueClient) Push(data []byte) error {
	client.m.Lock()
	if !client.isReady {
		client.m.Unlock()
		return errNotConnected
	}
	client.m.Unlock()
	for {
		err := client.unsafePush(data)
		if err != nil {
			log.Error().Err(err).Msg("message pushed failed, retrying...")
			select {
			case <-client.done:
				return errShutdown
			case <-time.After(resendDelay):
			}
			continue
		}
		confirm := <-client.notifyConfirm
		if confirm.Ack {
			log.Info().Msgf("push confirmed [%d]", confirm.DeliveryTag)
			return nil
		}
	}
}

func (client *QueueClient) unsafePush(data []byte) error {
	client.m.Lock()
	if !client.isReady {
		client.m.Unlock()
		return errNotConnected
	}
	client.m.Unlock()

	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	return client.channel.PublishWithContext(
		ctx,
		"",
		client.queueName,
		false,
		false,
		amqp.Publishing{
			ContentType: "json",
			Body:        data,
		},
	)
}

func (client *QueueClient) Close() error {
	client.m.Lock()
	defer client.m.Unlock()

	if !client.isReady {
		return errAlreadyClosed
	}
	close(client.done)
	err := client.channel.Close()
	if err != nil {
		return err
	}

	err = client.connection.Close()
	if err != nil {
		return err
	}

	client.isReady = false
	return nil
}
