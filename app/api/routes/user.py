import logging

from fastapi import APIRouter, HTTPException, status

from app.api.deps import SessionDep, TokenDep, TokenPayloadDep
from app.dao.models import (
    ApiKeyCreate,
    ListUsers,
    RegisterUser,
    StandardResponse,
    UserClientCreate,
    UserClientCreated,
)
from app.dao.schema import ClientRoleEnum
from app.dao.user_dao import (
    UserAlreadyExistsError,
    delete_user_db,
    list_users_db,
    promote_user_db,
    register_user,
)
from app.token_svc.token_manager import KeyNotFoundError

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
        api_key, api_key_bytes, api_key_signature, active_key_id = (
            token_manager.generate_api_key()
        )
    except KeyNotFoundError:
        logger.error("cannot create api key while registering user", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="error while creating api keys",
        )
    except RuntimeError:
        msg = "cannot create api key while registering user"
        logger.error(msg, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=msg
        )

    try:
        user = UserClientCreate(email=user_in.email, role=ClientRoleEnum.USER)
        api_key_params = ApiKeyCreate(
            key_id=active_key_id,
            key_credential=api_key_bytes,
            key_signature=api_key_signature,
        )
        db_user_client, db_api_key = register_user(
            db=db, user=user, api_key_params=api_key_params
        )
    except UserAlreadyExistsError:
        msg = "user already exists"
        logger.error(msg, exc_info=True)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)
    except Exception:
        msg = "error registering user and storing it"
        logger.error(msg, exc_info=True)
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
    return ListUsers(message="successfully fetched users", users=users)


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

    if user_id == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="please provide user_id to promote",
        )
    try:
        user_client = promote_user_db(db=db, user_id=user_id)
        if user_client is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="cannot find user with provided id",
            )
    except HTTPException:
        raise
    except Exception:
        msg = "error promoting user to admin"
        logger.error(msg, exc_info=True)
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

    if user_id == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="please provide user_id to delete",
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
    except HTTPException:
        raise
    except Exception:
        msg = "error deleting user"
        logger.error(msg, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=msg
        )

    return StandardResponse(message="user deleted successfully")
