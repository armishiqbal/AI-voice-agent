import base64
import hashlib

from cryptography.fernet import Fernet

from app.core.config import settings


class ContactCipher:
    def __init__(self) -> None:
        key = settings.pii_encryption_key
        if not key:
            if settings.app_env != "development":
                raise RuntimeError("PII_ENCRYPTION_KEY is required outside development")
            key = base64.urlsafe_b64encode(
                hashlib.sha256(b"awaaz-local-development-only").digest()
            ).decode()
        self._cipher = Fernet(key.encode())

    def encrypt(self, value: str) -> str:
        return self._cipher.encrypt(value.lower().encode()).decode()

    def decrypt(self, value: str) -> str:
        return self._cipher.decrypt(value.encode()).decode()
