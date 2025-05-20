from pydantic import BaseModel
from typing import Any, Optional


class StandardResponse(BaseModel):
    status: int
    message: str


