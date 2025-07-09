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

        def task_done_callback(task: asyncio.Task):
            if task.cancelled():
                logger.info("consumer task was cancelled")
            elif task.exception():
                logger.error(
                    "consumer task failed with exception",
                    extra={"error": str(task.exception())},
                )
            else:
                logger.info("consumer task completed normally")

        self.consumer_task.add_done_callback(task_done_callback)

    async def _consumer_loop(self):
        while self.is_running:
            try:
                messages = await self._receive_message()
                logger.info(f"received: {len(messages)} messages from SQS")
                if messages:
                    for message in messages:
                        logger.info(f"message: {message}")

                        try:
                            await self._delete_message(message.receipt_handle)
                            logger.info(f"delete message: {message.message_id}")
                        except Exception as e:
                            logger.error(
                                "failed to delete message",
                                extra={"error": str(e)},
                                exc_info=True,
                            )
                            raise
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

    async def _receive_message(self):
        return await asyncio.to_thread(self.aws_client_manager.receive_sqs_message)

    async def _delete_message(self, receipt_handle: str):
        return await asyncio.to_thread(
            self.aws_client_manager.delete_message, receipt_handle
        )

    async def stop(self):
        if not self.is_running:
            logger.info("manager found none consumer running")
            return

        self.is_running = False
        if self.consumer_task and not self.consumer_task.done():
            self.consumer_task.cancel()
            try:
                await asyncio.wait_for(self.consumer_task, timeout=5.0)
            except asyncio.CancelledError:
                pass
        logger.info("manager stopped the consumer")
