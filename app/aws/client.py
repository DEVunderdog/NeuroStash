import boto3
import logging
from botocore.exceptions import ClientError
from typing import Optional
from app.core.config import Settings

logger = logging.getLogger(__name__)


class AwsClientManager:
    def __init__(
        self,
        settings: Settings,
    ):
        self.settings = settings
        self.session_kwargs = {"region_name": self.settings.AWS_REGION}
        self.kms_key_id = settings.AWS_KMS_KEY_ID

        if self.settings.AWS_ACCESS_KEY_ID and self.settings.AWS_SECRET_ACCESS_KEY:
            logger.info("use static aws credentials for development")
            self.session_kwargs["aws_access_key_id"] = self.settings.AWS_ACCESS_KEY_ID
            self.session_kwargs["aws_secret_access_key"] = (
                self.settings.AWS_SECRET_ACCESS_KEY
            )
        else:
            logger.info("using default aws credentials provider")

        self.session = boto3.Session(**self.session_kwargs)
        self._kms_client = None

    @property
    def kms(self):
        if self._kms_client is None:
            self._kms_client = self.session.client("kms")
        return self._kms_client

    def encrypt_key(self, key_blob: bytes) -> Optional[bytes]:
        if not self.kms or not self.kms_key_id:
            logger.error("kms client or kms key id not configured for encryption")
            return None
        try:
            response = self.kms.encrypt(
                KeyId=self.settings.AWS_KMS_KEY_ID, Plaintext=key_blob
            )
            return response.get("CiphertextBlob")
        except ClientError as e:
            logger.error(f"error encrypting key with kms key id: {e}")
            return None

    def decrypt_key(self, ciphertext_blob: bytes) -> Optional[bytes]:
        if not self.kms or not self.kms_key_id:
            logger.error("kms client or kms key id not configured for encryption")
            return None
        try:
            response = self.kms.decrypt(
                CiphertextBlob=ciphertext_blob, KeyId=self.settings.AWS_KMS_KEY_ID
            )
            return response.get("Plaintext")
        except ClientError as e:
            logger.error(f"error decrypting key: {e}")
            return None
