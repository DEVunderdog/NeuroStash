import os
import asyncio
import aio_pika
import aio_pika.abc
import json
import tempfile

from aws.aws_s3 import aws_object_storage, S3DownloadError
from log import logger


class Processor:
    def __init__(
        self,
        aws_region: str,
        download_temp_dir: str,
        bucket_name: str,
        temp_dir: str
    ):
        self.aws_region = aws_region
        self.download_temp_dir = download_temp_dir
        self.bucket_name = bucket_name
        self.temp_dir = temp_dir

        os.makedirs(self.temp_dir, exist_ok=True)

        self.aws_storage = aws_object_storage(
            bucket_name=self.bucket_name, region_name=self.aws_region
        )

    async def process_download_message(
        self, message: aio_pika.abc.AbstractIncomingMessage
    ):
        try:
            body = message.body.decode()
            logger.info(f"received message: {body}")
            data = json.loads(body)

            if (
                not isinstance(data, dict)
                or "object_key" not in data
                or "id" not in data
            ):
                err_msg = f"invalid message format received: {body}"
                logger.error(err_msg)
                raise ValueError(err_msg)

            object_key = data["object_key"]
            object_id = data["id"]

            with tempfile.TemporaryDirectory(
                dir=self.download_temp_dir, prefix=f"msg_{id}"
            ) as temp_dir:
                filename = object_key.split("/")[-1]
                local_file_path = os.path.join(temp_dir, filename)

                logger.info("preparing to download")

                try:
                    await asyncio.to_thread(
                        self.aws_storage.download_file, object_key, local_file_path
                    )
                    # TODO: Process the file
                except S3DownloadError as e:
                    logger.error(f"failed to download '{object_key}'. Error: {e}")
                    raise
                except Exception as e:
                    logger.error(
                        f"error processing download process for '{object_key}'. Error: {e}",
                        exc_info=True,
                    )
                    raise
        except json.JSONDecodeError:
            logger.error(f"failed to decode JSON message body: {message.body}")
            raise
        except Exception as e:
            logger.error(f"generice error in message processor: {e}", exc_info=True)
            raise
