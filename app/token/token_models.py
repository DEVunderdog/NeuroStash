from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime, timezone
from app.dao.schema import ClientRoleEnum


class PayloadData(BaseModel):
    email: EmailStr
    user_id: int
    role: ClientRoleEnum


class TokenData(PayloadData):
    pass


class ApiData(PayloadData):
    pass


class KeyInfo:
    def __init__(self, key: bytes, expires_at: Optional[datetime] = None):
        self.key = key
        self.expires_at = expires_at

    def is_expired(self) -> bool:
        if self.expires_at and datetime.now(timezone.utc) > self.expires_at:
            return True
        return False
