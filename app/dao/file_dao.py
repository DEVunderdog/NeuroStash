from sqlalchemy.orm import Session
from sqlalchemy import insert, update, select, case, delete, or_, and_, cast
from sqlalchemy.exc import IntegrityError
from app.dao.models import CreateDocument
from app.dao.schema import DocumentRegistry, OperationStatusEnum
from typing import List, Tuple
import logging

logger = logging.getLogger(__name__)


def create_document(
    *, db: Session, files: List[CreateDocument]
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
        result = db.execute(stmt, documents_data)

        created_documents = [(row.id, row.file_name) for row in result.fetchall()]

        db.commit()

        logger.info(f"successfully created {len(created_documents)} documents")

        return created_documents

    except IntegrityError as e:
        db.rollback()
        logging.error("integrity error during creating documents", exc_info=e)
        raise ValueError("duplicate file names or constraint violation")

    except Exception as e:
        db.rollback()
        logging.error("error during bulk document creation", exc_info=e)
        raise


def finalize_documents(*, db: Session, successful: List[int], failed: List[int]):
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

        db.execute(stmt)

        db.commit()
    except Exception as e:
        db.rollback()
        logger.error("error finalizing documents in database", exc_info=e)
        raise


def list_files(*, db: Session, user_id: int) -> List[DocumentRegistry]:
    try:
        stmt = select(DocumentRegistry).where(
            DocumentRegistry.user_id == user_id,
            DocumentRegistry.lock_status == False,
            DocumentRegistry.op_status == OperationStatusEnum.SUCCESS,
        )

        documents = db.execute(stmt).scalars().all()

        return documents
    except Exception as e:
        logger.error("error listing users documents from database", exc_info=e)
        raise


def lock_documents(*, db: Session, document_ids: List[int], user_id: int) -> List[str]:
    try:
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
        result = db.execute(stmt)
        object_keys = [row.object_key for row in result.fetchall()]
        db.commit()
        return object_keys
    except Exception as e:
        db.rollback()
        logger.error("error locking the documents", exc_info=e)
        raise


def delete_documents(*, db: Session, document_ids: List[int], user_id: int):
    try:
        stmt = delete(DocumentRegistry).where(
            DocumentRegistry.id.in_(document_ids),
            DocumentRegistry.op_status == OperationStatusEnum.PENDING,
            DocumentRegistry.lock_status is True,
            DocumentRegistry.user_id == user_id,
        )

        db.execute(stmt)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error("error during deleting file in database", exc_info=e)
        raise


def conflicted_docs(*, db: Session, user_id: int) -> List[DocumentRegistry]:
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

        result = db.execute(stmt)
        return result.scalars().all()
    except Exception as e:
        logger.error("error while fetching conflicted documents", exc_info=e)
        raise


def cleanup_docs(
    *, db: Session, user_id: int, to_be_unlocked: List[int], to_be_deleted: List[int]
):
    try:
        if to_be_deleted:
            stmt = delete(DocumentRegistry).where(
                DocumentRegistry.id.in_(to_be_deleted),
                DocumentRegistry.user_id == user_id,
            )
            db.execute(stmt)

        if to_be_unlocked:
            stmt = (
                update(DocumentRegistry)
                .where(
                    DocumentRegistry.id.in_(to_be_unlocked),
                    DocumentRegistry.user_id == user_id,
                )
                .values(lock_status=False, op_status=OperationStatusEnum.SUCCESS)
            )
            db.execute(stmt)

        db.commit()
    except Exception as e:
        db.rollback()
        logger.error("error cleaning up docs in database", exc_info=e)
        raise
