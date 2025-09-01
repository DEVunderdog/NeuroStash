from dataclasses import dataclass
from typing import Optional, List, Dict


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


auto_generated_fields = {"text_sparse_vector"}
