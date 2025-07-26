from langchain_experimental.text_splitter import SemanticChunker
from langchain_openai import OpenAIEmbeddings
from app.processor.splitters import SentenceSplitter
from app.core.config import Settings
from app.constants.models import OPENAI_EMBEDDINGS_MODEL
from app.constants.globals import GRADIENT_BREAKPOINT
from typing import List


class CustomSemanticChunker(SemanticChunker):
    def __init__(self, settings: Settings):
        self.sentence_splitters = SentenceSplitter()
        self.embeddings = OpenAIEmbeddings(
            model=OPENAI_EMBEDDINGS_MODEL, api_key=settings.OPENAI_KEY,
        )
        super().__init__(
            embeddings=self.embeddings,
            breakpoint_threshold_type=GRADIENT_BREAKPOINT,
        )

    def _get_single_sentences_list(self, text: str) -> List[str]:
        sentences = self.sentence_splitters.split_text(text=text)
        return sentences
