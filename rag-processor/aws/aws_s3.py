import boto3
import botocore

from log import logger


class S3DownloadError(Exception):
    pass


class aws_object_storage:
    def __init__(self, bucket_name, region_name: str):
        self.s3_client = boto3.client("s3", region_name=region_name)
        self.bucket_name = bucket_name

    def download_file(self, object_key: str, local_file_path: str) -> bool:
        try:
            self.s3_client.download_file(self.bucket_name, object_key, local_file_path)
            logger.info(
                f"File s3://{self.bucket_name}/{object_key} downloaded successfully to {local_file_path}"
            )
            return True

        except botocore.exceptions.ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")
            if error_code == "404" or error_code == "NoSuchKey":
                msg = f"The object '{object_key}' does not exist in bucket '{self.bucket_name}'"
                logger.error(msg)
                raise S3DownloadError(msg) from e
            elif error_code == "NoSuchBucket":
                msg = f"The bucket '{self.bucket_name}' does not exist or you lack permissions"
                logger.error(msg)
                raise S3DownloadError(msg) from e
            else:
                msg = f"An unexpected S3 ClientError occurred during download: {e}"
                logger.error(msg)
                raise S3DownloadError(msg) from e
        except FileNotFoundError:
            msg = (
                f"the local directory for path '{self.local_file_path}' does not exists"
            )
            logger.error(msg)
            raise S3DownloadError(msg)

        except Exception as e:
            msg = f"an unexpected error occurred during download: {e}"
            logger.error(msg=msg)
            raise S3DownloadError(msg)
