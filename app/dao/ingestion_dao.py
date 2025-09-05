import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert, update
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

        documents_to_be_ingested: List[int] = []
        kb_documents_to_reprocessed: List[int] = []
        successfully_processed_docs: List[int] = []
        file_for_ingestion: List[FileForIngestion] = []

        if document_ids:
            stmt = (
                select(
                    KnowledgeBaseDocument.id.label("kb_doc_id"),
                    KnowledgeBaseDocument.status,
                    KnowledgeBaseDocument.document_id.label("doc_id"),
                    DocumentRegistry.file_name,
                    DocumentRegistry.object_key,
                )
                .join(
                    DocumentRegistry,
                    DocumentRegistry.id == KnowledgeBaseDocument.document_id,
                )
                .where(
                    KnowledgeBaseDocument.knowledge_base_id == kb_id,
                    KnowledgeBaseDocument.document_id.in_(document_ids),
                )
            )

            document_result = await db.execute(stmt)

            document_rows = document_result.all()

            for row in document_rows:
                kb_doc_id = row.kb_doc_id
                doc_id = row.doc_id
                status = row.status
                file_name = row.file_name
                object_key = row.object_key

                if status == OperationStatusEnum.PENDING:
                    kb_documents_to_reprocessed.append(kb_doc_id)
                    documents_to_be_ingested.append(doc_id)
                    file_for_ingestion.append(
                        FileForIngestion(
                            doc_id=doc_id, file_name=file_name, object_key=object_key
                        )
                    )
                if status == OperationStatusEnum.FAILED:
                    kb_documents_to_reprocessed.append(kb_doc_id)
                    documents_to_be_ingested.append(doc_id)
                    file_for_ingestion.append(
                        FileForIngestion(
                            doc_id=doc_id, file_name=file_name, object_key=object_key
                        )
                    )
                if status == OperationStatusEnum.SUCCESS:
                    successfully_processed_docs.append(doc_id)

            if kb_documents_to_reprocessed:
                update_stmt = (
                    update(KnowledgeBaseDocument)
                    .where(KnowledgeBaseDocument.id.in_(kb_documents_to_reprocessed))
                    .values(status=OperationStatusEnum.PENDING)
                )

                await db.execute(update_stmt)

        return CreatedIngestionJob(
            ingestion_id=ingestion_job_id,
            ingestion_resource_id=str(job_resource_id),
            collection_name=knowledge_base_result.collection_name,
            category=knowledge_base_result.category,
            user_id=user_id,
            documents=file_for_ingestion,
            successfully_processed_docs=successfully_processed_docs,
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
