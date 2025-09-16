import asyncio
import logging
from app.core.config import settings
from app.provisioner.manager import ProvisionManager
from app.milvus.client import MilvusOps

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def prime_milvus_pool() -> None:
    logger.info("Priming Milvus collection pool...")
    try:
        milvus_ops = MilvusOps(settings=settings)
        milvus_ops.ensure_database(name=settings.MILVUS_DATABASE)
        provision_manager = ProvisionManager(milvusOps=milvus_ops, settings=settings)
        await provision_manager.reconcile_collections()
        logger.info("Successfully primed Milvus collection pool.")
    except Exception as e:
        logger.error(f"Failed to prime Milvus collection pool: {e}", exc_info=True)
        raise


async def main() -> None:
    logger.info("Initializing service...")
    await prime_milvus_pool()
    logger.info("Service finished initializing.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.critical(
            f"A critical error occurred during pre-start initialization: {e}"
        )
        exit(1)
