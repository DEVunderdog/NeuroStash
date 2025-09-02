import logging
from app.aws.client import AwsClientManager
from app.core.db import SessionLocal
from app.dao.file_dao import conflicted_docs, cleanup_docs

logger = logging.getLogger(__name__)


class FileCleaner:
    def __init__(self, aws_client: AwsClientManager):
        self.aws_client: AwsClientManager = aws_client

    async def file_cleanup_worker(self):
        try:
            async with SessionLocal() as db:
                conflicting_docs = await conflicted_docs(db=db)
                if not conflicting_docs:
                    return

                to_be_unlocked = []
                to_be_deleted = []

                for doc in conflicting_docs:
                    exists: bool = self.aws_client.object_exists(
                        object_key=doc.object_key
                    )
                    if not exists:
                        to_be_deleted.append(doc.id)
                    else:
                        to_be_unlocked.append(doc.id)

                if to_be_deleted or to_be_unlocked:
                    await cleanup_docs(
                        db=db,
                        to_be_unlocked=to_be_unlocked,
                        to_be_deleted=to_be_deleted,
                    )
        except Exception as e:
            logger.error(f"error cleaning up files: {e}")
            raise
