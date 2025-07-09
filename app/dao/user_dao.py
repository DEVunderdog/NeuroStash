from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.dao.schema import UserClient, ApiKey, ClientRoleEnum
from app.dao.models import UserClientCreate, ApiKeyCreate
from pydantic import EmailStr
from typing import List
import psycopg

from typing import Tuple
import logging

logger = logging.getLogger(__name__)


class UserAlreadyExistsError(Exception):
    def __init__(self, email: str):
        self.email = email
        super().__init__(f"user with email '{email}' already exists")


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
    except IntegrityError as e:
        db.rollback()
        if isinstance(e.orig, psycopg.errors.UniqueViolation):
            raise UserAlreadyExistsError(email=user.email) from e
    except Exception as e:
        db.rollback()
        raise RuntimeError(f"failed to register user due to an unexpected error: {e}")


def get_user_db(*, db: Session, email: EmailStr) -> UserClient | None:
    stmt = select(UserClient).where(UserClient.email == email)
    user = db.scalars(stmt).first()
    return user


def list_users_db(*, db: Session, limit: int = 10, offset: int = 0) -> List[UserClient]:
    stmt = select(UserClient).order_by(UserClient.id).limit(limit).offset(offset)
    users = db.scalars(stmt).all()
    return users


def promote_user_db(*, db: Session, user_id: int) -> UserClient | None:
    stmt = select(UserClient).where(UserClient.id == user_id)
    user_client = db.scalars(stmt).first()

    if user_client:
        if user_client.role == ClientRoleEnum.ADMIN:
            return user_client

        user_client.role = ClientRoleEnum.ADMIN
        try:
            db.commit()
            return user_client
        except Exception:
            db.rollback()
            raise
    else:
        return None


def delete_user_db(*, db: Session, user_id: int) -> bool:
    stmt = select(UserClient).where(UserClient.id == user_id)
    user_client = db.scalars(stmt).first()

    if user_client:
        db.delete(user_client)
        try:
            db.commit()
            return True
        except Exception:
            db.rollback()
            raise
    else:
        return False
