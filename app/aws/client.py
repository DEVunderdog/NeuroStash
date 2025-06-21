import boto3
import logging
import os
from botocore.exceptions import ClientError
from typing import Optional, List
from app.core.config import Settings
from app.constants.content_type import S3_CONTENT_TYPE_MAP

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
        self._s3_client = None

    @property
    def kms(self):
        if self._kms_client is None:
            self._kms_client = self.session.client("kms")
        return self._kms_client

    @property
    def s3(self):
        if self._s3_client is None:
            self._s3_client = self.session.client("s3")
        return self._s3_client

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

    def generate_presigned_upload_url(
        self, object_key: str, content_type: Optional[str] = None
    ) -> Optional[str]:
        if not self.s3:
            logger.error("s3 client not configured for generating presigned url")
            return None

        try:
            params = {"Bucket": self.settings.AWS_BUCKET_NAME, "Key": object_key}
            if content_type:
                params["ContentType"] = content_type

            response = self.s3.generate_presigned_url(
                "put_object",
                Params=params,
                ExpiresIn=self.settings.AWS_PRESIGNED_URL_EXP,
            )
            return response
        except ClientError as e:
            logger.error("error generating presigend upload url", exc_info=e)
            return None

    def extract_content_type(self, filename: str) -> Optional[str]:
        if not filename or not isinstance(filename, str):
            return None

        _, extension = os.path.splitext(filename)

        if not extension:
            return None

        return S3_CONTENT_TYPE_MAP.get(extension.lower())

    def individual_delete_object(self, object_key: str) -> bool:
        try:
            response = self.s3.delete_object(
                Bucket=self.settings.AWS_BUCKET_NAME, Key=object_key
            )

            if response["ResponseMetadata"]["HTTPStatusCode"] == 204:
                return True
            else:
                logger.error(
                    f"received an unexpected status code: {response['ResponseMetadata']['HTTPStatusCode']}"
                )
        except ClientError as e:
            logger.error("error deleting object due to ClientError", exc_info=e)
            raise
        except Exception as e:
            logger.error("error deleting object due to exception", exc_info=e)
            raise

    def multiple_delete_objects(self, object_keys: List[str]):
        try:
            objects_to_delete = [{"Key": key} for key in object_keys]

            response = self.s3.delete_objects(
                Bucket=self.settings.AWS_BUCKET_NAME,
                Delete={"Objects": objects_to_delete, "Quiet": False},
            )

            if "Errors" in response and len(response["Errors"]) > 0:
                logger.error("error occurred during batch deletion")
                for error in response["Errors"]:
                    logger.error(
                        f"Key: {error['Key']}, Code: {error['Code']}, Message: {error['Message']}"
                    )
        except ClientError as e:
            logger.error("error delete objects from bucket due ClientError", exc_info=e)
            raise
        except Exception as e:
            logger.error(
                "error deleting object from bucket exception occurred", exc_info=e
            )
            raise

    def object_exists(self, object_key: str) -> bool:
        try:
            self.s3.head_object(Bucket=self.settings.AWS_BUCKET_NAME, Key=object_key)
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                return False
            raise
