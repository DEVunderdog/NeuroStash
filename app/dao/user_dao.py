from sqlalchemy.ext.asyncio import AsyncSession
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


async def register_user(
    *, db: AsyncSession, user: UserClientCreate, api_key_params: ApiKeyCreate
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
        await db.commit()
        await db.refresh(user_client)
        await db.refresh(api_key)
        return user_client, api_key
    except IntegrityError as e:
        await db.rollback()
        if isinstance(e.orig, psycopg.errors.UniqueViolation):
            raise UserAlreadyExistsError(email=user.email) from e
    except Exception as e:
        await db.rollback()
        raise RuntimeError(f"failed to register user due to an unexpected error: {e}")


async def get_user_db(*, db: AsyncSession, email: EmailStr) -> UserClient | None:
    stmt = select(UserClient).where(UserClient.email == email)
    result = await db.execute(stmt)
    return result.scalars().first()


async def list_users_db(
    *, db: AsyncSession, limit: int = 10, offset: int = 0
) -> List[UserClient]:
    stmt = select(UserClient).order_by(UserClient.id).limit(limit).offset(offset)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def promote_user_db(*, db: AsyncSession, user_id: int) -> UserClient | None:
    stmt = select(UserClient).where(UserClient.id == user_id)
    result = await db.execute(stmt)
    user_client = result.scalars().first()

    if user_client:
        if user_client.role == ClientRoleEnum.ADMIN:
            return user_client

        user_client.role = ClientRoleEnum.ADMIN
        try:
            await db.commit()
            return user_client
        except Exception:
            await db.rollback()
            raise
    else:
        return None


async def delete_user_db(*, db: AsyncSession, user_id: int) -> bool:
    stmt = select(UserClient).where(UserClient.id == user_id)
    result = await db.execute(stmt)
    user_client = result.scalars().first()

    if user_client:
        await db.delete(user_client)
        try:
            await db.commit()
            return True
        except Exception:
            await db.rollback()
            raise
    else:
        return False
