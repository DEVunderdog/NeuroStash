import logging
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session as SqlSession
from tenacity import after_log, before_log, retry, stop_after_attempt, wait_fixed
from app.core.config import settings

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

database_uri = str(settings.SQLALCHEMY_DATABASE_URI)
engine = create_engine(url=database_uri, pool_pre_ping=True)

max_tries = 60 * 5
wait_seconds = 3


@retry(
    stop=stop_after_attempt(max_tries),
    wait=wait_fixed(wait_seconds),
    before=before_log(logger, logging.DEBUG),
    after=after_log(logger, logging.INFO),
)
def init(db_engine: Engine) -> None:
    try:
        with SqlSession(db_engine) as session:
            session.execute(text("SELECT 1"))
        logger.info("database connection successfully")
    except Exception as e:
        logger.error(f"database connection/query failed: {e}")
        raise


def main() -> None:
    logger.info("initializing service")
    init(engine)
    logger.info("service finished intializing")


if __name__ == "__main__":
    main()
