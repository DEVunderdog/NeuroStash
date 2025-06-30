import logging
from sqlalchemy.orm import Session
from sqlalchemy import select, insert
from sqlalchemy.exc import SQLAlchemyError
from typing import List
from app.dao.models import CreatedIngestionJob
from app.dao.schema import (
    KnowledgeBaseDocument,
    OperationStatusEnum,
    IngestionJob,
    DocumentRegistry,
)
from uuid import UUID

logger = logging.getLogger(__name__)


def create_ingestion_job(
    *,
    db: Session,
    document_ids: List[int],
    kb_id: int,
    job_resource_id: UUID,
    user_id: int
) -> CreatedIngestionJob:
    try:
        stmt = (
            insert(IngestionJob)
            .values(
                kb_id=kb_id,
                resource_id=job_resource_id,
                op_status=OperationStatusEnum.PENDING,
            )
            .returning(IngestionJob.id)
        )

        result = db.execute(stmt)
        ingestion_job_id = result.scalar()

        if ingestion_job_id is None:
            raise SQLAlchemyError("failed to create ingestion job")

        existing_stmt = select(
            KnowledgeBaseDocument.id, KnowledgeBaseDocument.document_id
        ).where(
            KnowledgeBaseDocument.knowledge_base_id == kb_id,
            KnowledgeBaseDocument.document_id.in_(document_ids),
            KnowledgeBaseDocument.status == OperationStatusEnum.SUCCESS
        )

        existing_result = db.execute(existing_stmt).all()
        existing_map = {doc_id: kb_doc_id for kb_doc_id, doc_id in existing_result}
        existing_doc_ids = set(existing_map.keys())

        new_doc_ids = [
            doc_id for doc_id in document_ids if doc_id not in existing_doc_ids
        ]
        conflicted_doc_ids = [
            doc_id for doc_id in document_ids if doc_id in existing_doc_ids
        ]

        new_object_keys_stmt = select(DocumentRegistry.object_key).where(
            DocumentRegistry.id.in_(new_doc_ids), DocumentRegistry.user_id == user_id
        )
        new_object_keys_result = db.execute(new_object_keys_stmt)
        object_keys = new_object_keys_result.scalars().all()

        inserted_ids = []

        if new_doc_ids:
            data_to_insert = [
                {
                    "knowledge_base_id": kb_id,
                    "document_id": doc_id,
                    "status": OperationStatusEnum.PENDING,
                }
                for doc_id in new_doc_ids
            ]
            stmt = (
                insert(KnowledgeBaseDocument)
                .values(data_to_insert)
                .returning(KnowledgeBaseDocument.id)
            )
            insert_result = db.execute(stmt)
            inserted_ids = insert_result.scalars().all()

        conflicted_kb_doc_ids = [existing_map[doc_id] for doc_id in conflicted_doc_ids]

        db.commit()

        return CreatedIngestionJob(
            new_kb_documents=inserted_ids,
            existing_kb_documents=conflicted_kb_doc_ids,
            ingestion_id=ingestion_job_id,
            ingestion_resource_id=job_resource_id,
            object_keys=object_keys,
        )
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(
            "database error creating ingestion job",
            extra={
                "kb_id": kb_id,
                "resource_id": str(job_resource_id),
                "document_count": len(document_ids),
                "error": str(e),
            },
            exc_info=True,
        )
        raise
    except Exception as e:
        db.rollback()
        logger.error(
            "Unexpected error creating ingestion job",
            extra={
                "kb_id": kb_id,
                "resource_id": str(job_resource_id),
                "document_count": len(document_ids),
                "error": str(e),
            },
            exc_info=True,
        )
        raise

