from fastapi import FastAPI
from contextlib import asynccontextmanager
from sqlalchemy.orm import Session

from app.api.main import api_router
from app.core.config import settings
from app.aws.client import AwsClientManager
from app.core.db import SessionLocal
from app.token_svc.token_manager import TokenManager

import logging

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
        raise RuntimeError(msg) from e

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
        raise RuntimeError(msg) from e
    finally:
        db_session_for_token.close()
        logger.debug("database session just for token is closed")
    yield
    logger.info("application is shutting down")

app = FastAPI(
    title=settings.PROJECT_NAME,
    lifespan=lifespan,
)

app.include_router(api_router, prefix=settings.API_V1)
