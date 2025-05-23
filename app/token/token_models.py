from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime, timezone
from enum import Enum

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
