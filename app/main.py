from fastapi import FastAPI
from contextlib import asynccontextmanager
from sqlalchemy.orm import Session
from fastapi.exceptions import RequestValidationError
import asyncio

from app.api.main import api_router
from app.core.config import settings
from app.aws.client import AwsClientManager
from app.core.db import SessionLocal
from app.token_svc.token_manager import TokenManager
from app.consumer.consumer_manager import ConsumerManager
from app.provisioner.manager import ProvisionManager
from app.milvus.client import MilvusOps
from app.utils.scheduler import scheduler
from app.core.exceptions import request_validation_exception_handler

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
logging.getLogger("sqlalchemy.dialects").setLevel(logging.INFO)
logging.getLogger("sqlalchemy.pool").setLevel(logging.INFO)
logging.getLogger("sqlalchemy.orm").setLevel(logging.INFO)
logging.getLogger("sqlalchemy.engine").setLevel(logging.DEBUG)

logger = logging.getLogger(__name__)

async def schedule_cleanup_job(provision_manager: ProvisionManager):
    logger.info("scheduler starting 'cleanup_collections' job")
    try:
        await provision_manager.cleanup_collections()
        logger.info("scheduler finished 'cleanup_collections' job successfully.")
    except Exception as e:
        logger.error(f"scheduled 'cleanup_collections' job failed: {e}", exc_info=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("application startup: initializing resources...")

    app.state.aws_client_manager = AwsClientManager(settings=settings)
    app.state.milvus_ops = MilvusOps(settings=settings)
    db_session: Session = SessionLocal()

    provision_manager = ProvisionManager(
        session=db_session, settings=settings, milvusOps=app.state.milvus_ops
    )

    app.state.provision_manager = provision_manager

    reconcilation_task = asyncio.create_task(provision_manager.reconcilation_worker())
    cleanup_task = asyncio.create_task(provision_manager.cleanup_worker())

    scheduler.add_job(
        schedule_cleanup_job,
        "cron",
        hour=2,
        minute=0,
        name="daily_collection_cleanup",
        args=[provision_manager],
    )
    scheduler.start()

    app.state.token_manager = TokenManager(
        initial_db_session=db_session,
        aws_client_manager=app.state.aws_client_manager,
    )

    app.consumer_manager = ConsumerManager(
        aws_client_manager=app.state.aws_client_manager,
        settings=settings,
        db=db_session,
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

    db_session.close()


app = FastAPI(
    title=settings.PROJECT_NAME,
    lifespan=lifespan,
)

app.add_exception_handler(RequestValidationError, request_validation_exception_handler)

app.include_router(api_router, prefix=settings.API_V1)
