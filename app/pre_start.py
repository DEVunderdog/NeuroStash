import asyncio
import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from tenacity import after_log, before_log, retry, stop_after_attempt, wait_fixed
from app.core.config import settings
from app.provisioner.manager import ProvisionManager
from app.milvus.client import MilvusOps

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

MAX_TRIES = 60 * 5  # 5 minutes
WAIT_SECONDS = 3

@retry(
    stop=stop_after_attempt(MAX_TRIES),
    wait=wait_fixed(WAIT_SECONDS),
    before=before_log(logger, logging.INFO),
    after=after_log(logger, logging.WARNING),
    reraise=True
)
async def check_db_ready() -> None:
    try:
        async_engine = create_async_engine(str(settings.SQLALCHEMY_DATABASE_URI), pool_pre_ping=True)
        async with async_engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        logger.info("Database connection successful.")
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        raise

async def prime_milvus_pool() -> None:
    logger.info("Priming Milvus collection pool...")
    try:
        milvus_ops = MilvusOps(settings=settings)
        provision_manager = ProvisionManager(milvusOps=milvus_ops, settings=settings)
        await provision_manager.reconcile_collections()
        logger.info("Successfully primed Milvus collection pool.")
    except Exception as e:
        logger.error(f"Failed to prime Milvus collection pool: {e}", exc_info=True)
        raise

async def main() -> None:
    logger.info("Initializing service...")
    await check_db_ready()
    await prime_milvus_pool()
    logger.info("Service finished initializing.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.critical(f"A critical error occurred during pre-start initialization: {e}")
        exit(1)