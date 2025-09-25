import uuid

def generate_chunk_id(file_name: str, parent_id: int, chunk_index: int) -> str:
    unique_name = f"{file_name}::parent:{parent_id}::chunk:{chunk_index}"

    deterministic_id = uuid.uuid5(uuid.NAMESPACE_DNS, unique_name)

    return str(deterministic_id)