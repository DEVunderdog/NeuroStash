import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert, update, delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError
from typing import List
from datetime import timedelta
from app.dao.models import CreatedIngestionJob, FileForIngestion
from app.dao.schema import (
    KnowledgeBaseDocument,
    OperationStatusEnum,
    IngestionJob,
    DocumentRegistry,
    KnowledgeBase,
    MilvusCollections,
    ParentChunkedDoc,
)
from uuid import UUID
from app.utils.application_timezone import get_current_time

logger = logging.getLogger(__name__)


class KnowledgeBaseNotFound(Exception):
    pass


class DocsNotFound(Exception):
    def __init__(self, missing_ids):
        self.missing_ids = missing_ids
        super().__init__(f"documents not found: {missing_ids}")


async def create_ingestion_job(
    *,
    db: AsyncSession,
    document_ids: List[int],
    kb_id: int,
    job_resource_id: UUID,
    user_id: int,
) -> CreatedIngestionJob:
    try:
        kb_stmt = (
            select(MilvusCollections.collection_name, KnowledgeBase.category)
            .join(
                MilvusCollections, KnowledgeBase.collection_id == MilvusCollections.id
            )
            .where(KnowledgeBase.id == kb_id)
            .where(KnowledgeBase.user_id == user_id)
        )

        result = await db.execute(kb_stmt)
        knowledge_base_result = result.first()

        if knowledge_base_result is None:
            raise KnowledgeBaseNotFound(
                f"KnowledgeBase with id={kb_id} and user_id={user_id} not found."
            )

        existing_docs = await db.execute(
            select(
                DocumentRegistry.id,
                DocumentRegistry.file_name,
                DocumentRegistry.object_key,
            ).where(DocumentRegistry.id.in_(document_ids))
        )

        existing_data = {
            row.id: {"file_name": row.file_name, "object_key": row.object_key}
            for row in existing_docs
        }
        missing_ids = set(document_ids) - set(existing_data.keys())

        if missing_ids:
            raise DocsNotFound(missing_ids=missing_ids)

        ingestion_job_id = (
            await db.execute(
                insert(IngestionJob)
                .values(
                    kb_id=kb_id,
                    resource_id=job_resource_id,
                    op_status=OperationStatusEnum.PENDING,
                )
                .returning(IngestionJob.id)
            )
        ).scalar_one()

        kb_doc_pairs = [(kb_id, doc_id) for doc_id in document_ids]

        stmt = (
            pg_insert(KnowledgeBaseDocument)
            .values(
                [
                    {
                        "knowledge_base_id": kb_id,
                        "document_id": doc_id,
                        "status": OperationStatusEnum.PENDING,
                    }
                    for kb_id, doc_id in kb_doc_pairs
                ]
            )
            .on_conflict_do_update(
                index_elements=["knowledge_base_id", "document_id"],
                set_={"status": OperationStatusEnum.PENDING},
            )
        ).returning(
            KnowledgeBaseDocument.id,
            KnowledgeBaseDocument.document_id,
        )

        kb_doc_upsert_result = await db.execute(stmt)

        kb_doc_ids_rows = kb_doc_upsert_result.mappings().all()

        file_for_ingestion: List[FileForIngestion] = []

        for row in kb_doc_ids_rows:
            if row.document_id in existing_data:
                file_for_ingestion.append(
                    FileForIngestion(
                        kb_doc_id=row.id,
                        doc_id=row.document_id,
                        file_name=existing_data[row.document_id]["file_name"],
                        object_key=existing_data[row.document_id]["object_key"],
                    )
                )

        return CreatedIngestionJob(
            ingestion_id=ingestion_job_id,
            collection_name=knowledge_base_result.collection_name,
            category=knowledge_base_result.category,
            user_id=user_id,
            documents=file_for_ingestion,
            kb_id=kb_id,
        )

    except (KnowledgeBaseNotFound, SQLAlchemyError) as e:
        await db.rollback()
        logger.error(
            f"Error during ingestion job creation for kb_id={kb_id}: {e}",
            exc_info=True,
        )
        raise

    except DocsNotFound as e:
        await db.rollback()
        logger.error(f"we cannot find the following documents: {e}")
        raise

    except Exception as e:
        await db.rollback()
        logger.error(
            f"Unexpected error during ingestion job creation for kb_id={kb_id}: {e}",
            exc_info=True,
        )
        raise


async def create_parent_chunk(
    *, db: AsyncSession, document_id: int, chunk: str
) -> ParentChunkedDoc:
    parent_doc = ParentChunkedDoc(
        document_id=document_id,
        chunk=chunk,
    )
    return parent_doc


async def delete_parent_chunk(*, db: AsyncSession, document_id: int):
    await db.execute(
        delete(ParentChunkedDoc).where(ParentChunkedDoc.document_id == document_id)
    )


async def get_ingestion_job_status(
    *, db: AsyncSession, ingestion_job_id: int, user_id: int
) -> OperationStatusEnum:

    stmt = select(IngestionJob.op_status).where(
        IngestionJob.id == ingestion_job_id, user_id == user_id
    )

    result = await db.execute(stmt)

    status = result.scalar()

    return status


async def cleanup_ingestion_job(*, db: AsyncSession):
    current_time = get_current_time()
    cutoff_time = current_time - timedelta(hours=1)
    stmt = (
        update(IngestionJob)
        .where(
            IngestionJob.op_status == OperationStatusEnum.PENDING,
            IngestionJob.updated_at < cutoff_time,
        )
        .values(op_status=OperationStatusEnum.FAILED)
    )

    await db.execute(stmt)
    await db.commit()
