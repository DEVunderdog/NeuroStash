from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select, delete, func
from app.dao.models import CreateKbInDb, ListKbDocs, KbDoc
from app.dao.schema import (
    KnowledgeBase,
    DocumentRegistry,
    KnowledgeBaseDocument,
    OperationStatusEnum,
)
from typing import List, Tuple
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
    *, db: Session, limit: int = 100, offset: int = 0, user_id: int
) -> Tuple[List[KnowledgeBase], int]:
    stmt = select(KnowledgeBase).where(KnowledgeBase.user_id == user_id)

    count_stmt = select(func.count()).select_from(stmt.subquery())

    total_count = db.execute(count_stmt).scalar()

    stmt = stmt.limit(limit=limit)
    stmt = stmt.offset(offset=offset)

    kb = db.execute(stmt).scalars().all()

    return kb, total_count


def list_kb_docs(
    *, db: Session, limit: int = 200, offset: int = 0, user_id: int, kb_id: int
) -> ListKbDocs:

    query = (
        select(
            DocumentRegistry.id,
            DocumentRegistry.file_name,
            KnowledgeBaseDocument.id.label("kb_doc_id"),
        )
        .join(
            KnowledgeBaseDocument,
            DocumentRegistry.id == KnowledgeBaseDocument.document_id,
        )
        .where(
            DocumentRegistry.user_id == user_id,
            DocumentRegistry.op_status == OperationStatusEnum.SUCCESS,
            DocumentRegistry.lock_status == False,
            KnowledgeBaseDocument.op_status == OperationStatusEnum.SUCCESS,
            KnowledgeBaseDocument.knowledge_base_id == kb_id,
        )
    )

    count_stmt = select(func.count()).select_from(query.subquery())

    total_count = db.execute(count_stmt).scalar()

    query = query.limit(limit=limit)
    query = query.offset(offset=offset)

    result = db.execute(query).all()

    docs = [
        KbDoc(id=row.id, kb_doc_id=row.kb_doc_id, file_name=row.file_name)
        for row in result
    ]

    return ListKbDocs(
        docs=docs,
        knowledge_base_id=kb_id,
        total_count=total_count,
        message="successfully fetch knowledge base documents",
    )


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
