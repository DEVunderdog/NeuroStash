from dataclasses import dataclass
from typing import Optional, List, Dict
from pydantic import BaseModel
from app.constants.globals import (
    HNSW_EF,
    SPARSE_DROP_RATIO,
    RERANKER_SMOOTHING_PARAMETERS,
)


@dataclass
class CollectionSchemaEntity:
    id: str
    text_dense_vector: List[float]
    category: str
    object_key: str
    file_name: str
    text_content: str
    user_id: int
    file_id: int
    text_sparse_vector: Optional[Dict[int, float]] = None


class SearchingConfiguration(BaseModel):
    hnsw_ef: int = 10
    sparse_drop_ratio: float = 0.2
    reranker_smoothing_parameter: int = 60


auto_generated_fields = {"text_sparse_vector"}


def get_global_searching_configuration() -> SearchingConfiguration:
    return SearchingConfiguration(
        hnsw_ef=HNSW_EF,
        sparse_drop_ratio=SPARSE_DROP_RATIO,
        reranker_smoothing_parameter=RERANKER_SMOOTHING_PARAMETERS,
    )
