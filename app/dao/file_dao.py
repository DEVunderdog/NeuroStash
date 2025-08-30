import logging
from typing import List, Tuple

from sqlalchemy import and_, case, cast, delete, insert, or_, select, update, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from app.dao.models import CreateDocument
from app.dao.schema import DocumentRegistry, OperationStatusEnum, KnowledgeBaseDocument

logger = logging.getLogger(__name__)


class DocumentInKnowledgeBaseError(Exception):
    def __init__(
        self,
        message="one or more documents are already preset in knowledge base and cannot be locked",
    ):
        self.message = message
        super().__init__(self.message)


async def create_document(
    *, db: AsyncSession, files: List[CreateDocument]
) -> List[Tuple[int, str]]:
    try:
        documents_data = [
            {
                "user_id": file.user_id,
                "file_name": file.file_name,
                "object_key": file.object_key,
                "lock_status": True,
                "op_status": OperationStatusEnum.PENDING,
            }
            for file in files
        ]

        stmt = insert(DocumentRegistry).returning(
            DocumentRegistry.id, DocumentRegistry.file_name
        )

        result = await db.execute(stmt, documents_data)

        created_documents = [(row.id, row.file_name) for row in result.fetchall()]

        await db.commit()

        logger.info(f"successfully created {len(created_documents)} documents")

        return created_documents

    except IntegrityError:
        await db.rollback()
        logging.error("integrity error during creating documents", exc_info=True)
        raise ValueError("duplicate file names or constraint violation")

    except Exception:
        await db.rollback()
        logging.error("error during bulk document creation", exc_info=True)
        raise


async def finalize_documents(
    *, db: AsyncSession, successful: List[int], failed: List[int]
):
    try:
        all_ids = successful + failed

        stmt = (
            update(DocumentRegistry)
            .where(DocumentRegistry.id.in_(all_ids))
            .values(
                op_status=case(
                    (
                        DocumentRegistry.id.in_(successful),
                        cast(
                            OperationStatusEnum.SUCCESS.value,
                            DocumentRegistry.op_status.type,
                        ),
                    ),
                    (
                        DocumentRegistry.id.in_(failed),
                        cast(
                            OperationStatusEnum.FAILED.value,
                            DocumentRegistry.op_status.type,
                        ),
                    ),
                ),
                lock_status=False,
            )
        )

        await db.execute(stmt)

        await db.commit()
    except Exception:
        db.rollback()
        logger.error("error finalizing documents in database", exc_info=True)
        raise


async def list_files(
    *, db: AsyncSession, user_id: int, limit: int, offset: int
) -> Tuple[List[DocumentRegistry], int]:
    try:
        stmt = select(DocumentRegistry).where(
            DocumentRegistry.user_id == user_id,
            DocumentRegistry.lock_status == False,
            DocumentRegistry.op_status == OperationStatusEnum.SUCCESS,
        )

        count_stmt = select(func.count()).select_from(stmt.subquery())

        count_result = await db.execute(count_stmt)
        total_count = count_result.scalar()

        stmt = stmt.limit(limit=limit)
        stmt = stmt.offset(offset=offset)

        result = await db.execute(stmt)
        documents = result.scalars().all()

        return documents, total_count
    except Exception:
        logger.error("error listing users documents from database", exc_info=True)
        raise


async def lock_documents(
    *, db: AsyncSession, document_ids: List[int], user_id: int
) -> List[str]:
    try:
        query = select(KnowledgeBaseDocument.document_id).where(
            KnowledgeBaseDocument.document_id.in_(document_ids)
        )
        result = await db.execute(query)
        existing_docs = result.scalars().all()

        if existing_docs:
            raise DocumentInKnowledgeBaseError(
                f"documents with IDs {existing_docs} are in knowledge base"
            )
        
        stmt = (
            update(DocumentRegistry)
            .where(
                DocumentRegistry.id.in_(document_ids),
                DocumentRegistry.op_status == OperationStatusEnum.SUCCESS,
                DocumentRegistry.lock_status == False,
                DocumentRegistry.user_id == user_id,
            )
            .values(lock_status=True, op_status=OperationStatusEnum.PENDING)
            .returning(DocumentRegistry.object_key)
        )
        result = await db.execute(stmt)
        object_keys = [row.object_key for row in result.fetchall()]
        await db.commit()
        return object_keys
    except Exception:
        await db.rollback()
        logger.error("error locking the documents", exc_info=True)
        raise


async def delete_documents(*, db: AsyncSession, document_ids: List[int], user_id: int):
    try:
        stmt = delete(DocumentRegistry).where(
            DocumentRegistry.id.in_(document_ids),
            DocumentRegistry.op_status == OperationStatusEnum.PENDING,
            DocumentRegistry.lock_status is True,
            DocumentRegistry.user_id == user_id,
        )

        await db.execute(stmt)
        await db.commit()
    except Exception:
        await db.rollback()
        logger.error("error during deleting file in database", exc_info=True)
        raise


async def conflicted_docs(*, db: AsyncSession, user_id: int) -> List[DocumentRegistry]:
    try:
        valid_combinations = [
            (True, OperationStatusEnum.PENDING),
            (True, OperationStatusEnum.SUCCESS),
            (True, OperationStatusEnum.FAILED),
            (False, OperationStatusEnum.PENDING),
            (False, OperationStatusEnum.FAILED),
        ]

        stmt = select(DocumentRegistry).where(
            and_(
                DocumentRegistry.user_id == user_id,
                or_(
                    *[
                        and_(
                            DocumentRegistry.lock_status == lock_status,
                            DocumentRegistry.op_status == op_status,
                        )
                        for lock_status, op_status in valid_combinations
                    ]
                ),
            )
        )

        result = await db.execute(stmt)
        return result.scalars().all()
    except Exception:
        logger.error("error while fetching conflicted documents", exc_info=True)
        raise


async def cleanup_docs(
    *,
    db: AsyncSession,
    user_id: int,
    to_be_unlocked: List[int],
    to_be_deleted: List[int],
):
    try:
        if to_be_deleted:
            stmt = delete(DocumentRegistry).where(
                DocumentRegistry.id.in_(to_be_deleted),
                DocumentRegistry.user_id == user_id,
            )
            await db.execute(stmt)

        if to_be_unlocked:
            stmt = (
                update(DocumentRegistry)
                .where(
                    DocumentRegistry.id.in_(to_be_unlocked),
                    DocumentRegistry.user_id == user_id,
                )
                .values(lock_status=False, op_status=OperationStatusEnum.SUCCESS)
            )
            await db.execute(stmt)

        await db.commit()
    except Exception:
        db.rollback()
        logger.error("error cleaning up docs in database", exc_info=True)
        raise
