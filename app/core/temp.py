import os
import tempfile

def get_system_temp_file_path(filename: str) -> str:
    return os.path.join(tempfile.gettempdir(), filename)
