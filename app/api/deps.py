from typing import Annotated, Optional, AsyncGenerator
from app.core.db import SessionLocal
from fastapi import Depends, Request, HTTPException, status, Header
from fastapi.security import HTTPBearer, APIKeyHeader
from app.aws.client import AwsClientManager
from app.token_svc.token_manager import TokenManager, KeyNotFoundError
from app.token_svc.token_models import TokenData, ApiData
from jose import JWTError, ExpiredSignatureError
from app.provisioner.manager import ProvisionManager
from app.dao.api_keys_dao import get_api_key_for_verification
from sqlalchemy.ext.asyncio import AsyncSession


oauth2_scheme = HTTPBearer(auto_error=False)

api_key_scheme = APIKeyHeader(
    name="Authorization",
    auto_error=False,
    scheme_name="ApiKeyAuth",
    description="enter api key in the format: ApiKey <YOUR_API_KEY>",
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session


def get_aws_client_manager(request: Request) -> AwsClientManager:
    if not hasattr(request.app.state, "aws_client_manager"):
        raise RuntimeError("AwsClientManager not initialized. Check lifespan events")
    return request.app.state.aws_client_manager


def get_token_manager(request: Request) -> TokenManager:
    if not hasattr(request.app.state, "token_manager"):
        raise RuntimeError("TokenManager not initialized. Check lifespan events.")
    return request.app.state.token_manager


def get_provision_manager(request: Request) -> ProvisionManager:
    if not hasattr(request.app.state, "provision_manager"):
        raise RuntimeError("ProvisionManager not initialized. Check lifespan events")
    return request.app.state.provision_manager


SessionDep = Annotated[AsyncSession, Depends(get_db)]
TokenDep = Annotated[TokenManager, Depends(get_token_manager)]
AwsDep = Annotated[AwsClientManager, Depends(get_aws_client_manager)]
ProvisionDep = Annotated[ProvisionManager, Depends(get_provision_manager)]


async def get_token_payload(
    token: Annotated[Optional[str], Depends(oauth2_scheme)],
    token_manager: TokenDep,
) -> TokenData:
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="not authenticated: missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_str = token.credentials
    try:
        payload = token_manager.verify_token(token=token_str)
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
    db: SessionDep,
    token_manager: TokenDep,
    authorization: Annotated[
        Optional[str], Header(alias="Authorization", convert_underscores=False)
    ] = None,
) -> Optional[ApiData]:
    if authorization is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="not authenticated: missing authorization header for api key",
        )

    auth_parts = authorization.split(" ", 1)
    if len(auth_parts) != 2 or auth_parts[0] != "ApiKey":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid api key authentication scheme. Expected 'ApiKey <key>'",
        )
    api_key_full_string = auth_parts[1]

    api_key_bytes = api_key_full_string.encode("utf-8")

    verified_api_key = get_api_key_for_verification(db=db, api_key=api_key_bytes)
    if not verified_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="api key not found"
        )

    try:
        is_valid = token_manager.verify_api_key(
            api_key=api_key_full_string,
            key_hmac=verified_api_key.key_signature,
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


TokenPayloadDep = Annotated[TokenData, Depends(get_token_payload)]
ApiPayloadDep = Annotated[ApiData, Depends(get_api_payload)]
