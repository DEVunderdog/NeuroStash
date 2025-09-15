from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError, NoResultFound, SQLAlchemyError
from sqlalchemy import select, func
from app.dao.models import CreateKbInDb, ListKbDocs, KbDoc
from app.dao.schema import (
    KnowledgeBase,
    DocumentRegistry,
    KnowledgeBaseDocument,
    OperationStatusEnum,
    MilvusCollections,
    ProvisionerStatusEnum,
)
from typing import List, Tuple
from sqlalchemy.orm import selectinload
import psycopg


class KnowledgeBaseAlreadyExists(Exception):
    def __init__(self, knowledg_base_name: str):
        self.kb = knowledg_base_name
        super().__init__(f"knowledge with name '{knowledg_base_name}' already exists")


class KnowledgeBaseNotFound(Exception):
    def __init__(self, kb_id: int):
        self.kb_id = kb_id
        super().__init__(f"knowledge base with id {kb_id} not found")


async def create_kb_db(*, db: AsyncSession, kb: CreateKbInDb) -> KnowledgeBase:
    try:
        async with db.begin():
            stmt = (
                select(MilvusCollections)
                .where(MilvusCollections.status == ProvisionerStatusEnum.AVAILABLE)
                .order_by(func.random())
                .limit(1)
                .with_for_update(skip_locked=True)
            )

            result = await db.execute(stmt)

            available_collection = result.scalar_one()

            available_collection.status = ProvisionerStatusEnum.ASSIGNED

            knowledge_base = KnowledgeBase(
                user_id=kb.user_id,
                name=kb.name,
                collection_id=available_collection.id,
                category=kb.category,
                milvus_collections=available_collection,
            )

            db.add(knowledge_base)

        await db.refresh(knowledge_base)
        return knowledge_base

    except NoResultFound:
        await db.rollback()
        raise RuntimeError("no available milvus collection found.")

    except IntegrityError as e:
        await db.rollback()
        if isinstance(e.orig, psycopg.errors.UniqueViolation):
            raise KnowledgeBaseAlreadyExists(knowledg_base_name=kb.name)
        else:
            raise RuntimeError(f"database integrity error: {e}")

    except Exception as e:
        await db.rollback()
        raise RuntimeError(f"failed to create knowledge base in database: {e}")


async def get_kb_collection(*, db: AsyncSession, user_id, kb_id: int) -> str:
    try:
        stmt = (
            select(MilvusCollections.collection_name)
            .join(KnowledgeBase, KnowledgeBase.collection_id == MilvusCollections.id)
            .where(KnowledgeBase.id == kb_id, KnowledgeBase.user_id == user_id)
        )

        result = await db.execute(stmt)
        collection_name = result.scalar_one()

        return collection_name
    except NoResultFound:
        raise KnowledgeBaseNotFound(kb_id=kb_id)
    except SQLAlchemyError:
        raise
    except Exception:
        raise


async def list_users_kb(
    *, db: AsyncSession, limit: int = 100, offset: int = 0, user_id: int
) -> Tuple[List[KnowledgeBase], int]:
    stmt = select(KnowledgeBase).where(KnowledgeBase.user_id == user_id)

    count_stmt = select(func.count()).select_from(stmt.subquery())

    result = await db.execute(count_stmt)
    total_count = result.scalar()

    stmt = stmt.limit(limit=limit)
    stmt = stmt.offset(offset=offset)

    kb_result = await db.execute(stmt)

    kb = kb_result.scalars().all()

    return kb, total_count


async def list_kb_docs(
    *, db: AsyncSession, limit: int = 200, offset: int = 0, user_id: int, kb_id: int
) -> ListKbDocs:

    query = (
        select(
            DocumentRegistry.id,
            DocumentRegistry.file_name,
            KnowledgeBaseDocument.id.label("kb_doc_id"),
            KnowledgeBaseDocument.status,
        )
        .join(
            KnowledgeBaseDocument,
            DocumentRegistry.id == KnowledgeBaseDocument.document_id,
        )
        .where(
            DocumentRegistry.user_id == user_id,
            DocumentRegistry.op_status == OperationStatusEnum.SUCCESS,
            DocumentRegistry.lock_status == False,
            KnowledgeBaseDocument.knowledge_base_id == kb_id,
        )
    )

    count_stmt = select(func.count()).select_from(query.subquery())

    count_result = await db.execute(count_stmt)

    total_count = count_result.scalar()

    query = query.limit(limit=limit)
    query = query.offset(offset=offset)

    result = await db.execute(query)

    docs = [
        KbDoc(
            kb_doc_id=row.kb_doc_id,
            doc_id=row.id,
            file_name=row.file_name,
            status=row.status.value,
        )
        for row in result.all()
    ]

    return ListKbDocs(
        docs=docs,
        knowledge_base_id=kb_id,
        total_count=total_count,
        message="successfully fetch knowledge base documents",
    )


async def delete_kb_db(*, db: AsyncSession, user_id: int, kb_id: int) -> bool:
    try:
        async with db.begin():
            stmt = (
                select(KnowledgeBase)
                .options(selectinload(KnowledgeBase.milvus_collections))
                .where(KnowledgeBase.id == kb_id, KnowledgeBase.user_id == user_id)
            )
            result = await db.execute(stmt)
            kb = result.scalar_one()

            if kb.milvus_collections:
                kb.milvus_collections.status = ProvisionerStatusEnum.CLEANUP
            else:
                raise RuntimeError(
                    f"inconsistent state: KnowledgeBase {kb_id} has no associated milvus collections"
                )
            await db.delete(kb)
        return True
    except NoResultFound:
        raise
    except Exception:
        await db.rollback()
        raise
