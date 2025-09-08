import asyncio
import logging
from typing import List, Tuple

from langchain_openai import OpenAIEmbeddings
from sqlalchemy import case, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.aws.client import AwsClientManager
from app.constants.models import OPENAI_EMBEDDINGS_MODEL
from app.core.config import Settings
from app.dao.models import FileForIngestion, ReceivedSqsMessage
from app.dao.schema import IngestionJob, KnowledgeBaseDocument, OperationStatusEnum
from app.milvus.client import MilvusOps
from app.processor.ingest_data import IngestData
from app.processor.semantic_chunker import CustomSemanticChunker
from app.core.db import SessionLocal


logger = logging.getLogger(__name__)


class InvalidFileExtension(Exception):
    pass

class ProcessorManager:
    def __init__(
        self,
        aws_client_manager: AwsClientManager,
        settings: Settings,
        milvus_ops: MilvusOps,
    ):
        self.aws_client_manager: AwsClientManager = aws_client_manager
        self.settings: Settings = settings
        self.embeddings = OpenAIEmbeddings(
            model=OPENAI_EMBEDDINGS_MODEL, api_key=settings.OPENAI_KEY
        )
        self.semantic_chunker: CustomSemanticChunker = CustomSemanticChunker(
            embeddings=self.embeddings
        )
        self.ingest_data_ops: IngestData = IngestData(
            embeddings=self.embeddings,
            aws_client_manager=self.aws_client_manager,
            semantic_chunker=self.semantic_chunker,
            milvus_ops=milvus_ops,
        )

    async def _process_tasks_concurrently(
        self, message: ReceivedSqsMessage
    ) -> Tuple[List, List]:
        tasks_to_run = []
        indexing_task_present = False
        reindexing_task_present = False

        if message.body.index_kb_doc_id and len(message.body.index_kb_doc_id):
            index_files: List[FileForIngestion] = message.body.index_kb_doc_id
            tasks_to_run.append(
                asyncio.create_task(
                    self.ingest_data_ops.index_data(
                        files=index_files,
                        user_id=message.body.user_id,
                        category=message.body.category,
                        collection_name=message.body.collection_name,
                    )
                )
            )
            indexing_task_present = True

        if message.body.delete_kb_doc_id and len(message.body.delete_kb_doc_id):
            delete_files: List[FileForIngestion] = message.body.delete_kb_doc_id
            tasks_to_run.append(
                asyncio.create_task(
                    self.ingest_data_ops.reindex_data(
                        files=delete_files, collection_name=message.body.collection_name
                    )
                )
            )
            reindexing_task_present = True

        if not tasks_to_run:
            return [], []

        all_results = await asyncio.gather(*tasks_to_run)

        if indexing_task_present and reindexing_task_present:
            return all_results[0], all_results[1]
        elif indexing_task_present:
            return all_results[0], []
        elif reindexing_task_present:
            return [], all_results[0]
        else:
            return [], []

    async def _bulk_update_document_statuses(
        self, db: AsyncSession, results: List[Tuple[int, OperationStatusEnum]]
    ):
        if not results:
            logger.info("no document statues to update")
            return

        status_map = {doc_id: status for doc_id, status in results}

        status_case = case(
            status_map,
            value=KnowledgeBaseDocument.id,
            else_=KnowledgeBaseDocument.status,
        )

        stmt = (
            update(KnowledgeBaseDocument)
            .where(KnowledgeBaseDocument.id.in_(status_map.keys()))
            .values(status=status_case)
        )
        await db.execute(stmt)
        logger.info("successfully updated document statuses")

    async def _set_ingestion_job_status(
        self, db: AsyncSession, job_id: int, status: OperationStatusEnum
    ):
        stmt = (
            update(IngestionJob)
            .where(IngestionJob.id == job_id)
            .values(op_status=status)
        )
        await db.execute(stmt)

    async def _bulk_delete_documents(self, db: AsyncSession, doc_ids: List[int]):
        if not doc_ids:
            logger.info("no document statuses to update")
            return

        stmt = delete(KnowledgeBaseDocument).where(
            KnowledgeBaseDocument.id.in_(doc_ids)
        )

        await db.execute(stmt)

    async def process_message(self, message: ReceivedSqsMessage):
        logger.info("initiating processing message")
        try:
            job_failed = False
            indexing_results, deletion_results = await self._process_tasks_concurrently(
                message=message
            )
            logger.info("indexing and reindexing is completed")

            exceptions = [
                res
                for res in indexing_results + deletion_results
                if isinstance(res, Exception)
            ]

            if exceptions:
                job_failed = True
                for exc in exceptions:
                    logger.error(
                        f"An exception occurred during concurrent execution for job {message.body.ingestion_job_id}: {exc}",
                        exc_info=exc,
                    )

            async with SessionLocal() as db:
                updates_to_perform = [
                    res for res in indexing_results if isinstance(res, tuple)
                ]
                if updates_to_perform:
                    await self._bulk_update_document_statuses(
                        db=db, results=updates_to_perform
                    )

                deletion_to_perform = [
                    res for res in deletion_results if isinstance(res, tuple)
                ]
                if deletion_to_perform:
                    ids_to_delete = [
                        doc_id
                        for doc_id, status in deletion_to_perform
                        if status == OperationStatusEnum.SUCCESS
                    ]
                    failed_deletion = [
                        (doc_id, status)
                        for doc_id, status in deletion_to_perform
                        if status == OperationStatusEnum.FAILED
                    ]

                    if ids_to_delete:
                        await self._bulk_delete_documents(db=db, doc_ids=ids_to_delete)

                    if failed_deletion:
                        await self._bulk_update_document_statuses(
                            db=db, results=failed_deletion
                        )
                        job_failed = True

                final_job_status = (
                    OperationStatusEnum.FAILED
                    if job_failed
                    else OperationStatusEnum.SUCCESS
                )
                await self._set_ingestion_job_status(
                    db=db,
                    job_id=message.body.ingestion_job_id,
                    status=final_job_status,
                )

                await db.commit()

                logger.info(
                    f"Database updates for job {message.body.ingestion_job_id} committed with final status: {final_job_status.name}"
                )

        except Exception as e:
            logger.error(
                f"An unexpected error occurred in process_message for job {message.body.ingestion_job_id}: {e}",
                exc_info=True,
            )
            try:
                async with SessionLocal() as db:
                    await self._set_ingestion_job_status(
                        db=db,
                        job_id=message.body.ingestion_job_id,
                        status=OperationStatusEnum.FAILED,
                    )
                    await db.commit()
                    logger.warning(
                        f"Successfully marked job {message.body.ingestion_job_id} as FAILED after transaction failure."
                    )
            except Exception as final_update_exc:
                logger.critical(
                    f"CRITICAL: Could not mark job {message.body.ingestion_job_id} as FAILED. Manual intervention required. Error: {final_update_exc}",
                    exc_info=True,
                )
