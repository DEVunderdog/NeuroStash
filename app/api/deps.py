from collections.abc import Generator
from typing import Annotated
from sqlalchemy.orm import Session
from app.core.db import SessionLocal
from fastapi import Depends, Request
from app.aws.client import AwsClientManager
from app.token.token_manager import TokenManager


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_aws_client_manager(request: Request) -> AwsClientManager:
    if not hasattr(request.app.state, "aws_client_manager"):
        raise RuntimeError("AwsClientManager not initialized. Check lifespan events")
    return request.app.state.aws_client_manager


def get_token_manager(request: Request) -> TokenManager:
    if not hasattr(request.app.state, "token_manager"):
        raise RuntimeError("TokenManager not initialized. Check lifespan events.")
    return request.app.state.token_manager


SessionDep = Annotated[Session, Depends(get_db)]
TokenDep = Annotated[TokenManager, Depends[get_token_manager]]
AwsDep = Annotated[AwsClientManager, Depends[get_aws_client_manager]]
