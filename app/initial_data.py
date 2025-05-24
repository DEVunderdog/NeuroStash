import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import Session as SqlSession
from app.dao.user_dao import get_user, register_user
from app.dao.models import UserClientCreate, ApiKeyCreate
from app.dao.schema import ClientRoleEnum
from app.aws.client import AwsClientManager
from app.core.config import settings
from app.token.token_manager import TokenManager, KeyNotFoundError
from app.mail.mail import send_api_email

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

database_uri = str(settings.SQLALCHEMY_DATABASE_URI)
engine = create_engine(url=database_uri, pool_pre_ping=True)


def init() -> None:
    with SqlSession(engine) as session:
        existing_admin = get_user(db=session, email=settings.FIRST_ADMIN)
        if existing_admin is None:
            logger.debug("initializing aws client")
            aws_client_manager = AwsClientManager(settings=settings)
            logger.info("initializing token manager")
            try:
                token_manager = TokenManager(
                    initial_db_session=session, aws_client_manager=aws_client_manager
                )
            except RuntimeError as e:
                logger.error(
                    f"failed to initialize token manager due to RuntimeError: {e}"
                )
                raise
            except Exception as e:
                logger.error(
                    f"failed to initialize token manager due to Exception: {e}"
                )
                raise

            logger.debug("generating api key...")
            try:
                api_key, signature = token_manager.generate_api_key()
            except KeyNotFoundError as e:
                logger.error(f"key not found for signing: {e}")
                raise
            except RuntimeError as e:
                logger.error(f"RuntimeError while generating api key: {e}")
                raise

            try:
                user_client_create = UserClientCreate(
                    email=settings.FIRST_ADMIN, role=ClientRoleEnum.ADMIN
                )
                _, active_key_id = token_manager.get_keys()
                api_key_create = ApiKeyCreate(
                    key_id=active_key_id,
                    key_credential=api_key,
                    key_signature=signature,
                )
                _, _ = register_user(
                    db=session, user=user_client_create, api_key_params=api_key_create
                )
            except Exception as e:
                msg = f"error creating user and api keys in database: {e}"
                logger.error(msg)
                raise

            try:
                send_api_email(
                    email_to=settings.FIRST_ADMIN,
                    project_name=settings.PROJECT_NAME,
                    api_key=api_key,
                )
            except Exception as e:
                msg = f"error sending mail for api keys: {e}"
                logger.error(msg, exc_info=True)
                return
        else:
            logger.info("admin already exists")
            return


def main() -> None:
    init()


if __name__ == "__main__":
    main()
