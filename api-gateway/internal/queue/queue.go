package queue

import (
	"errors"
	"fmt"
	"sync"
	"time"

	amqp "github.com/rabbitmq/amqp091-go"
	"github.com/rs/zerolog/log"
)

type QueueClient struct {
	m               *sync.Mutex
	queueName       string
	connection      *amqp.Connection
	channel         *amqp.Channel
	done            chan bool
	notifyConnClose chan *amqp.Error
	notifyChanClose chan *amqp.Error
	notifyConfirm   chan amqp.Confirmation
	isReady         bool
}

const (
	reconnectDelay = 5 * time.Second
	reInitDelay    = 2 * time.Second
	resendDelay    = 5 * time.Second
)

var (
	errNotConnected  = errors.New("not connected to queue server")
	errAlreadyClosed = errors.New("already closed: not connected to queue server")
	errShutdown      = errors.New("client is shutting down")
)

func NewQueueClient(queueName, addr string) *QueueClient {
	client := &QueueClient{
		m:         &sync.Mutex{},
		queueName: queueName,
		done:      make(chan bool),
	}

	go client.handleReconnect(addr)
	return client
}

func (client *QueueClient) changeConnection(connection *amqp.Connection) {
	client.connection = connection
	client.notifyConnClose = make(chan *amqp.Error, 1)
	client.connection.NotifyClose(client.notifyConnClose)
}

func (client *QueueClient) connect(addr string) (*amqp.Connection, error) {
	conn, err := amqp.Dial(addr)
	if err != nil {
		return nil, err
	}

	client.changeConnection(conn)
	log.Info().Msg("connected to queue server")
	return conn, nil
}

func (client *QueueClient) handleReconnect(addr string) {
	for {
		client.m.Lock()
		client.isReady = false
		client.m.Unlock()

		log.Info().Msg("attempting to connect to queue server")

		conn, err := client.connect(addr)
		if err != nil {
			log.Error().Err(err).Msg("failed to connected to queue server")

			select {
			case <-client.done:
				return
			case <-time.After(reconnectDelay):
			}
			continue
		}

		if done := client.handleReInit(conn); done {
			break
		}
	}
}

func (client *QueueClient) init(conn *amqp.Connection) error {
	ch, err := conn.Channel()
	if err != nil {
		return fmt.Errorf("error opening queue server channel: %w", err)
	}

	err = ch.Confirm(false)
	if err != nil {
		return fmt.Errorf("error setting channel to confirm mode: %w", err)
	}

	_, err = ch.QueueDeclare(
		client.queueName,
		true,
		false,
		false,
		false,
		nil,
	)
	if err != nil {
		return fmt.Errorf("error declaring queue: %w", err)
	}

	client.changeChannel(ch)
	client.m.Lock()
	client.isReady = true
	client.m.Unlock()

	log.Info().Msg("queue client initialized")

	return nil
}

func (client *QueueClient) changeChannel(channel *amqp.Channel) {
	client.channel = channel
	client.notifyChanClose = make(chan *amqp.Error, 1)
	client.notifyConfirm = make(chan amqp.Confirmation, 1)
	client.channel.NotifyClose(client.notifyChanClose)
	client.channel.NotifyPublish(client.notifyConfirm)
}

func (client *QueueClient) handleReInit(conn *amqp.Connection) bool {
	for {
		client.m.Lock()
		client.isReady = false
		client.m.Unlock()

		err := client.init(conn)
		if err != nil {
			log.Error().Err(err).Msg("failed to initialzie channel")

			select {
			case <-client.done:
				return true
			case <-client.notifyConnClose:
				log.Info().Msg("connection closed")
				return false
			case <-time.After(reInitDelay):
			}
			continue
		}

		select {
		case <-client.done:
			return true
		case <-client.notifyConnClose:
			log.Info().Msg("connection closed, reconnecting")
			return false
		case <-client.notifyChanClose:
			log.Info().Msg("channel closed, re-running initialization")
		}
	}
}
