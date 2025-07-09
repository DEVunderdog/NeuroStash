import logging
import uuid
from app.aws.client import AwsClientManager
from app.core.config import Settings
from app.core.temp import get_system_temp_file_path
from app.dao.models import ReceivedSqsMessage
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class ProcessorManager:
    def __init__(
        self, aws_client_manager: AwsClientManager, settings: Settings, db: Session
    ):
        self.aws_client_manager: AwsClientManager = aws_client_manager
        self.settings: Settings = settings
        self.db: Session = db

    def process_message(self, message: ReceivedSqsMessage, db: Session):
        for object in message.body.new_object_keys:
            unique_identifier = uuid.uuid4()
            temp_file = get_system_temp_file_path(unique_identifier)
            try:
                self.aws_client_manager.download_file(
                    object_key=object, temp_file_path=temp_file
                )
            except Exception as e:
                logger.error(
                    "error downloading file", extra={"error": {e}}, exc_info=True
                )
                raise
