from dataclasses import dataclass
from app.processor.device_manager import DeviceType

@dataclass
class EmbeddingConfig:
    model_name: str
    batch_size: int
    max_seq_length: int
    device: DeviceType
