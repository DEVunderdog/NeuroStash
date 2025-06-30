import logging
import asyncio
from app.aws.client import AwsClientManager
from app.core.config import Settings

logger = logging.getLogger(__name__)


class ConsumerManager:
    def __init__(self, aws_client_manager: AwsClientManager, settings: Settings):
        self.aws_client_manager = aws_client_manager
        self.settings = settings
        self.is_running = False
        self.consumer_task = None

    async def start(self):
        if self.is_running:
            logger.warning("manager already started the consumer")
            return

        self.is_running = True
        self.consumer_task = asyncio.create_task(self._consumer_loop())
        logger.info("manager is starting the consumer")

    async def _consumer_loop(self):
        while self.is_running:
            try:
                messages = self.aws_client_manager.receive_sqs_message()
                logger.info(
                    "successfully received the message", extra={"messages": messages}
                )
            except asyncio.CancelledError:
                logger.info("manager cancelled the consumer")
                break
            except Exception as e:
                logger.error(
                    "manager faced an exception while listening for messages on queue",
                    extra={"error": str(e)},
                    exc_info=True,
                )
                raise

    async def stop(self):
        if not self.is_running:
            logger.info("manager found none consumer running")
            return

        self.is_running = False
        if self.consumer_task:
            self.consumer_task.cancel()
            try:
                await self.consumer_task
            except asyncio.CancelledError:
                pass
        logger.info("manager stopped the consumer")
