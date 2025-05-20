from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime, timezone
from enum import Enum


class EncryptedKeyInfoArg(BaseModel):
    key_base64: str
    expired_at_iso: Optional[str] = None

    @property
    def key_bytes(self) -> bytes:
        import base64

        return base64.b64decode(self.key_base64)

    @property
    def expires_at(self) -> Optional[datetime]:
        if self.expired_at_iso:
            return datetime.fromisoformat(self.expired_at_iso.replace("Z", "+00:00"))
        return None


class Role(Enum):
    USER = 1
    ADMIN = 2


class JwtPayloadData(BaseModel):
    email: EmailStr
    user_id: int
    role: Role


class TokenData(JwtPayloadData):
    pass


class KeyInfo:
    def __init__(self, key: bytes, expires_at: Optional[datetime] = None):
        self.key = key
        self.expires_at = expires_at

    def is_expired(self) -> bool:
        if self.expires_at and datetime.now(timezone.utc) > self.expires_at:
            return True
        return False
