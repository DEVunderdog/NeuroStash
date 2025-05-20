from fastapi import APIRouter, HTTPException
from app.models import StandardResponse
from typing import Any

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/", response_model=StandardResponse)
def server_health_check() -> Any:
    return StandardResponse(status=200, message="server healthy, up and running")
