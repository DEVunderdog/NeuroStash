import logging

from fastapi import APIRouter, HTTPException, status

from app.api.deps import ApiPayloadDep, SessionDep, TokenDep
from app.dao.api_keys_dao import store_api_key
from app.dao.models import GeneratedApiKey, GeneratedToken, StoreApiKey
from app.token_svc.token_manager import KeyNotFoundError
from app.token_svc.token_models import TokenData

router = APIRouter(prefix="/auth/generate", tags=["Token"])

logger = logging.getLogger(__name__)


@router.get(
    "/token",
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
    except Exception:
        msg = "error generating token"
        logger.error(msg, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=msg
        )
    return GeneratedToken(message="generated token successfully", token=token)


@router.get(
    "/api-key",
    response_model=GeneratedApiKey,
    status_code=status.HTTP_201_CREATED,
    summary="generate multiple api keys for user",
)
def generate_user_api_keys(
    db: SessionDep, token_manager: TokenDep, payload: ApiPayloadDep
):
    try:
        new_api_key, new_api_key_bytes, new_api_key_signature, active_key_id = (
            token_manager.generate_api_key()
        )
    except KeyNotFoundError:
        logger.error(
            "cannot create api key, because signing key not found", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="error while creating api key",
        )
    except RuntimeError:
        msg = "cannot create api key"
        logger.error(msg, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=msg
        )

    try:
        store_api_key(
            db=db,
            api_key_params=StoreApiKey(
                user_id=payload.user_id,
                key_id=active_key_id,
                key_credential=new_api_key_bytes,
                key_signature=new_api_key_signature,
            ),
        )
    except Exception:
        msg = "error storing generated api key"
        logger.error(msg, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=msg
        )
    return GeneratedApiKey(
        message="successfully generated api key", api_key=new_api_key
    )
