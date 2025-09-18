import logging
from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession
from app.dao.models import PoolStats
from app.dao.schema import MilvusCollections, ProvisionerStatusEnum, SearchMethodEnum

logger = logging.getLogger(__name__)


async def get_collection_pool_stats(
    *, db: AsyncSession, collections_count: int
) -> PoolStats:
    try:

        stmt = select(
            func.count(MilvusCollections.id).label("total"),
            func.sum(
                case(
                    (
                        (MilvusCollections.status == ProvisionerStatusEnum.AVAILABLE)
                        & (MilvusCollections.search_method == SearchMethodEnum.FLAT),
                        1,
                    ),
                    else_=0,
                )
            ).label("flat_available_count"),
            func.sum(
                case(
                    (
                        (MilvusCollections.status == ProvisionerStatusEnum.PROVISIONING)
                        & (MilvusCollections.search_method == SearchMethodEnum.FLAT),
                        1,
                    ),
                    else_=0,
                )
            ).label("flat_provisioning_count"),
            func.sum(
                case(
                    (
                        (MilvusCollections.status == ProvisionerStatusEnum.AVAILABLE)
                        & (MilvusCollections.search_method == SearchMethodEnum.HNSW),
                        1,
                    ),
                    else_=0,
                )
            ).label("hnsw_available_count"),
            func.sum(
                case(
                    (
                        (MilvusCollections.status == ProvisionerStatusEnum.PROVISIONING)
                        & (MilvusCollections.search_method == SearchMethodEnum.HNSW),
                        1,
                    ),
                    else_=0,
                )
            ).label("hnsw_provisioning_count"),
            func.sum(
                case(
                    (
                        (MilvusCollections.status == ProvisionerStatusEnum.AVAILABLE)
                        & (MilvusCollections.search_method == SearchMethodEnum.IVF_SQ8),
                        1,
                    ),
                    else_=0,
                )
            ).label("ivf_available_count"),
            func.sum(
                case(
                    (
                        (MilvusCollections.status == ProvisionerStatusEnum.PROVISIONING)
                        & (MilvusCollections.search_method == SearchMethodEnum.IVF_SQ8),
                        1,
                    ),
                    else_=0,
                )
            ).label("ivf_provisioning_count"),
        )

        counts = (await db.execute(stmt)).one()

        flat_available_count = counts.flat_available_count or 0
        flat_provisioning_count = counts.flat_provisioning_count or 0
        hnsw_available_count = counts.hnsw_available_count or 0
        hnsw_provisioning_count = counts.hnsw_provisioning_count or 0
        ivf_available_count = counts.ivf_available_count or 0
        ivf_provisioning_count = counts.ivf_provisioning_count or 0

        return PoolStats(
            message="successfully fetched the pool stats",
            flat_available_count=flat_available_count,
            flat_provisioning_count=flat_provisioning_count,
            hnsw_available_count=hnsw_available_count,
            hnsw_provisioning_count=hnsw_provisioning_count,
            ivf_available_count=ivf_available_count,
            ivf_provisioning_count=ivf_provisioning_count,
            remote_collections=collections_count,
        )

    except Exception as e:
        logger.error(f"error getting pool collection stats: {e}")
        raise
