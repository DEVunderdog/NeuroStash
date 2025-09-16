from fastapi import FastAPI
from contextlib import asynccontextmanager
from fastapi.exceptions import RequestValidationError
import asyncio

from app.api.main import api_router
from app.core.config import settings
from app.aws.client import AwsClientManager
from app.token_svc.token_manager import TokenManager
from app.consumer.consumer_manager import ConsumerManager
from app.provisioner.manager import ProvisionManager
from app.file_cleaner.cleaner import FileCleaner
from app.milvus.client import MilvusOps
from app.utils.scheduler import scheduler
from app.core.exceptions import request_validation_exception_handler
from app.milvus.searching import SearchOps

import logging
import sys

log_level_str = "DEBUG"
numeric_log_level = getattr(logging, log_level_str, logging.INFO)

logging.basicConfig(
    level=numeric_log_level,
    stream=sys.stdout,
    format="%(levelname)-8s [%(asctime)s] [%(name)s] %(message)s (%(filename)s:%(lineno)d)",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logging.getLogger("sqlalchemy.dialects").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.orm").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

logging.getLogger("botocore").setLevel(logging.WARNING)
logging.getLogger("boto3").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("s3transfer").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


def create_robust_task(coro, task_name: str):
    async def task_wrapper():
        try:
            await coro
        except asyncio.CancelledError:
            logger.info(f"Task '{task_name}' was cancelled.")
        except Exception:
            logger.critical(
                f"Critical unhandled exception in background task '{task_name}'",
                exc_info=True,
            )

    return asyncio.create_task(task_wrapper(), name=task_name)


async def schedule_cleanup_job(
    provision_manager: ProvisionManager, file_cleaner: FileCleaner
):
    logger.info("scheduler starting 'cleanup_collections' job")
    try:
        await provision_manager.cleanup_collections()
        await file_cleaner.file_cleanup_worker()
        await file_cleaner.ingestion_job_cleaner()
        logger.info(
            "scheduler finished 'cleanup_collections and files' job successfully."
        )
    except Exception as e:
        logger.error(
            f"scheduled 'cleanup_collections' and 'files cleanup' job failed: {e}",
            exc_info=True,
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("application startup: initializing resources...")

    app.state.aws_client_manager = AwsClientManager(settings=settings)
    app.state.milvus_ops = MilvusOps(settings=settings)

    app.state.milvus_ops.ensure_database(name=settings.MILVUS_DATABASE)

    provision_manager = ProvisionManager(
        settings=settings, milvusOps=app.state.milvus_ops
    )

    search_ops = SearchOps(settings=settings)

    app.state.search_ops = search_ops

    app.state.provision_manager = provision_manager

    file_cleaner = FileCleaner(aws_client=app.state.aws_client_manager)

    reconcilation_task = create_robust_task(
        provision_manager.reconcilation_worker(), "reconciliation_worker"
    )
    cleanup_task = create_robust_task(
        provision_manager.cleanup_worker(), "cleanup_worker"
    )

    scheduler.add_job(
        schedule_cleanup_job,
        "cron",
        hour=8,
        minute=3,
        name="daily_collection_cleanup",
        args=[provision_manager, file_cleaner],
    )
    scheduler.start()

    app.state.token_manager = await TokenManager.create(
        aws_client_manager=app.state.aws_client_manager,
        settings=settings,
    )

    app.state.consumer_manager = ConsumerManager(
        aws_client_manager=app.state.aws_client_manager,
        settings=settings,
        milvus_ops=app.state.milvus_ops,
    )

    await app.state.consumer_manager.start()

    yield

    logger.info("application is shutting down")

    if hasattr(app.state, "consumer_manager"):
        await app.state.consumer_manager.stop()

    if scheduler.running:
        scheduler.shutdown()

    reconcilation_task.cancel()
    cleanup_task.cancel()

    try:
        await reconcilation_task
        await cleanup_task
    except asyncio.CancelledError:
        logger.info(
            "Reconciliation worker task and cleanup task has been cancelled and stopped."
        )


app = FastAPI(
    title=settings.PROJECT_NAME,
    lifespan=lifespan,
)

app.add_exception_handler(RequestValidationError, request_validation_exception_handler)

app.include_router(api_router, prefix=settings.API_V1)
