import secrets
import logging

logger = logging.getLogger(__name__)

key_size_bytes: int = 32


class KeyGenerationError(Exception):
    pass


def generate_symmetric_key() -> bytes:
    try:
        key = secrets.token_bytes(key_size_bytes)
        return key
    except Exception as e:
        logger.error(f"failed to generate symmetric key: {e}")
        raise KeyGenerationError(f"failed to generate symmetric key: {e}") from e
