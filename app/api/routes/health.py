from fastapi import APIRouter
from app.dao.models import StandardResponse
from typing import Any

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/", response_model=StandardResponse)
def server_health_check() -> Any:
    return StandardResponse(message="server healthy, up and running")
