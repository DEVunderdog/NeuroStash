from pydantic import BaseModel, EmailStr
from app.dao.schema import ClientRoleEnum


class StandardResponse(BaseModel):
    status: int
    message: str


class UserClientBase(BaseModel):
    email: EmailStr
    role: ClientRoleEnum


class UserClientCreate(UserClientBase):
    pass


class ApiKeyCreate(BaseModel):
    key_id: int
    key_credential: bytes
    key_signature: bytes
