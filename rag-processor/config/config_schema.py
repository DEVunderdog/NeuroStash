from pydantic import BaseModel, SecretStr


class QueueSettings(BaseModel):
    queue_name: str
    queue_url: str
    queue_prefetch_count: int


class CloudSettings(BaseModel):
    bucket_name: str
    region_name: str
    access_key: SecretStr
    secret_key: SecretStr


class AppSettings(BaseModel):
    temp_path: str
    queue: QueueSettings
    aws_cloud: CloudSettings

    model_config = {"extra": "forbid"}
