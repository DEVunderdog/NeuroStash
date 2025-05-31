from fastapi import APIRouter, status, HTTPException
from app.dao.models import (
    UserClientCreate,
    UserClientCreated,
    RegisterUser,
    ApiKeyCreate,
    ListUsers,
    StandardResponse,
)
from app.api.deps import SessionDep, TokenDep, TokenPayloadDep
from app.dao.schema import ClientRoleEnum
from app.token_svc.token_manager import KeyNotFoundError
from app.dao.user_dao import (
    register_user,
    UserAlreadyExistsError,
    list_users_db,
    promote_user_db,
    delete_user_db,
)

import logging

router = APIRouter(prefix="/user", tags=["User"])

logger = logging.getLogger(__name__)


@router.post(
    "/register",
    response_model=UserClientCreated,
    status_code=status.HTTP_201_CREATED,
    summary="register a new user and provision an api key via mail by Admin",
)
def register_user_to_app(
    user_in: RegisterUser,
    db: SessionDep,
    token_manager: TokenDep,
    admin_payload: TokenPayloadDep,
):
    if admin_payload.role != ClientRoleEnum.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="you are not authorized to perform this action",
        )
    try:
        api_key, api_key_signature, active_key_id = token_manager.generate_api_key()
    except KeyNotFoundError as e:
        logger.error("cannot create api key while registering user", exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="error while creating api keys",
        )
    except RuntimeError as e:
        msg = "cannot create api key while registering user"
        logger.error(msg, exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=msg
        )

    try:
        user = UserClientCreate(email=user_in.email, role=ClientRoleEnum.USER)
        api_key_params = ApiKeyCreate(
            key_id=active_key_id,
            key_credential=api_key,
            key_signature=api_key_signature,
        )
        db_user_client, db_api_key = register_user(
            db=db, user=user, api_key_params=api_key_params
        )
    except UserAlreadyExistsError as e:
        msg = "user already exists"
        logger.error(msg, exc_info=e)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)
    except Exception as e:
        msg = "error registering user and storing it"
        logger.error(msg, exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=msg
        )
    return UserClientCreated(
        id=db_user_client.id, email=db_user_client.email, api_key=api_key
    )


@router.get(
    "/list",
    response_model=ListUsers,
    status_code=status.HTTP_200_OK,
    summary="list of users",
)
def list_users(
    admin_payload: TokenPayloadDep,
    db: SessionDep,
    limit: int = 10,
    offset: int = 0,
):
    if admin_payload.role != ClientRoleEnum.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="you are not authorized to perform this action",
        )
    users = list_users_db(db=db, limit=limit, offset=offset)
    return ListUsers(users=users)


@router.patch(
    "/promote/{user_id}",
    response_model=StandardResponse,
    status_code=status.HTTP_200_OK,
    summary="promote users to admin role",
)
def promote_users(
    user_id: int,
    db: SessionDep,
    admin_payload: TokenPayloadDep,
):
    if admin_payload.role != ClientRoleEnum.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="you are not authorized to perform this action",
        )
    try:
        user_client = promote_user_db(db=db, user_id=user_id)
        if user_client is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="cannot find user with provided id",
            )
    except Exception as e:
        msg = "error promoting user to admin"
        logger.error(msg, exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=msg
        )

    return StandardResponse(message="successfully promoted user to admin")


@router.delete(
    "/delete/{user_id}",
    response_model=StandardResponse,
    status_code=status.HTTP_200_OK,
    summary="delete users",
)
def delete_users(
    user_id: int,
    db: SessionDep,
    admin_payload: TokenPayloadDep,
):
    if admin_payload.role != ClientRoleEnum.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="you are not authorized to peform this action",
        )

    if admin_payload.user_id == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="you cannot delete yourself"
        )

    try:
        deleted = delete_user_db(db=db, user_id=user_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="cannot find user with provided id",
            )
    except Exception as e:
        msg = "error deleting user"
        logger.error(msg, exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=msg
        )

    return StandardResponse(message="user deleted successfully")
