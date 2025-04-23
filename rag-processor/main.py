import asyncio
import signal
import yaml
from config.settings import Settings, AppSettings
from pathlib import Path
from log import logger
from pydantic import ValidationError
from rabbitmq import QueueClient
from service.processor import Processor


class RagProcessor:
    def __init__(self, config_path: Path):
        try:
            self._settings_loader = Settings(config_path=config_path)
            self.settings: AppSettings = self._settings_loader.get_settings()
            logger.info("configuration loaded successfully")
        except (FileNotFoundError, yaml.YAMLError, ValidationError, ValueError) as e:
            logger.exception(f"failed to loading configuration from settings: {e}")
            raise RuntimeError(
                "application failed to start due to configuration error."
            ) from e

        self.queue_client = QueueClient(
            url=self.settings.queue.queue_url,
            consumer_queue_name=self.settings.queue.queue_name,
            consumer_queue_prefetch=self.settings.queue.queue_prefetch_count,
        )

        self.processor = Processor(
            aws_region=self.settings.aws_cloud.region_name,
            bucket_name=self.settings.aws_cloud.bucket_name,
            download_temp_dir=self.settings.temp_path,
            temp_dir=self.settings.temp_path,
        )
        self._shutdown_event = asyncio.Event()

    async def start(self):
        logger.info("staring rag-processor...")
        try:
            await self.queue_client.connect()
            await self.queue_client.start_consumer(
                self.processor.process_download_message
            )
            logger.info("queue consumer started successfully")
        except Exception as e:
            logger.error(f"error during startup: {e}", exc_info=True)
            await self.stop()
            raise

    async def stop(self):
        logger.info("stopping rag-processor...")
        await self.queue_client.stop_consumer()
        await self.queue_client.close()
        logger.info("stopped rag-processor")

    def _signal_handler(self, sig):
        logger.info(f"received signal {sig.name}, initializing shutdown procedure...")
        self._shutdown_event.set()

    async def run(self):
        loop = asyncio.get_running_loop()

        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, self._signal_handler, sig)
                logger.debug(f"registered signal handler for {sig.name}")
            except ValueError as e:
                logger.warning(f"could not register signal handler for {sig.name}: {e}")

        try:
            await self.start()
            logger.info("application started successfully")
            await self._shutdown_event.wait()

        except asyncio.CancelledError:
            logger.info("main run task cancelled")
        except Exception as e:
            logger.error(f"an unexpected error ocurred in the main run loop: {e}")
        finally:
            logger.info("shutdown initiated, cleaning up")

            for sig in (signal.SIGINT, signal.SIGTERM):
                try:
                    loop.remove_signal_handler(sig=sig)
                    logger.debug(f"removed signal handler for {sig.name}")
                except (ValueError, RuntimeError) as e:
                    logger.debug(f"could not remove signal for {sig.name}: {e}")

            await self.stop()
            logger.info("application shutdown completely")


if __name__ == "__main__":
    config_file_path = Path("./app.yaml")

    if not config_file_path.is_file():
        logger.error(f"configuration file not found at: {config_file_path}")
        exit(1)

    app = RagProcessor(config_path=config_file_path)

    try:
        asyncio.run(app.run())
    except RuntimeError as e:
        logger.critical(f"application failed to start: {e}")
        exit(1)
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received, shutting down...")
    except Exception as e:
        logger.critical(
            f"unhandled exception during application execution: {e}", exc_info=True
        )
        exit(1)
