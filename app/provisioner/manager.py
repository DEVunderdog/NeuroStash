import asyncio
import logging
from sqlalchemy import select, func, and_, or_, case, delete
from app.core.db import SessionLocal
from datetime import timedelta
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
    def __init__(self, milvusOps: MilvusOps, settings: Settings):
        self.milvusOps = milvusOps
        self.settings = settings
        self.minPoolSize = MIN_POOL_SIZE
        self.maxPoolSize = MAX_POOL_SIZE
        self.maxProvisioner = MAX_CONCURRENT_PROVISIONER

        self._reconcile_trigger_queue = asyncio.Queue()
        self._cleanup_trigger_queue = asyncio.Queue()

    async def provision_new_collection(self):
        collection_name = f"_{generate_random_string()}"
        collection_record_id = None
        try:
            async with SessionLocal() as db:
                async with db.begin():
                    new_collection = MilvusCollections(
                        collection_name=collection_name,
                        status=ProvisionerStatusEnum.PROVISIONING,
                    )
                    db.add(new_collection)
                await db.refresh(new_collection)
                collection_record_id = new_collection.id
            logger.info(
                f"successfully initiated record for collection: {collection_name}"
            )
        except Exception as e:
            logger.error(
                f"error initiating provisioning collection: {e}", exc_info=True
            )
            raise

        try:
            await asyncio.to_thread(
                self.milvusOps.create_collection, collection_name=collection_name
            )
            logger.info(
                f"successfully created collection '{collection_name}' in milvus"
            )
        except Exception as e:
            logger.error(f"error creating collection in milvus: {e}", exc_info=True)
            try:
                async with SessionLocal() as db:
                    async with db.begin():
                        record_to_delete = await db.get(
                            MilvusCollections, collection_record_id
                        )
                        if record_to_delete:
                            await db.delete(record_to_delete)
                            logger.info(
                                "successfully rolled back by deleted record for milvus collection"
                            )
            except Exception as cleanup_e:
                logger.error(
                    f"error deleting initiated collection in db: {cleanup_e}",
                    exc_info=True,
                )
            raise e
        try:
            async with SessionLocal() as db:
                async with db.begin():
                    collection_to_update = await db.get(
                        MilvusCollections, collection_record_id
                    )
                    if not collection_to_update:
                        raise RuntimeError(
                            f"record for collection id {collection_record_id} not found for final update"
                        )
                    collection_to_update.status = ProvisionerStatusEnum.AVAILABLE
            logger.info("successfully provisioned a collection")
        except Exception as e:
            logger.error(f"error finalizing provisioned collection: {e}", exc_info=True)
            raise

    async def reconcile_collections(self):
        time_threshold = get_current_time() - timedelta(minutes=TIME_THRESHOLD)

        async with SessionLocal() as db:
            stmt = select(
                func.count(MilvusCollections.id).label("total"),
                func.sum(
                    case(
                        (
                            MilvusCollections.status == ProvisionerStatusEnum.AVAILABLE,
                            1,
                        ),
                        else_=0,
                    )
                ).label("available_count"),
                func.sum(
                    case(
                        (
                            (
                                MilvusCollections.status
                                == ProvisionerStatusEnum.PROVISIONING
                            )
                            & (MilvusCollections.created_at >= time_threshold),
                            1,
                        ),
                        else_=0,
                    )
                ).label("provisioning_count"),
            )

            counts = (await db.execute(stmt)).one()

            available_count = counts.available_count or 0
            provisioning_count = counts.provisioning_count or 0

        total_count = available_count + provisioning_count

        if total_count >= self.minPoolSize:
            return (available_count >= self.minPoolSize, False)

        needed = self.minPoolSize - total_count

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

        exceptions = None
        try:
            async with asyncio.TaskGroup() as tg:
                for i in range(needed):
                    tg.create_task(provision_with_limit())
        except* Exception as eg:
            error_msg = (
                f"reconcilation failed during provision of indexes: {eg.exceptions}"
            )
            logger.error(error_msg)
            exceptions = eg

        if exceptions:
            raise

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
            logger.info("reconcilation check is already pending, skipping")

    def trigger_cleanup(self):
        try:
            self._cleanup_trigger_queue.put_nowait(True)
            logger.info("successfully triggered a cleanup")
        except asyncio.QueueFull:
            logger.info("cleanup check is already pending, skipping")

    async def get_cleanup_collections(self):
        try:
            async with SessionLocal() as db:
                current_time = get_current_time()
                stuck_threshold = current_time - timedelta(minutes=10)

                failed_collection = (
                    MilvusCollections.status == ProvisionerStatusEnum.FAILED
                )

                stuck_provisioning_collection = and_(
                    MilvusCollections.status == ProvisionerStatusEnum.PROVISIONING,
                    MilvusCollections.created_at < stuck_threshold,
                )

                unlinked_cleanup_collections = and_(
                    MilvusCollections.status == ProvisionerStatusEnum.CLEANUP,
                    KnowledgeBase.collection_id.is_(None),
                )

                stmt = (
                    select(MilvusCollections)
                    .outerjoin(
                        KnowledgeBase,
                        MilvusCollections.id == KnowledgeBase.collection_id,
                    )
                    .where(
                        or_(
                            failed_collection,
                            stuck_provisioning_collection,
                            unlinked_cleanup_collections,
                        )
                    )
                    .distinct()
                )

                result = await db.scalars(stmt)
                collections_to_clean = result.all()

                return collections_to_clean
        except Exception as e:
            logger.error(
                f"database error while querying for cleanup collection: {e}",
                exc_info=True,
            )
            raise

    async def cleanup_collections(self):
        try:
            collections_for_cleanup = await self.get_cleanup_collections()
        except Exception:
            logger.error("Failed to query collections for cleanup.", exc_info=True)
            raise

        if len(collections_for_cleanup) == 0:
            return

        logger.info(f"found {len(collections_for_cleanup)} collections for cleanup")

        semaphore = asyncio.Semaphore(self.maxProvisioner)
        exceptions = None

        try:
            async with asyncio.TaskGroup() as tg:
                for collection in collections_for_cleanup:
                    tg.create_task(
                        self._cleanup_one_collection(
                            collection=collection, sem=semaphore
                        )
                    )
        except* Exception as eg:
            error_msg = f"Cleanup cycle finished with {len(eg.exceptions)} error(s)."
            logger.error(error_msg, exc_info=True)
            exceptions = eg

        if exceptions:
            logger.info("Collections cleanup cycle finished with errors.")
            raise exceptions
        else:
            logger.info("Successfully finished collections cleanup cycle.")

    async def _cleanup_one_collection(
        self, collection: MilvusCollections, sem: asyncio.Semaphore
    ):
        async with sem:
            collection_name = collection.collection_name
            collection_id = collection.id

            try:
                await asyncio.to_thread(
                    self.milvusOps.drop_collection, collection_name=collection_name
                )
                logger.info("successfully drop collection from milvus")
            except Exception as e:
                logger.error(
                    f"failed to drop collection from milvus aborting cleanup for this item: {e}"
                )
                raise

            try:
                async with SessionLocal() as db:
                    async with db.begin():
                        delete_stmt = delete(MilvusCollections).where(
                            MilvusCollections.id == collection_id
                        )
                        await db.execute(delete_stmt)
                    logger.info("successfully deleted record for collection")
            except Exception as e:
                logger.critical(
                    f"error dropping collection in database: {e}", exc_info=True
                )
                raise

    async def cleanup_worker(self):
        logger.info("event-driven cleanup worker for collections")

        while True:
            try:
                await self._cleanup_trigger_queue.get()
                logger.info("event-driven trigger received for cleanup collection")

                while not self._cleanup_trigger_queue.empty():
                    self._cleanup_trigger_queue.get_nowait()
                    logger.info("drained cleanup queue buffered trigger")

                await self.cleanup_collections()
            except Exception as e:
                logger.error(
                    f"cleanup cycle failed with an exception: {e}", exc_info=True
                )

    def get_list_of_collections(self):
        try:
            res = self.milvusOps.list_collections()
            return res
        except Exception as e:
            logger.error(f"{e}")
            raise
