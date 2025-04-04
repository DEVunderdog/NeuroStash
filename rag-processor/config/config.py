from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(case_sensitive=False)

    aws_bucket_name: str
    aws_access_key_id: str
    aws_secret_access_key: str
    aws_region: str

settings = Settings()