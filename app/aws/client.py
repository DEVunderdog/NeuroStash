import boto3
import logging
import os
from botocore.exceptions import ClientError, NoCredentialsError, BotoCoreError
from typing import Optional, List
from app.core.config import Settings
from app.constants.content_type import S3_CONTENT_TYPE_MAP

logger = logging.getLogger(__name__)


class S3OperationError(Exception):
    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        object_key: Optional[str] = None,
    ):
        self.error_code = error_code
        self.object_key = object_key
        super().__init__(message)


class S3AccessDeniedError(S3OperationError):
    pass


class S3ObjectNotFoundError(S3OperationError):
    pass


class S3ConfigurationError(S3OperationError):
    pass


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

    def _handle_client_error(
        self, error: ClientError, operation: str, object_key: Optional[str] = None
    ) -> None:
        error_code = error.response.get("Error", {}).get("Code", "Unknown")
        error_message = error.response.get("Error", {}).get("Message", str(error))

        logger.error(
            f"S3 {operation} failed - Code: {error_code}, Message: {error_message}, Key: {object_key}"
        )

        if error_code == "AccessDenied":
            raise S3AccessDeniedError(
                f"Access denied for S3 {operation}: {error_message}",
                error_code=error_code,
                object_key=object_key,
            )
        elif error_code == "NoSuchKey" or error_code == "404":
            raise S3ObjectNotFoundError(
                f"S3 object not found during {operation}: {error_message}",
                error_code=error_code,
                object_key=object_key,
            )
        else:
            raise S3OperationError(
                f"S3 {operation} failed: {error_message}",
                error_code=error_code,
                object_key=object_key,
            )

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
            self._handle_client_error(e, "presigned URL generation", object_key)
        except (NoCredentialsError, BotoCoreError) as e:
            logger.error(
                f"AWS configuration error during presigned URL generation: {e}"
            )
            raise S3ConfigurationError(f"AWS configuration error: {e}")
        except Exception as e:
            logger.error(
                f"Unexpected error generating presigned URL: {e}", exc_info=True
            )
            raise S3OperationError(f"Unexpected error generating presigned URL: {e}")

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
            status_code = response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            if status_code == 204:
                return True
            else:
                error_msg = f"Unexpected status code {status_code} for object deletion: {object_key}"
                logger.error(error_msg)
                raise S3OperationError(error_msg, object_key=object_key)

        except ClientError as e:
            if e.response.get("Error", {}).get("Code") == "NoSuchKey":
                logger.warning(f"Object not found for deletion: {object_key}")
                return True  # Consider deletion successful if object doesn't exist
            self._handle_client_error(e, "individual object deletion", object_key)
        except Exception as e:
            logger.error("error deleting object due to exception", exc_info=e)
            raise S3OperationError(
                f"Unexpected error deleting object: {e}", object_key=object_key
            )

    def multiple_delete_objects(self, object_keys: List[str]):
        try:
            objects_to_delete = [{"Key": key} for key in object_keys]

            response = self.s3.delete_objects(
                Bucket=self.settings.AWS_BUCKET_NAME,
                Delete={"Objects": objects_to_delete, "Quiet": False},
            )

            deleted_objects = response.get("Deleted", [])
            errors = response.get("Errors", [])

            result = {
                "deleted_count": len(deleted_objects),
                "deleted_objects": [obj.get("Key") for obj in deleted_objects],
                "error_count": len(errors),
                "errors": errors,
            }

            # Log results
            logger.info(
                f"Batch deletion completed: {result['deleted_count']} deleted, {result['error_count']} errors"
            )

            if errors:
                error_details = []
                for error in errors:
                    error_msg = f"Key: {error['Key']}, Code: {error['Code']}, Message: {error['Message']}"
                    logger.error(f"Batch deletion error - {error_msg}")
                    error_details.append(error_msg)
                raise S3OperationError(
                    f"S3 batch deletion failed for {len(errors)} objects: {'; '.join(error_details)}"
                )
            return result
        except ClientError as e:
            self._handle_client_error(e, "batch object deletion")
        except S3OperationError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error during batch deletion: {e}", exc_info=True)
            raise S3OperationError(f"Unexpected error during batch deletion: {e}")

    def object_exists(self, object_key: str) -> bool:
        try:
            self.s3.head_object(Bucket=self.settings.AWS_BUCKET_NAME, Key=object_key)
            return True
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")
            if error_code == "404" or error_code == "NoSuchKey":
                return False
            self._handle_client_error(e, "object existence check", object_key)
        except Exception as e:
            logger.error(
                f"Unexpected error checking object existence {object_key}: {e}",
                exc_info=True,
            )
            raise S3OperationError(
                f"Unexpected error checking object existence: {e}",
                object_key=object_key,
            )
