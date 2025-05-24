from sqlalchemy.orm import Session
from sqlalchemy import select
from app.dao.schema import UserClient, ApiKey
from app.dao.models import UserClientCreate, ApiKeyCreate
from pydantic import EmailStr
from typing import Tuple
import logging

logger = logging.getLogger(__name__)

def register_user(
    *, db: Session, user: UserClientCreate, api_key_params: ApiKeyCreate
) -> Tuple[UserClient, ApiKey]:
    try:
        user_client = UserClient(**user.model_dump())
        db.add(user_client)
        api_key = ApiKey(
            user_client=user_client,
            key_id=api_key_params.key_id,
            key_credential=api_key_params.key_credential,
            key_signature=api_key_params.key_signature,
        )
        db.add(api_key)
        db.commit()
        db.refresh(user_client)
        db.refresh(api_key)
        return user_client, api_key
    except Exception as e:
        db.rollback()
        raise RuntimeError(f"failed to register user: {e}") from e


def get_user(*, db: Session, email: EmailStr) -> UserClient | None:
    stmt = select(UserClient).where(UserClient.email == email)
    user = db.scalars(stmt).first()
    return user
