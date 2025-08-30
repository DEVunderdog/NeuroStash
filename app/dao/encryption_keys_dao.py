from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.dao.schema import EncryptionKey
from datetime import datetime, timezone
from typing import List


async def get_active_encryption_key(*, db: AsyncSession) -> EncryptionKey | None:
    stmt = select(EncryptionKey).where(EncryptionKey.is_active.is_(True))
    result = await db.execute(stmt)
    key = result.scalars().first()
    return key


async def get_other_encryption_keys(*, db: AsyncSession) -> List[EncryptionKey]:
    now = datetime.now(timezone.utc)
    stmt = select(EncryptionKey).where(
        (EncryptionKey.expired_at.is_(None)) | (EncryptionKey.expired_at > now)
    )
    result = await db.execute(stmt)
    keys = result.scalars().all()
    return keys


async def create_encryption_key(*, db: AsyncSession, symmetric_key: bytes) -> int:
    new_key = EncryptionKey(symmetric_key=symmetric_key, is_active=True)
    db.add(new_key)
    try:
        await db.commit()
        await db.refresh(new_key)
        return new_key.id
    except Exception as e:
        await db.rollback()
        raise RuntimeError(f"failed to create encryption key: {e}") from e
