import logging
from langchain_openai import OpenAIEmbeddings
from typing import List
from app.core.config import Settings
from app.constants.models import OPENAI_EMBEDDINGS_MODEL
from app.milvus.client import MilvusOps

logger = logging.getLogger(__name__)


class SearchOps:
    def __init__(self, settings: Settings):
        self.settings: Settings = settings
        self.embeddings = OpenAIEmbeddings(
            model=OPENAI_EMBEDDINGS_MODEL, api_key=self.settings.OPENAI_KEY
        )
        self.milvus_ops = MilvusOps(settings=self.settings)

    def __generate_query_embeddings(self, query: str) -> List[float]:
        try:
            generated_embeddings = self.embeddings.embed_query(text=query)
            return generated_embeddings
        except Exception as e:
            logger.error(
                f"error generating embeddings for user query: {e}", exc_info=True
            )
            raise

    def _perform_hybrid_search(self, collection_name:str, query: str, limit: int):
        try:
            generated_embeddings = self.__generate_query_embeddings(query=query)
            search_response = self.milvus_ops.hybrid_search(collection_name=collection_name, query=query, generated_embeddings=generated_embeddings)

            return search_response
        except Exception as e:
            logger.error(f"error performing hybrid search: {e}", exc_info=True)
            raise
