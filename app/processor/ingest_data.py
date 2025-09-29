import asyncio
import logging
import uuid
from pathlib import Path
from typing import List, Sequence, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from app.constants.models import OPENAI_EMBEDDINGS_MODEL
from app.aws.client import AwsClientManager
from app.constants.globals import MAX_CONCURRENT_PROVISIONER
from app.core.file_extension_validation import is_valid_file_extension
from app.core.temp import get_system_temp_file_path
from app.dao.models import FileForIngestion
from app.dao.schema import OperationStatusEnum, ParentChunkedDoc
from app.milvus.client import MilvusOps
from app.milvus.entity import CollectionSchemaEntity
from app.processor.loaders import DocumentLoaderFactory
from app.processor.parent_document_retriever import ParentDocumentRetriever
from app.utils.deterministic_id import generate_chunk_id
from app.core.config import Settings
from app.dao.ingestion_dao import create_parent_chunk, delete_parent_chunk
from app.core.db import SessionLocal


logger = logging.getLogger(__name__)


class InvalidFileExtension(Exception):
    pass


class DocumentNotLoaded(Exception):
    pass


class DocumentNotChunked(Exception):
    pass


class IngestData:
    def __init__(
        self,
        settings: Settings,
        aws_client_manager: AwsClientManager,
        milvus_ops: MilvusOps,
    ):
        self.embeddings = OpenAIEmbeddings(
            model=OPENAI_EMBEDDINGS_MODEL, api_key=settings.OPENAI_KEY
        )
        self.aws_client = aws_client_manager
        self.milvus_ops = milvus_ops
        self.semantic_chunker = ParentDocumentRetriever(embeddings=self.embeddings)
        self.max_concurrency = MAX_CONCURRENT_PROVISIONER

    async def index_data(
        self,
        files: List[FileForIngestion],
        user_id: int,
        category: str,
        collection_name: str,
    ) -> List[Tuple[int, OperationStatusEnum]]:
        semaphore = asyncio.Semaphore(self.max_concurrency)
        results = []

        async def indexing_with_limit(
            file: FileForIngestion,
            user_id: int,
            category: int,
            collection_name: str,
            db: AsyncSession,
        ):
            async with semaphore:
                try:
                    await self._upsert_into_milvus(
                        file=file,
                        user_id=user_id,
                        category=category,
                        collection_name=collection_name,
                        db=db,
                    )
                    logger.info(
                        "successfully processed and inserted into milvus collection"
                    )
                    return (file.kb_doc_id, OperationStatusEnum.SUCCESS)
                except Exception as e:
                    logger.error(
                        f"error processing file and inserting into collection: {e}",
                        exc_info=True,
                    )
                    return (file.kb_doc_id, OperationStatusEnum.FAILED)

        exceptions = None
        try:
            async with asyncio.TaskGroup() as tg:
                async with SessionLocal() as db:
                    tasks = [
                        tg.create_task(
                            indexing_with_limit(
                                file=item,
                                user_id=user_id,
                                category=category,
                                collection_name=collection_name,
                                db=db,
                            )
                        )
                        for item in files
                    ]
            for task in tasks:
                results.append(task.result())
        except* Exception as eg:
            error_msg = f"indexing finished with {len(eg.exceptions)} errors"
            logger.error(error_msg, exc_info=True)
            exceptions = eg

        if exceptions:
            raise

        logger.info("successfully index the data")
        return results

    async def reindex_data(
        self, files: List[FileForIngestion], collection_name: str
    ) -> List[Tuple[int, OperationStatusEnum]]:
        semaphore = asyncio.Semaphore(self.max_concurrency)
        results = []

        async def reindexing_with_limit(
            file: FileForIngestion, collection_name: str, db: AsyncSession
        ):
            async with semaphore:
                try:
                    self._process_reindexing(
                        file=file, collection_name=collection_name, db=db
                    )
                    logger.info("successfully deleted from milvus")
                    return (file.kb_doc_id, OperationStatusEnum.SUCCESS)
                except Exception as e:
                    logger.error(
                        f"error processing file for reindexing and deletion from milvus: {e}",
                        exc_info=True,
                    )
                    return (file.kb_doc_id, OperationStatusEnum.FAILED)

        exceptions = None
        try:
            async with asyncio.TaskGroup() as tg:
                async with SessionLocal() as db:
                    tasks = [
                        tg.create_task(
                            reindexing_with_limit(
                                file=item, collection_name=collection_name, db=db
                            )
                        )
                        for item in files
                    ]

            for task in tasks:
                results.append(task.result())
        except* Exception as eg:
            error_msg = f"reindexing finished with {len(eg.exceptions)} errors"
            logger.error(error_msg, exc_info=True)
            exceptions = eg

        if exceptions:
            raise

        logger.info("successfully reindexed the data")
        return results

    def _download_temp_file(self, object_key: str) -> str:
        try:
            unique_identifier = uuid.uuid4()
            original_extension = Path(object_key).suffix

            valid = is_valid_file_extension(extension=original_extension)
            if not valid:
                raise InvalidFileExtension(
                    "invalid file extension, file cannot be processed"
                )

            temp_file = get_system_temp_file_path(
                f"{unique_identifier}{original_extension}"
            )

            self.aws_client.download_file(
                object_key=object_key, temp_file_path=temp_file
            )

            return temp_file
        except Exception as e:
            logger.error(f"error downloading file: {e}", exc_info=True)
            raise

    async def _process_file(self, file: FileForIngestion) -> List[dict]:
        try:
            temp_file = self._download_temp_file(object_key=file.object_key)
            loader = DocumentLoaderFactory.create_loader(file_path=temp_file)
            if not loader:
                raise DocumentNotLoaded("cannot load the document from temporary file")
            document = loader.load()
            chunked_docs = self.semantic_chunker.transform_documents(documents=document)

            if not chunked_docs or len(chunked_docs) == 0:
                raise DocumentNotChunked("none data chunked from the documents")

            for chunked_doc in chunked_docs:
                child_doc = chunked_doc["child_doc"]
                child_doc_embeddings = await self._get_concurrent_embeddings(
                    documents=child_doc,
                    embedding_model=self.embeddings,
                )
                chunked_doc["child_doc_embeddings"] = child_doc_embeddings

            return chunked_docs

        except Exception as e:
            logger.error(f"error processing file: {e}", exc_info=e)
            raise

    async def _get_concurrent_embeddings(
        self,
        documents: Sequence[Document],
        embedding_model: OpenAIEmbeddings,
        batch_size: int = 2048,
    ) -> List[List[float]]:
        try:
            document_texts = [doc.page_content for doc in documents]

            text_batches = [
                document_texts[i : i + batch_size]
                for i in range(0, len(document_texts), batch_size)
            ]

            tasks = [embedding_model.aembed_documents(batch) for batch in text_batches]
            batch_embeddings = await asyncio.gather(*tasks)

            all_embeddings = [
                embedding for batch in batch_embeddings for embedding in batch
            ]

            return all_embeddings
        except Exception as e:
            logger.error(f"error calculating embeddings: {e}", exc_info=True)
            raise

    async def _upsert_into_milvus(
        self,
        file: FileForIngestion,
        user_id: int,
        category: int,
        collection_name: str,
        db: AsyncSession,
    ):
        try:
            chunked_docs = await self._process_file(file=file)

            data_for_milvus: List[CollectionSchemaEntity] = []
            parent_doc_objects: List[ParentChunkedDoc] = []

            for chunked_doc in chunked_docs:
                parent_doc_obj = await create_parent_chunk(
                    db=db,
                    document_id=file.doc_id,
                    chunk=chunked_doc["parent_doc"].page_content,
                )
                db.add(parent_doc_obj)
                parent_doc_objects.append(parent_doc_obj)

            await db.flush(parent_doc_objects)

            for i, chunked_doc in enumerate(chunked_docs):
                parent_id = parent_doc_objects[i].id
                if parent_id is None:
                    raise Exception(f"Parent doc ID not generated for chunk {i}")
                for index, (doc, embedding) in enumerate(
                    zip(chunked_doc["child_doc"], chunked_doc["child_doc_embeddings"])
                ):
                    id = generate_chunk_id(
                        file_name=file.file_name, parent_id=parent_id, chunk_index=index
                    )
                    entity = CollectionSchemaEntity(
                        id=id,
                        text_dense_vector=embedding,
                        text_content=doc.page_content,
                        object_key=file.object_key,
                        category=category,
                        file_name=file.file_name,
                        user_id=user_id,
                        file_id=file.kb_doc_id,
                        parent_id=parent_id,
                    )
                    data_for_milvus.append(entity)

            if data_for_milvus:
                self.milvus_ops.upsert_into_collection(
                    collection_name=collection_name, data=data_for_milvus
                )

            await db.commit()
        except Exception as e:
            logger.error(f"error inserting into milvus: {e}", exc_info=True)
            await db.rollback()
            raise

    async def _process_reindexing(
        self, db: AsyncSession, file: FileForIngestion, collection_name: str
    ):
        try:
            expr = f"file_id == {file.kb_doc_id}"
            self.milvus_ops.delete_entities_record(
                collection_name=collection_name, filter=expr
            )
            await delete_parent_chunk(db=db, document_id=file.doc_id)
            await db.commit()
        except Exception as e:
            logger.error(
                f"error deleting entities record in milvus: {e}", exc_info=True
            )
            await db.rollback()
            raise
