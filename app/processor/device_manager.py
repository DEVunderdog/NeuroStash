import torch
import logging
import enum
import psutil

logger = logging.getLogger(__name__)


class DeviceType(enum.Enum):
    GPU = "cuda"
    CPU = "cpu"


class DeviceManager:
    @staticmethod
    def get_optimal_device() -> DeviceType:
        if torch.cuda.is_available():
            gpu_memory = torch.cuda.get_device_properties(0).total_memory / (1024 * 3)
            logger.info(f"GPU available with {gpu_memory:.2f} GB memory")
            return DeviceType.GPU
        else:
            cpu_count = psutil.cpu_count()
            logger.info(f"using CPU with {cpu_count} cores")
            return DeviceType.CPU

    @staticmethod
    def optimize_batch_size(device: DeviceType, base_batch_size: int = 32) -> int:
        if device == DeviceType.GPU:
            gpu_memory = torch.cuda.get_device_properties(0).total_memory / (1024**3)
            if gpu_memory < 4:
                return max(8, base_batch_size // 4)
            elif gpu_memory < 8:
                return max(16, base_batch_size // 2)
            else:
                return base_batch_size
        elif device == DeviceType.CPU:
            cpu_count = psutil.cpu_count()
            return min(base_batch_size, cpu_count * 2)
        return base_batch_size
