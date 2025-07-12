import logging
from langchain_text_splitters import (
    RecursiveCharacterTextSplitter,
    Language,
    TextSplitter,
)

logger = logging.getLogger(__name__)


class ContentSplitterFactory:
    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        self.default_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""],
        )

        self.markdown_splitter = RecursiveCharacterTextSplitter.from_language(
            language=Language.MARKDOWN,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

        self.splitter_mapping = {
            ".txt": self.default_splitter,
            ".pdf": self.default_splitter,
            ".docx": self.default_splitter,
            ".doc": self.default_splitter,
            ".pptx": self.default_splitter,
            ".ppt": self.default_splitter,
            ".xlsx": self.default_splitter,
            ".xls": self.default_splitter,
            ".html": self.default_splitter,
            ".htm": self.default_splitter,
            ".json": self.default_splitter,
            ".csv": self.default_splitter,
            ".md": self.markdown_splitter,
        }

    def create_splitter(self, ext: str) -> TextSplitter:
        splitter = self.splitter_mapping.get(ext)
        if splitter:
            logger.debug(f"using specific splitter for extension: {ext}")
            return splitter

        logger.debug(f"no specific splitter for {ext}, using default splitter")
        return self.default_splitter
