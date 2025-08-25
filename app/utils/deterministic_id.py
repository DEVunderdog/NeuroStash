import uuid

def generate_deterministic_uuid(name: str, id: int) -> str:
    custom_entity = f"{name}:{id}"

    deterministic_id = uuid.uuid5(uuid.NAMESPACE_DNS, custom_entity)

    return str(deterministic_id)

