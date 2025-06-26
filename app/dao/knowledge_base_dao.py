from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select, delete
from app.dao.models import CreateKbInDb
from app.dao.schema import KnowledgeBase
from typing import List
import psycopg2


class KnowledgeBaseAlreadyExists(Exception):
    def __init__(self, knowledg_base_name: str):
        self.kb = knowledg_base_name
        super().__init__(f"knowledge with name '{knowledg_base_name}' already exists")


def create_kb_db(*, db: Session, kb: CreateKbInDb) -> KnowledgeBase:
    try:
        knowledge_base = KnowledgeBase(**kb.model_dump())
        db.add(knowledge_base)
        db.commit()
        db.refresh(knowledge_base)
        return knowledge_base
    except IntegrityError as e:
        db.rollback()
        if isinstance(e.orig, psycopg2.errors.UniqueViolation):
            raise KnowledgeBaseAlreadyExists(knowledg_base_name=kb.name)
    except Exception as e:
        db.rollback()
        raise RuntimeError(f"failed to create knowledge base in database: {e}")


def list_users_kb(
    *, db: Session, limit: int = 10, offset: int = 0, user_id: int
) -> List[KnowledgeBase]:
    stmt = select(KnowledgeBase).where(KnowledgeBase.user_id == user_id)
    kb = db.scalars(stmt).all()
    return kb


def delete_kb_db(*, db: Session, user_id: int, kb_id: int) -> bool:
    try:
        stmt = delete(KnowledgeBase).where(
            KnowledgeBase.id == kb_id, KnowledgeBase.user_id == user_id
        )
        result = db.execute(stmt)
        db.commit()
        return result.rowcount > 0
    except Exception:
        db.rollback()
        raise
