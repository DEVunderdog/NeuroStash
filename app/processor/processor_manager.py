import logging
import uuid
from app.aws.client import AwsClientManager
from app.core.config import Settings
from app.core.temp import get_system_temp_file_path
from app.dao.models import ReceivedSqsMessage
from sqlalchemy.orm import Session
from pathlib import Path
from app.core.file_extension_validation import is_valid_file_extension
from app.processor.loaders import DocumentLoaderFactory
from app.processor.semantic_chunker import CustomSemanticChunker

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
        self.semantic_chunker: CustomSemanticChunker = CustomSemanticChunker(
            settings=settings
        )

    def process_message(self, message: ReceivedSqsMessage, db: Session):
        for object_key in message.body.new_object_keys:
            unique_identifier = uuid.uuid4()
            original_extension = Path(object_key).suffix

            valid = is_valid_file_extension(extension=original_extension)
            if not valid:
                raise InvalidFileExtension(
                    "invalid file extension cannnot be processed"
                )

            temp_file = get_system_temp_file_path(
                f"{unique_identifier}{original_extension}"
            )

            try:
                self.download_temp_file(object_key=object, temp_file_path=temp_file)
                loader = DocumentLoaderFactory.create_loader(file_path=temp_file)
                if not loader:
                    continue
                documents = loader.load()
                chunked_documents = self.semantic_chunker.transform_documents(
                    documents=documents
                )

            except Exception as e:
                logger.error(
                    "error processing message", extra={"error": {e}}, exc_info=True
                )
                raise

    def download_temp_file(self, object_key: str, temp_file_path: str):
        try:
            self.aws_client_manager.download_file(
                object_key=object_key, temp_file_path=temp_file_path
            )
        except Exception as e:
            logger.error("error downloading file", extra={"error": {e}}, exc_info=True)
            raise
