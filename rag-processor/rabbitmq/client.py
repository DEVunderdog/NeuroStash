import asyncio
from enum import Enum
from typing import Awaitable, Callable, Optional, Union

import aio_pika
import aio_pika.abc
from aio_pika.exceptions import ChannelClosed, ConnectionClosed
from log import logger

MessageProcessorCallback = Callable[
    [aio_pika.abc.AbstractIncomingMessage], Awaitable[None]
]


class ConsumerState(Enum):
    INACTIVE = 0
    ACTIVE = 1


class QueueClient:
    def __init__(
        self, url: str, consumer_queue_name: str, consumer_queue_prefetch: int
    ):
        self.queue_url = url
        self._connection: Optional[aio_pika.abc.AbstractRobustConnection] = None
        self._channel: Optional[aio_pika.abc.AbstractChannel] = None
        self._consumer_tag: Optional[str] = None
        self._consuming_queue: Optional[aio_pika.abc.AbstractQueue] = None
        self._consumer_queue_name = consumer_queue_name
        self._consumer_queue_prefetch = consumer_queue_prefetch
        self._consumer_state = ConsumerState.INACTIVE
        self._message_processor: Optional[MessageProcessorCallback] = None
        self._setup_lock = asyncio.Lock()

    def is_connected(self) -> bool:
        return (
            self._connection is not None
            and not self._connection.is_closed
            and self._channel is not None
            and not self._channel.is_closed
        )

    def _on_connection_close(self, exc: Optional[BaseException]) -> None:
        logger.warning("queue connection closed")
        if exc is not None:
            logger.warning(f"due to exception: {exc}")
        self._connection = None
        self._channel = None
        self._consumer_state = ConsumerState.INACTIVE

    def _on_channel_close(self, exc: Optional[BaseException]) -> None:
        logger.warning("queue channel closed")
        if exc is not None:
            logger.warning(f"due to exception: {exc}")
        if self._connection or self._connection.is_closed:
            self._channel = None
            self._consumer_state = ConsumerState.INACTIVE
            self._consumer_tag = None

    async def _re_setup_channel(self):
        if self._setup_lock.locked():
            logger.info("channel setup already in progress. Skipping...")
            return

        async with self._setup_lock:
            if not self._connection or self._connection.is_closed:
                logger.warning(
                    "connection lost before channel setup could start/complete."
                )
                return

            if self._channel and not self._channel.is_closed:
                try:
                    logger.info("channel already exists and is open. ensuring callback")
                    self._channel.close_callbacks.add(self._on_channel_close)
                    await self._restart_consumer_if_needed()
                    return
                except Exception as e:
                    logger.error(f"failed to restart the consumer: {e}", exc_info=True)
                    if self._channel and self._channel.is_closed:
                        self._channel = None
                    elif isinstance(e, (ChannelClosed, ConnectionClosed)):
                        self._channel = None

            try:
                logger.info("attempting to re-create channel after reconnect...")
                self._channel = await self._connection.channel()
                self._channel.close_callbacks.add(self._on_channel_close)
                logger.info("channel re-created successfully")

                await self._restart_consumer_if_needed()

            except Exception as e:
                logger.error(f"failed to re-create channel: {e}", exc_info=True)
                if self._channel and self._channel.is_closed:
                    self._channel = None
                elif isinstance(e, (ChannelClosed, ConnectionClosed)):
                    self._channel = None

    def _on_connection_reconnect(self) -> None:
        logger.info(
            "connection re-estabilished, re-creating channel and potentially resuming consumer..."
        )
        asyncio.create_task(self._re_setup_channel())

    async def stop_consumer(self) -> None:
        if (
            not (self._consumer_state == ConsumerState.ACTIVE)
            or not self._consumer_tag
            or not self._consuming_queue
        ):
            logger.info("consumer is not working")
            return
        try:
            if self._channel:
                if not self._channel.is_closed:
                    await self._consuming_queue.cancel(self._consumer_tag)
                    logger.info("consumer stopped successfully")
                else:
                    logger.warning("cannot cancel consumer because channel is closed")
            else:
                logger.warning("_channel state empty")
        except Exception as e:
            logger.error(f"error stoping consumer: {e}", exc_info=True)
        finally:
            self._consumer_state = ConsumerState.INACTIVE
            self._consumer_tag = None
            self._consuming_queue = None
            self._message_processor = None
            self._consumer_state = ConsumerState.INACTIVE

    async def close(self) -> None:
        logger.info("closing queue client...")
        if self._consumer_state == ConsumerState.ACTIVE:
            await self.stop_consumer()

        if self._channel:
            try:
                self._channel.close_callbacks.remove(self._on_channel_close)
            except (KeyError, ValueError):
                logger.debug("error removing close callbacks on channel")

        if self._connection:
            try:
                self._connection.close_callbacks.remove(self._on_connection_close)
                self._connection.reconnect_callbacks.remove(
                    self._on_connection_reconnect
                )
            except (KeyError, ValueError):
                logger.debug("error removing close callbacks and reconnect callbacks")

        if self._channel and not self._channel.is_closed:
            logger.info("closing channel...")
            try:
                await self._channel.close()
                logger.info("channel closed.")
            except Exception as e:
                logger.error(f"error closing channel; {e}", exc_info=True)
        self._channel = None
        if self._connection and not self._connection.is_closed:
            logger.info("closing connection...")
            try:
                await self._connection.close()
                logger.info("connection closed")
            except Exception as e:
                logger.error(f"error closing connection: {e}", exc_info=True)
        self._connection = None
        self._consumer_state = ConsumerState.INACTIVE
        self._consumer_tag = None
        self._consuming_queue = None
        self._consumer_queue_name = None
        self._consumer_queue_prefetch = None
        self._message_processor = None
        logger.info("queue client closed")

    async def connect(self) -> None:
        if self.is_connected():
            logger.info("already connected")
            return
        try:
            logger.info(f"connecting to queue at {self.queue_url}")
            self._connection = await aio_pika.connect_robust(self.queue_url)
            self._connection.close_callbacks.add(self._on_connection_close)
            self._connection.reconnect_callbacks.add(self._on_connection_reconnect)
            logger.info("connection successful")


            self._channel = await self._connection.channel()
            self._channel.close_callbacks.add(self._on_channel_close)
        except (
            ConnectionError,
            asyncio.TimeoutError,
            aio_pika.exceptions.AMQPConnectionError,
        ) as e:
            logger.error(f"failed to connect to queue: {e}", exc_info=True)
            await self.close()
            raise

    async def publish_message(
        self,
        queue_name: str,
        message_body: Union[bytes, str],
        content_type: str = "text/plain",
        delivery_mode: aio_pika.DeliveryMode = aio_pika.DeliveryMode.PERSISTENT,
    ) -> None:
        if not self.is_connected():
            raise RuntimeError("client not connected. call connect() first.")
        if not self._channel:
            raise RuntimeError("channel is not available")

        try:
            await self._channel.declare_queue(queue_name, durable=True)
            logger.debug(f"queue '{queue_name}' ensured")
            body_bytes = (
                message_body.encode("utf-8")
                if isinstance(message_body, str)
                else message_body
            )
            message = aio_pika.Message(
                body=body_bytes,
                content_type=content_type,
                delivery_mode=delivery_mode,
            )
            logger.debug(f"publishing message to queue '{queue_name}'...")
            await self._channel.default_exchange.publish(
                message=message, routing_key=queue_name
            )
            logger.info(f"message published to queue '{queue_name}' successfully")
        except (ChannelClosed, ConnectionClosed) as e:
            logger.error(f"connection/channel closed during publish: {e}")
            raise
        except Exception as e:
            logger.error(
                f"failed to publish message to queue '{queue_name}': {e}", exc_info=True
            )
            raise

    async def _process_message_wrapper(
        self, message: aio_pika.abc.AbstractIncomingMessage
    ) -> None:
        if not self._message_processor:
            logger.warning(
                "no message processor set, message ignored and rejected (nack)."
            )
            try:
                await message.nack(requeue=False)
            except Exception as e:
                logger.error(
                    f"error NACKing message when no processor is set: {e}",
                    exc_info=True,
                )
            return

        async with message.process(requeue=False):
            try:
                logger.debug(
                    f"processing message {message.message_id or 'N/A'} from queue '{message.routing_key}'"
                )
                await self._message_processor(message)
                logger.debug(
                    f"finished processing message {message.message_id or 'N/A'}"
                )
            except Exception as e:
                logger.error(f"error processing message exception: {e}", exc_info=True)
                raise

    async def start_consumer(
        self,
        message_processor: MessageProcessorCallback,
    ):
        if not self.is_connected():
            raise RuntimeError("client not connected, connect the client")
        if not self._channel:
            raise RuntimeError("channel is not available")
        if self._consumer_state == ConsumerState.ACTIVE:
            logger.warning(
                f"already consuming from queue '{self._consuming_queue.name}'."
            )
            return

        self._message_processor = message_processor

        try:
            logger.info(
                f"setting consumer QoS prefetch count to {self._consumer_queue_prefetch}"
            )
            await self._channel.set_qos(prefetch_count=self._consumer_queue_prefetch)

            logger.info(f"accessing queue '{self._consumer_queue_prefetch}'...")

            self._consuming_queue = await self._channel.declare_queue(
                self._consumer_queue_name, durable=True
            )
            logger.info(f"queue '{self._consumer_queue_name}' declared/accessed")

            logger.info(
                f"starting consumption on queue '{self._consumer_queue_name}'..."
            )
            self._consumer_tag = await self._consuming_queue.consume(
                self._process_message_wrapper
            )
            self._consumer_state = ConsumerState.ACTIVE
            logger.info(f"consumption started with consumer tag: {self._consumer_tag}")

        except (ChannelClosed, ConnectionClosed) as e:
            logger.error(f"Connection/Channel closed during consumer setup: {e}")
            self._consumer_state = ConsumerState.INACTIVE
            self._consumer_tag = None
            self._consuming_queue = None
            raise

        except Exception as e:
            logger.error(
                f"Failed to start consumer on queue '{self._consumer_queue_name}': {e}",
                exc_info=True,
            )
            self._consumer_state = ConsumerState.INACTIVE
            self._consumer_tag = None
            self._consuming_queue = None
            raise

    async def _restart_consumer_if_needed(self):
        if (
            not (self._consumer_state == ConsumerState.ACTIVE)
            and self._message_processor
            and self._consumer_queue_name is not None
            and self._consumer_queue_prefetch is not None
        ):
            logger.info(
                f"attempting to restart consumer for queue '{self._consumer_queue_name}'..."
            )
            if not self._channel or self._channel.is_closed:
                logger.warning("cannot restart consumer, channel is not available.")
                return

            self._consumer_tag = None
            self._consuming_queue = None
            self._consumer_state = ConsumerState.INACTIVE

            try:
                await self._channel.set_qos(
                    prefetch_count=self._consumer_queue_prefetch
                )
                self._consuming_queue = await self._channel.declare_queue(
                    self._consumer_queue_name, durable=True
                )
                self._consumer_tag = await self._consuming_queue.consume(
                    self._process_message_wrapper
                )
                self._consumer_state = ConsumerState.ACTIVE
                logger.info(
                    f"consumer restarted successfully with tag: {self._consumer_tag}"
                )
            except (ChannelClosed, ConnectionClosed) as e:
                logger.error(f"connection/channel closed during consumer restart: {e}")
                self._consumer_state = ConsumerState.INACTIVE
                self._consumer_tag = None
                self._consuming_queue = None
            except Exception as e:
                logger.error(f"failed to restart the consumer: {e}", exc_info=True)
                self._consumer_state = ConsumerState.INACTIVE
                self._consumer_tag = None
                self._consuming_queue = None
        else:
            logger.debug(
                "no consumer restart needed (was neither consuming nor any state available)"
            )

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
