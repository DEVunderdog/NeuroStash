import asyncio
import logging
from sqlalchemy import select, func, and_, or_
from sqlalchemy.orm import Session
from datetime import timedelta, datetime, timezone
from app.milvus.client import MilvusOps
from app.core.config import Settings
from app.constants.globals import (
    MIN_POOL_SIZE,
    MAX_POOL_SIZE,
    TIME_THRESHOLD,
    MAX_CONCURRENT_PROVISIONER,
)
from app.utils.name import generate_random_string
from app.utils.application_timezone import get_current_time
from app.dao.schema import MilvusCollections, ProvisionerStatusEnum, KnowledgeBase


logger = logging.getLogger(__name__)


class ProvisionManager:
    def __init__(self, session: Session, milvusOps: MilvusOps, settings: Settings):
        self.milvusOps = milvusOps
        self.db = session
        self.settings = settings
        self.minPoolSize = MIN_POOL_SIZE
        self.maxPoolSize = MAX_POOL_SIZE
        self.maxProvisioner = MAX_CONCURRENT_PROVISIONER

        self._reconcile_trigger_queue = asyncio.Queue()

    def provision_new_collection(self):
        try:
            collection_name = generate_random_string()
            collection_record_data = MilvusCollections(collection_name=collection_name)
            self.db.add(collection_record_data)
            self.db.commit()
            self.db.refresh(collection_record_data)
        except Exception as e:
            logger.error(
                f"error initiating provisioning collection: {e}", exc_info=True
            )
            self.db.rollback()
            raise

        try:
            self.milvusOps.create_collection(collection_name=collection_name)
        except Exception as e:
            logger.error(f"error creating collection in milvus: {e}", exc_info=True)
            try:
                self.db.delete(collection_record_data)
                self.db.commit()
            except Exception as cleanup_e:
                logger.error(
                    f"error deleting initiated collection in db: {cleanup_e}",
                    exc_info=True,
                )
                raise
            raise
        try:
            collection_record_data.status = ProvisionerStatusEnum.AVAILABLE
            self.db.commit()
            logger.info("successfully provisioned a collection")
        except Exception as e:
            logger.error(f"error finalizing provisioned collection: {e}", exc_info=True)
            self.db.rollback()
            raise

    async def reconcile_collections(self):
        current_time = get_current_time()

        available_stmt = (
            select(func.count())
            .select_from(MilvusCollections)
            .where(MilvusCollections.status == ProvisionerStatusEnum.AVAILABLE)
        )

        time_threshold = current_time - timedelta(minutes=TIME_THRESHOLD)
        provisioning_stmt = (
            select(func.count())
            .select_from(MilvusCollections)
            .where(
                (MilvusCollections.status == ProvisionerStatusEnum.PROVISIONING)
                & (MilvusCollections.created_at >= time_threshold)
            )
        )

        available_count = self.db.scalar(available_stmt)
        provisioning_count = self.db.scalar(provisioning_stmt)

        total_count = available_count + provisioning_count

        if total_count >= self.minPoolSize:
            return (available_count >= self.minPoolSize, False)

        needed = total_count - self.minPoolSize

        logger.info(
            f"available index={available_count}, provisioning={provisioning_count}, need to create={needed}"
        )

        semaphore = asyncio.Semaphore(self.maxProvisioner)

        async def provision_with_limit():
            async with semaphore:
                logger.info("dispatching index provisioner task")
                try:
                    await self.provision_new_collection()
                    logger.info("successfully provisioned index")
                except Exception as e:
                    logger.error(f"failed to provision new index: {e}", exc_info=True)
                    raise

        try:
            async with asyncio.TaskGroup() as tg:
                for i in range(needed):
                    tg.create_task(provision_with_limit())
        except* Exception as eg:
            error_msg = (
                f"reconcilation failed during provision of indexes: {eg.exceptions}"
            )
            logger.error(error_msg)
            raise Exception(error_msg)

        logger.info("index reconcilation cycle finished")

    async def reconcilation_worker(self):
        logger.info("intial reconcilation started of collections")
        try:
            await self.reconcile_collections()
        except Exception as e:
            logger.error(
                f"Initial reconciliation failed. Worker will continue: {e}",
                exc_info=True,
            )

        while True:
            try:
                async with asyncio.timeout(300):
                    await self._reconcile_trigger_queue.get()

                    logger.info("event-driven trigger received")

                    while not self._reconcile_trigger_queue.empty():
                        self._reconcile_trigger_queue.get_nowait()
                        logger.info("drained a buffered trigger")

            except asyncio.TimeoutError:
                logger.info("starting periodic reconcilation")

            try:
                await self.reconcile_collections()
            except Exception as e:
                logger.error(
                    f"reconcilation cycle failed with an exception: {e}", exc_info=True
                )

    def trigger_reconcilation(self):
        try:
            self._reconcile_trigger_queue.put_nowait(True)
            logger.info("successfully triggered a reconcilation check")
        except asyncio.QueueFull:
            logger.info("check is already pending, skipping")

    async def get_cleanup_collections(self):
        interval = datetime.now(timezone.utc) - timedelta(minutes=10)

        stmt = (
            select(MilvusCollections)
            .outerjoin(
                KnowledgeBase, MilvusCollections.id == KnowledgeBase.collection_id
            )
            .where(
                or_(
                    MilvusCollections.status == ProvisionerStatusEnum.FAILED,
                    and_(
                        MilvusCollections.status == ProvisionerStatusEnum.PROVISIONING,
                        MilvusCollections.created_at < interval,
                    ),
                    and_(
                        MilvusCollections.status == ProvisionerStatusEnum.CLEANUP,
                        KnowledgeBase.collection_id.is_(None),
                    ),
                )
            )
            .distinct()
        )

        result = await self.db.scalars(stmt)

        return result.all()

    async def cleanup_collections(self):
        try:
            collections_for_cleanup = self.get_cleanup_collections()
        except Exception:
            logger.error("Failed to query collections for cleanup.", exc_info=True)
            return

        if len(collections_for_cleanup) == 0:
            return

        logger.info(f"found {len(collections_for_cleanup)} collections for cleanup")

        semaphore = asyncio.Semaphore(self.maxProvisioner)

        async def cleanup_one_collection(
            collection: MilvusCollections, sem: asyncio.Semaphore
        ):
            async with sem:
                try:
                    await self.milvusOps.drop_collection(
                        collection_name=collection.collection_name
                    )
                    await self.db.delete(collection)
                    await self.db.commit()
                    logger.info("successfully dropped the collection")
                except Exception as e:
                    logger.error(f"failed to drop collection: {e}", exc_info=True)
                    raise

        try:
            async with asyncio.TaskGroup() as tg:
                for collection in collections_for_cleanup:
                    tg.create_task(
                        cleanup_one_collection(collection=collection, sem=semaphore)
                    )
        except* Exception as eg:
            error_msg = f"Cleanup cycle finished with {len(eg.exceptions)} error(s)."
            logger.error(error_msg, exc_info=True)

        logger.info("successfully collections cleanup done")

