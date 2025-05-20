from app.aws.client import AwsClientManager
from typing import Dict, Tuple, Optional
from app.token.token_models import (
    EncryptedKeyInfoArg,
    KeyInfo,
    JwtPayloadData,
    TokenData,
)
from app.core.config import settings
from datetime import timedelta, datetime, timezone
from jose import JWTError, jwt
from jose.constants import ALGORITHMS
import secrets
import threading
import logging
import os
import base64
import hmac
import hashlib

logger = logging.getLogger(__name__)


class KeyNotFoundError(Exception):
    pass


class TokenManager:
    def __init__(
        self,
        aws_client_manager: AwsClientManager,
        initial_encrypted_keys: Dict[int, EncryptedKeyInfoArg],
        active_key_id: int,
    ):
        if not initial_encrypted_keys:
            raise ValueError("no encrypted keys provided")
        if active_key_id not in initial_encrypted_keys:
            raise ValueError(
                f"active key id {active_key_id} not found in provided encrypted keys"
            )

        self._aws_client_manager = aws_client_manager
        self._lock = threading.Lock()
        self._active_key_config: Tuple[Dict[int, KeyInfo], int] = self._build_key_tuple(
            initial_encrypted_keys, active_key_id
        )

    def _decrypt_keys(
        self, encrypted_keys: Dict[int, EncryptedKeyInfoArg]
    ) -> Dict[int, KeyInfo]:
        decrypted_keys: Dict[int, KeyInfo] = {}
        for key_id, value in encrypted_keys.items():
            decrypted_key_bytes = self._aws_client_manager.decrypt_key(value.key_bytes)
            if not decrypted_key_bytes:
                raise RuntimeError(f"failed to decrypt symmetric key id {key_id}")
            decrypted_key_bytes[key_id] = KeyInfo(
                key=decrypted_key_bytes, expires_at=value.expires_at
            )
        return decrypted_keys

    def _build_key_tuple(
        self, encrypted_keys: Dict[int, EncryptedKeyInfoArg], active_key: int
    ) -> Tuple[Dict[int, KeyInfo], int]:
        decrypted_keys = self._decrypt_keys(encrypted_keys=encrypted_keys)

        return (decrypted_keys, active_key)

    def get_keys(self) -> Tuple[Dict[int, KeyInfo], int]:
        return self._active_key_config

    def update_active_keys(
        self, new_encrypted_keys: Dict[int, EncryptedKeyInfoArg], new_active_id: int
    ):
        new_keys = self._build_key_tuple(new_encrypted_keys, new_active_id)
        with self._lock:
            self._active_key_config = new_keys

    def create_access_token(
        self, payload_data: JwtPayloadData, expires_delta: Optional[timedelta] = None
    ) -> str:
        all_keys, active_key_id = self.get_keys()
        if active_key_id not in all_keys:
            raise KeyNotFoundError(
                "active key id not found in current keys configuration"
            )

        active_key_info = all_keys[active_key_id]
        if active_key_info.is_expired():
            raise RuntimeError("active key has expired")

        to_encode = payload_data.model_dump(exclude_unset=True)
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(
                minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
            )

        to_encode.update(
            {
                "exp": expire,
                "iss": settings.JWT_ISSUER,
                "aud": settings.JWT_AUDIENCE,
                "iat": datetime.now(timezone.utc),
                "jti": os.urandom(16).hex(),
            }
        )

        headers = {"kid", active_key_id}
        encoded_jwt = jwt.encode(
            to_encode,
            active_key_info.key.hex(),
            algorithm=ALGORITHMS.HS256,
            headers=headers,
        )
        return encoded_jwt

    def verify_token(self, token: str) -> Optional[TokenData]:
        try:
            unverified_headers = jwt.get_unverified_headers(token=token)
            kid = unverified_headers.get("kid")
            if not kid:
                raise RuntimeError("token missing 'kid' header")

            all_keys, _ = self.get_keys()

            key_for_verification = all_keys.get(kid)
            if not key_for_verification:
                raise KeyNotFoundError(f"key id {kid} not found for verification")

            if key_for_verification.is_expired():
                raise RuntimeError(
                    f"symmetric key {kid} for token verification has expired"
                )

            payload = jwt.decode(
                token=token,
                key=key_for_verification.key.hex(),
                algorithms=[ALGORITHMS.HS256],
                audience=settings.JWT_AUDIENCE,
                issuer=settings.JWT_ISSUER,
                options={"verify_aud": True, "verify_iss": True, "verify_exp": True},
            )
            return TokenData(**payload)
        except jwt.ExpiredSignatureError:
            logger.error("token has expired")
            raise
        except jwt.JWTClaimsError as e:
            logger.error(f"token claims error: {e}")
            raise
        except JWTError as e:
            logger.error(f"invalid token: {e}")
            raise

    def generate_api_key(self) -> Tuple[str, str]:
        all_keys, active_key_id = self.get_keys()

        random_bytes = secrets.token_bytes(24)
        random_bytes_b64 = (
            base64.urlsafe_b64encode(random_bytes).decode("utf-8").rstrip("=")
        )

        active_key_info = all_keys.get(active_key_id)
        if not active_key_info:
            raise KeyNotFoundError(f"key id {active_key_id} not found for verification")

        if active_key_info.is_expired():
            raise RuntimeError(f"key id {active_key_id} has been expired")

        data_to_hmac = f"{active_key_id}:{random_bytes_b64}".encode("utf-8")
        hmac_obj = hmac.new(active_key_info.key, data_to_hmac, hashlib.sha256)
        signature_bytes = hmac_obj.digest()
        signature_b64 = (
            base64.urlsafe_b64encode(signature_bytes).decode("utf-8").rstrip("=")
        )

        api_key = f"{random_bytes_b64}.{signature_b64}"

        return api_key, signature_b64

    def verify_api_key(self, api_key: str, key_hmac: str, kid: int) -> bool:
        parts = api_key.split(".")
        if len(parts) != 2:
            return False

        random_bytes_b64, signature_b64 = parts
        all_keys, _ = self.get_keys()

        key_info = all_keys.get(kid)
        if not key_info:
            logger.info("cannot find key info while verifying the api key")
            return False

        if key_info.is_expired():
            raise RuntimeError(
                f"symmetric key {kid} for token verification has expired"
            )

        data_to_hmac = f"{kid}:{random_bytes_b64}".encode("utf-8")

        expected_hmac_obj = hmac.new(key_info.key, data_to_hmac, hashlib.sha256)
        expected_signature_bytes = expected_hmac_obj.digest()

        try:
            client_signature_bytes = base64.urlsafe_b64decode(signature_b64 + "==")
            stored_hmac_bytes = base64.urlsafe_b64decode(key_hmac + "==")
        except Exception as e:
            logger.error(f"error while ecoding signature and provided key hmac: {e}")
            return False

        return hmac.compare_digest(
            expected_signature_bytes, client_signature_bytes
        ) and hmac.compare_digest(expected_signature_bytes, stored_hmac_bytes)
