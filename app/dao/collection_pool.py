import logging
from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession
from app.dao.models import PoolStats
from app.dao.schema import MilvusCollections, ProvisionerStatusEnum

logger = logging.getLogger(__name__)


async def get_collection_pool_stats(*, db: AsyncSession) -> PoolStats:
    try:
        stmt = select(
            func.count(
                case(
                    (MilvusCollections.status == ProvisionerStatusEnum.AVAILABLE, 1),
                    else_=None,
                )
            ).label("available"),
            func.count(
                case(
                    (MilvusCollections.status == ProvisionerStatusEnum.FAILED, 1),
                    else_=None,
                )
            ).label("failed"),
            func.count(
                case(
                    (MilvusCollections.status == ProvisionerStatusEnum.CLEANUP, 1),
                    else_=None,
                )
            ).label("cleanup"),
            func.count(
                case(
                    (MilvusCollections.status == ProvisionerStatusEnum.ASSIGNED, 1),
                    else_=None,
                )
            ).label("assigned"),
        ).select_from(MilvusCollections)

        result = await db.execute(stmt)

        row = result.first()

        return PoolStats(
            message="successfully fetched the pool stats",
            available=row.available,
            assigned=row.assigned,
            cleanup=row.cleanup,
            failed=row.failed,
        )

    except Exception as e:
        logger.error(f"error getting pool collection stats: {e}")
        raise
