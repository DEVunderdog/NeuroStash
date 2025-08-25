import logging
import asyncio
from app.aws.client import AwsClientManager
from app.core.config import Settings
from app.dao.models import ReceivedSqsMessage, FilesForIngestion
from sqlalchemy.orm import Session
from app.processor.semantic_chunker import CustomSemanticChunker
from app.processor.ingest_data import IngestData
from langchain_openai import OpenAIEmbeddings
from app.constants.models import OPENAI_EMBEDDINGS_MODEL
from typing import List, Tuple
from app.dao.schema import OperationStatusEnum, KnowledgeBaseDocument, IngestionJob
import itertools
from sqlalchemy import update, case

logger = logging.getLogger(__name__)


class InvalidFileExtension(Exception):
    pass


class ProcessorManager:
    def __init__(
        self, aws_client_manager: AwsClientManager, settings: Settings, db: Session
    ):
        self.aws_client_manager: AwsClientManager = aws_client_manager
        self.settings: Settings = settings
        self.db: Session = db
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
            settings=settings,
        )

    async def _process_tasks_concurrently(
        self, message: ReceivedSqsMessage
    ) -> List[List[Tuple[int, OperationStatusEnum]]]:
        tasks = []

        if message.body.index_kb_doc_id and len(message.body.index_kb_doc_id):
            index_files: List[FilesForIngestion] = message.body.index_kb_doc_id
            indexing_task = asyncio.create_task(
                self.ingest_data_ops.index_data(
                    files=index_files,
                    user_id=message.body.user_id,
                    category=message.body.category,
                    collection_name=message.body.collection_name,
                )
            )
            tasks.append(indexing_task)

        if message.body.delete_kb_doc_id and len(message.body.delete_kb_doc_id):
            delete_files: List[FilesForIngestion] = message.body.delete_kb_doc_id
            reindexing_task = asyncio.create_task(
                self.ingest_data_ops.reindex_data(
                    files=delete_files, collection_name=message.body.collection_name
                )
            )
            tasks.append(reindexing_task)

        results = await asyncio.gather(*tasks, return_exceptions=True)
        return results

    def _bulk_update_document_statuses(
        self, results: List[Tuple[int, OperationStatusEnum]]
    ):
        if not results or len(results) == 0:
            logger.info("no document statues to update")
            return

        try:
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

            self.db.execute(stmt)
            logger.info("successfully updated document statuses")

        except Exception as e:
            logger.error(
                f"failedto perform bulk updates of document statuses: {e}",
                exc_info=True,
            )
            raise

    def process_message(self, message: ReceivedSqsMessage):
        logger.info("initiating processing message")
        try:
            all_results = asyncio.run(self._process_tasks_concurrently(message=message))
            logger.info("indexing and reindexing is completed")

            processed_items = itertools.chain.from_iterable(
                response for response in all_results if isinstance(response, list)
            )

            exceptions = [res for res in all_results if isinstance(res, Exception)]
            if exceptions:
                for exc in exceptions:
                    logger.error(
                        f"An exception occurred during concurrent execution: {exc}",
                        exc_info=exc,
                    )
            if processed_items:
                self._bulk_update_document_statuses(results=processed_items)

            stmt = (
                update(IngestionJob)
                .where(IngestionJob.id == message.body.ingestion_job_id)
                .values(op_status=OperationStatusEnum.SUCCESS)
            )

            self.db.execute(stmt)
            self.db.commit()
            logger.info("database updates committed successfully")
        except Exception as e:
            logger.error(
                f"an unexpected error occurred in process_message: {e}", exc_info=True
            )
            stmt = (
                update(IngestionJob)
                .where(IngestionJob.id == message.body.ingestion_job_id)
                .values(op_status=OperationStatusEnum.FAILED)
            )
            self.db.execute(stmt)
            self.db.commit()
            raise
