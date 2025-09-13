from dataclasses import dataclass
from typing import Optional, List, Dict
from pydantic import BaseModel


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
    hnsw_ef: int
    sparse_drop_ratio: float
    reranker_smoothing_parameter: int


auto_generated_fields = {"text_sparse_vector"}
