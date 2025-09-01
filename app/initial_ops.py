import asyncio
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine
from tenacity import after_log, before_log, retry, stop_after_attempt, wait_fixed
from sqlalchemy import text
from app.core.db import SessionLocal, engine
from app.dao.user_dao import get_user_db, register_user
from app.dao.models import UserClientCreate, ApiKeyCreate
from app.dao.schema import ClientRoleEnum
from app.aws.client import AwsClientManager
from app.core.config import settings
from app.token_svc.token_manager import TokenManager, KeyNotFoundError
from app.mail.mail import send_api_email
from app.milvus.client import MilvusOps

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

MAX_TRIES = 60 * 5
WAIT_SECONDS = 3


@retry(
    stop=stop_after_attempt(MAX_TRIES),
    wait=wait_fixed(WAIT_SECONDS),
    before=before_log(logger, logging.INFO),
    after=after_log(logger, logging.WARNING),
    reraise=True,
)
async def check_db_ready() -> None:
    try:
        async_engine = create_async_engine(
            str(settings.SQLALCHEMY_DATABASE_URI), pool_pre_ping=True
        )
        async with async_engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        logger.info("Database connection successful.")
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        raise


async def create_admin_user(db_session: AsyncSession) -> None:
    logger.info(f"Checking for existing admin user: {settings.FIRST_ADMIN}")
    existing_admin = await get_user_db(db=db_session, email=settings.FIRST_ADMIN)

    if existing_admin:
        logger.info("Admin user already exists. No action taken.")
        return

    logger.info("admin user not found. Proceeding with creation")
    try:
        logger.info("initializing aws and token manager clients")
        aws_client_manager = AwsClientManager(settings=settings)
        token_manager = await TokenManager.create(
            initial_db_session=db_session,
            aws_client_manager=aws_client_manager,
            settings=settings,
        )

        logger.info("generating api key for admin user")
        api_key, api_key_bytes, signature, _ = token_manager.generate_api_key()

        user_client_create = UserClientCreate(
            email=settings.FIRST_ADMIN, role=ClientRoleEnum.ADMIN
        )
        _, active_key_id = token_manager.get_keys()

        api_key_create = ApiKeyCreate(
            key_id=active_key_id,
            key_credential=api_key_bytes,
            key_signature=signature,
        )

        await register_user(
            db=db_session, user=user_client_create, api_key_params=api_key_create
        )

        logger.info("sending api key via email")

        send_api_email(
            email_to=settings.FIRST_ADMIN,
            project_name=settings.PROJECT_NAME,
            api_key=api_key,
        )

        logger.info("successfully created and notified the admin")
    except (KeyNotFoundError, RuntimeError, Exception) as e:
        logger.error(
            f"A critical error occurred during admin user creation: {e}", exc_info=True
        )
        raise


async def setup_milvus_database() -> None:
    logger.info("initializing milvus database")
    try:
        milvus_ops = MilvusOps(settings=settings)
        milvus_ops.ensure_database(name=settings.MILVUS_DATABASE)
        logger.info("milvus database is ready")
    except Exception:
        logger.error("a criticial error occurred during milvus setup", exc_info=True)
        raise


async def main() -> None:
    logger.info("starting initial application")

    await check_db_ready()

    async with SessionLocal() as session:
        await create_admin_user(session)

    await setup_milvus_database()

    logger.info("Initial application setup completed.")

    await engine.dispose()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception:
        logger.error("Initial application setup failed.")
        raise
