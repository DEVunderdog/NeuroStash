from dataclasses import dataclass
from typing import Optional, List, Dict


@dataclass
class CollectionSchemaEntity:
    id: str
    text_dense_vector: List[float]
    text_sparse_vector: Optional[Dict[int, float]] = None
    category: str
    object_key: str
    file_name: str
    text_content: str
    user_id: int
    file_id: int


auto_generated_fields = {"text_sparse_vector"}
