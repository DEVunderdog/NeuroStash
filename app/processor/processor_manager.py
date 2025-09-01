import asyncio
import itertools
import logging
from typing import List, Tuple

from langchain_openai import OpenAIEmbeddings
from sqlalchemy import case, update
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
    ) -> List[List[Tuple[int, OperationStatusEnum]]]:
        tasks = []

        if message.body.index_kb_doc_id and len(message.body.index_kb_doc_id):
            index_files: List[FileForIngestion] = message.body.index_kb_doc_id
            indexing_task = asyncio.create_task(
                self.ingest_data_ops.index_data(
                    files=index_files,
                    user_id=message.body.user_id,
                    category=message.body.category,
                    collection_name=message.body.collection_name,
                )
            )
            tasks.append(asyncio.create_task(indexing_task))

        if message.body.delete_kb_doc_id and len(message.body.delete_kb_doc_id):
            delete_files: List[FileForIngestion] = message.body.delete_kb_doc_id
            reindexing_task = asyncio.create_task(
                self.ingest_data_ops.reindex_data(
                    files=delete_files, collection_name=message.body.collection_name
                )
            )
            tasks.append(asyncio.create_task(reindexing_task))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        return results

    async def _bulk_update_document_statuses(
        self, db: AsyncSession, results: List[Tuple[int, OperationStatusEnum]]
    ):
        if not results or len(results) == 0:
            logger.info("no document statues to update")
            return

        status_map = {doc_id: status.value for doc_id, status in results}
        stmt = (
            update(KnowledgeBaseDocument)
            .where(KnowledgeBaseDocument.id.in_(status_map.keys()))
            .values(
                status=case(
                    whens=status_map,
                    value=KnowledgeBaseDocument.id,
                    else_=KnowledgeBaseDocument.status,
                )
            )
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

    async def process_message(self, message: ReceivedSqsMessage):
        logger.info("initiating processing message")
        try:
            all_results = asyncio.run(self._process_tasks_concurrently(message=message))
            logger.info("indexing and reindexing is completed")

            exceptions = [res for res in all_results if isinstance(res, Exception)]
            if exceptions:
                for exc in exceptions:
                    logger.error(
                        f"An exception occurred during concurrent execution: {exc}",
                        exc_info=exc,
                    )
                raise exceptions[0]

            processed_items = itertools.chain.from_iterable(
                response for response in all_results if isinstance(response, list)
            )

            async with SessionLocal() as db:
                if processed_items:
                    await self._bulk_update_document_statuses(
                        db=db, results=processed_items
                    )

                await self._set_ingestion_job_status(
                    db=db,
                    job_id=message.body.ingestion_job_id,
                    status=OperationStatusEnum.SUCCESS,
                )

                await db.commit()
                logger.info(
                    f"database updates for job {message.body.ingestion_job_id} committed successfully"
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
