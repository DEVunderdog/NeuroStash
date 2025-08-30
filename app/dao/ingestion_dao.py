import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert, update, union_all
from sqlalchemy.exc import SQLAlchemyError
from typing import List
from app.dao.models import CreatedIngestionJob, FileForIngestion
from app.dao.schema import (
    KnowledgeBaseDocument,
    OperationStatusEnum,
    IngestionJob,
    DocumentRegistry,
    KnowledgeBase,
    MilvusCollections,
)
from uuid import UUID

logger = logging.getLogger(__name__)


class KnowledgeBaseNotFound(Exception):
    pass


async def create_ingestion_job(
    *,
    db: AsyncSession,
    document_ids: List[int],
    retry_kb_doc_ids: List[int],
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

        ingestion_job_id = await db.execute(
            insert(IngestionJob)
            .values(
                kb_id=kb_id,
                resource_id=job_resource_id,
                op_status=OperationStatusEnum.PENDING,
            )
            .returning(IngestionJob.id)
        ).scalar_one()

        document_detail_queries = []

        if document_ids:
            documents_to_insert = [
                {
                    "knowledge_base_id": kb_id,
                    "document_id": doc_id,
                    "status": OperationStatusEnum.PENDING,
                }
                for doc_id in document_ids
            ]

            insert_stmt = (
                insert(KnowledgeBaseDocument)
                .values(documents_to_insert)
                .returning(KnowledgeBaseDocument.id, KnowledgeBaseDocument.document_id)
            ).cte("inserted_cte")

            select_inserted_stmt = select(
                insert_stmt.c.id,
                DocumentRegistry.file_name,
                DocumentRegistry.object_key,
            ).join(DocumentRegistry, insert_stmt.c.document_id == DocumentRegistry.id)

            document_detail_queries.append(select_inserted_stmt)

        if retry_kb_doc_ids:
            update_stmt = (
                update(KnowledgeBaseDocument)
                .where(KnowledgeBaseDocument.id.in_(retry_kb_doc_ids))
                .values(status=OperationStatusEnum.PENDING)
                .returning(KnowledgeBaseDocument.id, KnowledgeBaseDocument.document_id)
            ).cte("updated_cte")

            select_update_stmt = select(
                update_stmt.c.id,
                DocumentRegistry.file_name,
                DocumentRegistry.object_key,
            ).join(DocumentRegistry, update_stmt.c.document_id == DocumentRegistry.id)
            document_detail_queries.append(select_update_stmt)

        ingested_documents: List[FileForIngestion] = []

        if document_detail_queries:
            final_select_stmt = union_all(*document_detail_queries)
            results = await db.execute(final_select_stmt)

            ingested_documents = [
                FileForIngestion(
                    kb_doc_id=row.id, file_name=row.file_name, object_key=row.object_key
                )
                for row in results.all()
            ]

        return CreatedIngestionJob(
            ingestion_id=ingestion_job_id,
            ingestion_resource_id=str(job_resource_id),
            collection_name=knowledge_base_result.collection_name,
            category=knowledge_base_result.category,
            user_id=user_id,
            documents=ingested_documents,
        )

    except (KnowledgeBaseNotFound, SQLAlchemyError) as e:
        await db.rollback()
        logger.error(
            f"Error during ingestion job creation for kb_id={kb_id}: {e}",
            exc_info=True,
        )
        raise

    except Exception as e:
        await db.rollback()
        logger.error(
            f"Unexpected error during ingestion job creation for kb_id={kb_id}: {e}",
            exc_info=True,
        )
        raise
