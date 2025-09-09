import logging
from fastapi import APIRouter, status, HTTPException
from app.dao.models import PoolStats
from app.api.deps import SessionDep, TokenPayloadDep
from app.dao.schema import ClientRoleEnum
from app.dao.collection_pool import get_collection_pool_stats

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pool", tags=["pool management"])


@router.get(
    "/stats",
    response_model=PoolStats,
    status_code=status.HTTP_200_OK,
    summary="milvu collection pool stats",
)
async def get_pool_stats(db: SessionDep, payload: TokenPayloadDep):
    if payload.role != ClientRoleEnum.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="you are not authorized to perform this action",
        )

    try:
        pool_stats = await get_collection_pool_stats(db=db)

        return pool_stats
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"an error occurred while fetching collection stats pool: {e}",
        )
