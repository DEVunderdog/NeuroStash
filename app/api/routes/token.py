from fastapi import APIRouter, status, HTTPException
from app.dao.models import GeneratedToken
from app.api.deps import TokenDep, ApiPayloadDep
from app.token_svc.token_models import TokenData

import logging

router = APIRouter(prefix="/token", tags=["Token"])

logger = logging.getLogger(__name__)


@router.get(
    "/generate",
    response_model=GeneratedToken,
    status_code=status.HTTP_201_CREATED,
    summary="generate a jwt token",
)
def generate_token(token_manager: TokenDep, payload: ApiPayloadDep):
    try:
        data = TokenData(
            email=payload.email, user_id=payload.user_id, role=payload.role
        )
        token = token_manager.create_access_token(payload_data=data)
    except Exception as e:
        msg = "error generating token"
        logger.error(msg, exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=msg
        )
    return GeneratedToken(message="generated token successfully", token=token)
