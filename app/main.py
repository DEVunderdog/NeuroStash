from fastapi import FastAPI
from contextlib import asynccontextmanager
from sqlalchemy.orm import Session
from fastapi.exceptions import RequestValidationError

from app.api.main import api_router
from app.core.config import settings
from app.aws.client import AwsClientManager
from app.core.db import SessionLocal
from app.token_svc.token_manager import TokenManager
from app.consumer.consumer_manager import ConsumerManager
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("application startup: initializing resources...")

    try:
        aws_client_manager = AwsClientManager(settings=settings)
        app.state.aws_client_manager = aws_client_manager
        logger.debug("aws client inititalized")
    except Exception as e:
        msg = f"failed to initialized aws client: {e}"
        logger.error(msg)
        raise

    db_session_for_token: Session = SessionLocal()
    try:
        token_manager = TokenManager(
            initial_db_session=db_session_for_token,
            aws_client_manager=app.state.aws_client_manager,
        )
        app.state.token_manager = token_manager
        logger.debug("token manager intialized")
    except Exception as e:
        msg = f"failed to initialize token: {e}"
        logger.error(msg)
        raise
    finally:
        db_session_for_token.close()
        logger.debug("database session just for token is closed")

    try:
        consumer_manager = ConsumerManager(
            aws_client_manager=app.state.aws_client_manager, settings=settings
        )
        app.state.consumer_manager = consumer_manager
        await consumer_manager.start()
    except Exception as e:
        msg = f"failed to initialized consumer manager: {str(e)}"
        logger.error(msg)
        raise
    yield
    logger.info("application is shutting down")
    if hasattr(app.state, "consumer_manager"):
        await app.state.consumer_manager.stop()


app = FastAPI(
    title=settings.PROJECT_NAME,
    lifespan=lifespan,
)

app.add_exception_handler(RequestValidationError, request_validation_exception_handler)

app.include_router(api_router, prefix=settings.API_V1)
