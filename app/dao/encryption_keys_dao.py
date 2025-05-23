from sqlalchemy.orm import Session
from app.dao.schema import EncryptionKey
from datetime import datetime
from typing import List


def get_active_encryption_key(db: Session) -> EncryptionKey:
    return db.query(EncryptionKey).filter(EncryptionKey.is_active.is_(True)).first()


def get_other_encryption_keys(db: Session) -> List[EncryptionKey]:
    now = datetime.now()
    return (
        db.query(EncryptionKey)
        .filter((EncryptionKey.expired_at is None) | (EncryptionKey.expired_at > now))
        .all()
    )

def create_encryption_key(db: Session, symmetric_key: bytes) -> int:
    new_key = EncryptionKey(symmetric_key=symmetric_key, is_active=True)
    db.add(new_key)
    db.flush()
    inserted_id = new_key.id
    db.commit()
    return inserted_id

