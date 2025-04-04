import boto3
import botocore

from log import logger

class aws_object_storage:
    def __init__(self,  local_file_path, bucket_name, region_name: str):
        self.s3_client = boto3.client('s3', region_name=region_name)
        self.local_file_path = local_file_path
        self.bucket_name = bucket_name

    def download_file(self, object_key: str) -> bool:
        try:
            self.s3_client.download_file(self.bucket_name, object_key, self.local_file_path)
            logger.info("file downloaded successfully")
            return True
        
        except botocore.exceptions.ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")
            if error_code == "404" or error_code == "NoSuchKey":
                logger.error(f"The object '{object_key}' does not exists in bucket")
            elif error_code == "NoSuchBucket":
                logger.error(f"The bucket '{self.bucket_name}' does not exists or you lack permissions")
            else:
                logger.error(f"an unexpected s3 ClientError occurred: {e}")
            return False
        except FileNotFoundError:
            logger.error(f"the local directory for path '{self.local_file_path}' does not exists")
            return False
        except Exception as e:
            logger.error(f"an unexpected error occurred during download: {e}")
            return False