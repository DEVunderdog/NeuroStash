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

