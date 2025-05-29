from collections.abc import Generator
from typing import Annotated, Optional
from sqlalchemy.orm import Session
from app.core.db import SessionLocal
from fastapi import Depends, Request, HTTPException, status, Header, Request
from fastapi.security import OAuth2PasswordBearer
from app.aws.client import AwsClientManager
from app.token.token_manager import TokenManager, KeyNotFoundError
from app.core.config import settings
from app.token.token_models import TokenData, ApiData
from jose import JWTError, ExpiredSignatureError
from app.dao.api_keys_dao import get_api_key_for_verification

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1}/auth/generate/token", auto_error=False
)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_aws_client_manager(request: Request) -> AwsClientManager:
    if not hasattr(request.app.state, "aws_client_manager"):
        raise RuntimeError("AwsClientManager not initialized. Check lifespan events")
    return request.app.state.aws_client_manager


def get_token_manager(request: Request) -> TokenManager:
    if not hasattr(request.app.state, "token_manager"):
        raise RuntimeError("TokenManager not initialized. Check lifespan events.")
    return request.app.state.token_manager


SessionDep = Annotated[Session, Depends(get_db)]
TokenDep = Annotated[TokenManager, Depends[get_token_manager]]
AwsDep = Annotated[AwsClientManager, Depends[get_aws_client_manager]]


async def get_token_payload(
    token: Annotated[Optional[str], Depends[oauth2_scheme]],
    token_manager: TokenDep,
) -> TokenData:
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="not authenticated: missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = token_manager.verify_token(token=token)
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token payload"
            )
        return payload
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="token has expired",
            headers={
                "WWW-Authenticate": 'Bearer error="invalid_token", error_description="the token has expired"'
            },
        )
    except KeyNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"token verification key error: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"could not validate credentials: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Token verification internal error: {e}",
        )


async def get_api_payload(
    authorization: Annotated[Optional[str], Header()] = None,
    db: SessionDep = Depends(),
    token_manager: TokenDep = Depends(),
) -> ApiData:
    if authorization is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="not authenticated: missing authorization header for api key",
        )

    auth_parts = authorization.split(" ", 1)
    if len(auth_parts) != 2 or auth_parts[0].lower() != "apikey":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid api key authentication scheme. Expected 'ApiKey <key>'",
        )
    api_key_full_string = auth_parts[1]

    verified_api_key = get_api_key_for_verification(db=db, api_key=api_key_full_string)
    if not verified_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="api key not found"
        )

    try:
        is_valid = token_manager.verify_api_key(
            api_key=api_key_full_string,
            key_hmac=verified_api_key.key_credential,
            kid=verified_api_key.key_id,
        )
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="api key verification failed: signature mismatched",
            )
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"api key verification error: {e}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"api key verification internal error: {e}",
        )

    return ApiData(
        email=verified_api_key.user_email,
        user_id=verified_api_key.user_id,
        role=verified_api_key.user_role,
    )
