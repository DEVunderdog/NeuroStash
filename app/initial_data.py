import logging
from app.core.config import settings
from sqlalchemy import create_engine
from sqlalchemy.orm import Session as SqlSession
from app.dao.user_dao import first_admin

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

database_uri = str(settings.SQLALCHEMY_DATABASE_URI)
engine = create_engine(url=database_uri, pool_pre_ping=True)


def init() -> None:
    with SqlSession(engine) as session:
        first_admin(db=session)


def main() -> None:
    logger.info("creating initial data")
    init()
    logger.info("initial data created")


if __name__ == "__main__":
    main()
