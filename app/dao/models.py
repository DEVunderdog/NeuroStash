from pydantic import BaseModel, EmailStr, ConfigDict
from app.dao.schema import ClientRoleEnum
from typing import List


class StandardResponse(BaseModel):
    message: str


class GeneratedToken(StandardResponse):
    token: str


class UserClientBase(BaseModel):
    email: EmailStr
    role: ClientRoleEnum


class UserClientCreate(UserClientBase):
    pass


class RegisterUser(BaseModel):
    email: EmailStr


class UserClientCreated(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    api_key: str


class ApiKeyCreate(BaseModel):
    key_id: int
    key_credential: bytes
    key_signature: bytes


class StoreApiKey(ApiKeyCreate):
    user_id: int


class VerifiedApiKey(BaseModel):
    id: int
    user_id: int
    user_email: str
    user_role: ClientRoleEnum
    key_id: int
    key_credential: bytes
    key_signature: bytes


class IndividualListedUser(BaseModel):
    id: int
    email: str


class ListUsers(BaseModel):
    users: List[IndividualListedUser]
