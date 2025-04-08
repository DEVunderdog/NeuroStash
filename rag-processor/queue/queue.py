import pika
import time
import ssl
import msgpack
from pika.exceptions import AMQPConnectionError
from log import logger


class QueueClient:
    def __init__(self, username, password, host, port, protocol: str):
        self.username = username
        self.password = password
        self.host = host
        self.port = port
        self.protocol = protocol

        # Good practice so if someone inherits this class knows they can reimplement those function
        self._init_connection_parameters()
        self._connect()

    def _connect(self):
        tries = 0
        while True:
            try:
                self.connection = pika.BlockingConnection(self.parameters)
                self.channel = self.connection.channel()
                if self.connection.is_open:
                    break
            except (AMQPConnectionError, Exception) as e:
                time.sleep(5)
                tries += 1
                if tries == 5:
                    raise AMQPConnectionError(e)

    def _init_connection_parameters(self):
        self.credentials = pika.PlainCredentials(self.username, self.password)
        self.parameters = pika.ConnectionParameters(
            self.host, int(self.port), "/", self.credentials
        )
        if self.protocol == "amqps":
            ssl_context = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
            ssl_context.set_ciphers("ECDHE+AESGCM:!ECDSA")
            self.parameters.ssl_options = pika.SSLOptions(context=ssl_context)

    def check_connection(self):
        if not self.connection or self.connection.is_closed:
            self._connect()

    def close(self):
        self.channel.close()
        self.connection.close()


class BasicMessageReceiver(QueueClient):
    def __init__(self):
        super().__init__()
        self.channel_tag = None

    def decode_message(self, body):
        if type(body) is bytes:
            return msgpack.unpackb(body)
        else:
            raise NotImplementedError

    def get_message(self, queue_name: str, auto_ack: bool = False):
        method_frame, header_frame, body = self.channel.basic_get(
            queue=queue_name,
            auto_ack=auto_ack
        )
        if method_frame:
            logger.debug(f"{method_frame}, {header_frame}, {body}")
            return method_frame, header_frame, body
        else:
            logger.debug("no message returned")
            return None
    
    def consume_message(self, queue, callback):
        self.check_connection()
        self.channel_tag = self.channel.basic_consume(
            queue=queue,
            on_message_callback=callback,
            auto_ack=False
        )
        logger.debug("Waiting for messages...")
        self.channel.start_consuming()

    def cancel_consumer(self):
        if self.channel_tag is not None:
            self.channel.basic_cancel(self.channel_tag)
            self.channel_tag = None
        else:
            logger.error("do not cancel a non-existing job")