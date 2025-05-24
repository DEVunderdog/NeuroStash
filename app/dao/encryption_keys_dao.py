from sqlalchemy.orm import Session
from sqlalchemy import select
from app.dao.schema import EncryptionKey
from datetime import datetime, timezone
from typing import List


def get_active_encryption_key(db: Session) -> EncryptionKey | None:
    stmt = select(EncryptionKey).where(EncryptionKey.is_active.is_(True))
    key = db.scalars(stmt).first()
    return key


def get_other_encryption_keys(db: Session) -> List[EncryptionKey]:
    now = datetime.now(timezone.utc)
    stmt = select(EncryptionKey).where(
        (EncryptionKey.expired_at.is_(None)) | (EncryptionKey.expired_at > now)
    )
    keys = db.scalars(stmt).all()
    return keys


def create_encryption_key(db: Session, symmetric_key: bytes) -> int:
    new_key = EncryptionKey(symmetric_key=symmetric_key, is_active=True)
    db.add(new_key)
    try:
        db.commit()
        db.refresh(new_key)
        return new_key.id
    except Exception as e:
        db.rollback()
        raise RuntimeError(f"failed to create encryption key: {e}") from e
