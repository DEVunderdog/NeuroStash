from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

engine = create_async_engine(
    url=str(settings.SQLALCHEMY_DATABASE_URI),
    pool_pre_ping=True,
    connect_args={"options": "-c timezone=utc"},
)

SessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=engine, class_=AsyncSession
)
