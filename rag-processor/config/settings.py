import yaml
from pathlib import Path
from config.config_schema import AppSettings
from log import logger
from pydantic import ValidationError
from typing import Optional


class Settings:
    _loaded_settings: Optional[AppSettings] = None
    _config_path: Optional[Path] = None

    def __init__(self, config_path: Path):
        if Settings._config_path is None:
            Settings._config_path = config_path
        elif Settings._config_path != config_path:
            logger.warning(
                f"settings already initialized with pat {Settings._config_path}. Ignoring new path {config_path}"
            )

        if Settings._loaded_settings is None:
            Settings._loaded_settings = self._load_config(Settings._config_path)

    def _load_config(self, config_path: Path) -> AppSettings:
        if not config_path.exists():
            raise FileNotFoundError(
                f"default configuration file not found: {config_path}"
            )

        try:
            with open(config_path, "r") as f:
                config_data = yaml.safe_load(f)
                if config_data is None:
                    logger.error("nothing found from provided config file")
                    raise ValueError
        except yaml.YAMLError as e:
            raise yaml.YAMLError(f"error parsing yaml file {config_path}: {e}")
        except Exception as e:
            raise Exception(f"error reading file {config_path}: {e}")

        try:
            settings = AppSettings(**config_data)
            print("configuration loaded and validated successfully")
            return settings
        except ValidationError as e:
            logger.error(f"configuration validation error failed: {e}")
            raise

    def get_settings(self):
        if self._loaded_settings is None:
            raise ValueError(
                "settings have not been loaded. Initialze settings class first."
            )
        return self._loaded_settings
