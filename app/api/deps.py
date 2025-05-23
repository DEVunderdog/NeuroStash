from collections.abc import Generator
from typing import Annotated
from sqlalchemy.orm import Session
from app.core.db import SessionLocal
from fastapi import Depends


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


SessionDep = Annotated[Session, Depends(get_db)]
