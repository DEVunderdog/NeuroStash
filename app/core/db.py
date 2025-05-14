from sqlalchemy import create_engine
from app.core.config import settings

SQLALCHEMY_DATABASE_URL = str(settings.SQLALCHEMY_DATABASE_URI)

engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI))
