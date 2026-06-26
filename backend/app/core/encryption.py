"""
OpenCivic — Field-level encryption for sensitive columns.
Used for: connector.config, embargo_until, webhook.secret.
AES-256-GCM via cryptography library.
RULE: Decrypted values are NEVER logged.
"""

import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import settings
from app.core.errors import EncryptionError


def _get_key() -> bytes:
    key_b64 = settings.SECRET_KEY
    raw = key_b64.encode()[:32].ljust(32, b"0")
    return raw


def encrypt(plaintext: str) -> bytes:
    try:
        key = _get_key()
        aesgcm = AESGCM(key)
        nonce = os.urandom(12)
        ct = aesgcm.encrypt(nonce, plaintext.encode(), None)
        return nonce + ct
    except Exception as e:
        raise EncryptionError(message="Encryption failed.", detail=str(e)) from e


def decrypt(ciphertext: bytes) -> str:
    try:
        key = _get_key()
        aesgcm = AESGCM(key)
        nonce, ct = ciphertext[:12], ciphertext[12:]
        return aesgcm.decrypt(nonce, ct, None).decode()
    except Exception as e:
        raise EncryptionError(message="Decryption failed.", detail=str(e)) from e
