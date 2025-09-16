import logging
from fastapi import APIRouter, status, HTTPException
from app.dao.models import PoolStats
from app.api.deps import SessionDep, TokenPayloadDep, ProvisionDep
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
async def get_pool_stats(
    db: SessionDep, payload: TokenPayloadDep, provision_manager: ProvisionDep
):
    if payload.role != ClientRoleEnum.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="you are not authorized to perform this action",
        )

    try:
        res = provision_manager.get_list_of_collections()
        collections_count = len(res)
        
        pool_stats = await get_collection_pool_stats(db=db, collections_count=collections_count)
        return pool_stats
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"an error occurred while fetching collection stats pool: {e}",
        )
