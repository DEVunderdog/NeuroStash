from typing import Optional

from langchain_community.document_loaders import (
    PyPDFLoader,
    TextLoader,
    UnstructuredWordDocumentLoader,
    UnstructuredPowerPointLoader,
    UnstructuredHTMLLoader,
    UnstructuredExcelLoader,
    JSONLoader,
    UnstructuredImageLoader,
    CSVLoader,
)
from langchain_core.document_loaders import BaseLoader
from pathlib import Path

import logging

logger = logging.getLogger(__name__)

LOADER_MAPPING = {
    ".pdf": {"loader": PyPDFLoader, "config": {}},
    ".docx": {
        "loader": UnstructuredWordDocumentLoader,
        "config": {"mode": "elements", "strategy": "hi_res"},
    },
    ".doc": {
        "loader": UnstructuredWordDocumentLoader,
        "config": {"mode": "elements", "strategy": "hi_res"},
    },
    ".pptx": {
        "loader": UnstructuredPowerPointLoader,
        "config": {"mode": "elements", "strategy": "hi_res"},
    },
    ".ppt": {
        "loader": UnstructuredPowerPointLoader,
        "config": {"mode": "elements", "strategy": "hi_res"},
    },
    ".xlsx": {"loader": UnstructuredExcelLoader, "config": {"mode": "elements"}},
    ".xls": {"loader": UnstructuredExcelLoader, "config": {"mode": "elements"}},
    ".html": {"loader": UnstructuredHTMLLoader, "config": {}},
    ".htm": {"loader": UnstructuredHTMLLoader, "config": {}},
    ".csv": {"loader": CSVLoader, "config": {"autodetect_encoding": True}},
    ".json": {
        "loader": JSONLoader,
        "config": {"jq_schema": "..", "text_content": False},
    },
    ".txt": {"loader": TextLoader, "config": {"encoding": "utf-8"}},
    ".jpeg": {"loader": UnstructuredImageLoader, "config": {}},
    ".jpg": {"loader": UnstructuredImageLoader, "config": {}},
    ".png": {"loader": UnstructuredImageLoader, "config": {}},
}

# To maintain utility of it and stateless design of the factory we use static methods
class DocumentLoaderFactory:
    @staticmethod
    def create_loader(file_path: str) -> Optional[BaseLoader]:
        ext = Path(file_path).suffix.lower()
        mapping = LOADER_MAPPING.get(ext)

        if not mapping:
            logger.warning(
                f"no loader found for file extension: {ext}. File will be skipped..."
            )
            return None

        loader_class = mapping["loader"]
        loader_config = mapping["config"]

        try:
            return loader_class(file_path, **loader_config)
        except Exception as e:
            logger.error(
                f"error instantiating loader for {file_path} with config {loader_config}",
                extra={"error": e},
                exc_info=True,
            )
            return None
