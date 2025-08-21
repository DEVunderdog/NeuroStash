import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import Session as SqlSession
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

def create_admin_user(db_session: SqlSession) -> None:
    logger.info(f"Checking for existing admin user: {settings.FIRST_ADMIN}")
    existing_admin = get_user_db(db=db_session, email=settings.FIRST_ADMIN)

    if existing_admin:
        logger.info("Admin user already exists. No action taken.")
        return

    logger.info("admin user not found. Proceeding with creation")
    try:
        logger.info("initializing aws and token manager clients")
        aws_client_manager = AwsClientManager(settings=settings)
        token_manager = TokenManager(
            initial_db_session=db_session, aws_client_manager=aws_client_manager
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

        register_user(
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


def setup_milvus_database() -> None:
    logger.info("initializing milvus database")
    try:
        milvus_ops = MilvusOps(settings=settings)
        db_name = "rag_db"
        db = milvus_ops.get_database(name=db_name)
        if db is None:
            milvus_ops.create_database(name=db_name)
        else:
            logger.info(f"milvus database '{db_name}' already exists")
    except Exception:
        logger.error("a criticial error occurred during milvus setup", exc_info=True)
        raise


def main() -> None:
    database_uri = str(settings.SQLALCHEMY_DATABASE_URI)
    engine = create_engine(url=database_uri, pool_pre_ping=True)

    with SqlSession(engine) as session:
        create_admin_user(session)

    setup_milvus_database()

    logger.info("Initial application setup completed.")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logger.error("inital application setup failed")
