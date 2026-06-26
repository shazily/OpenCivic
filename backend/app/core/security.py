"""
OpenCivic — Security Utilities

Covers:
- JWT validation against Keycloak JWKS endpoint (per-tenant)
- API key generation and SHA-256 hashing
- Field-level encryption for connector config and embargo datetimes
- Password hashing for local accounts

RULES:
- Raw API keys are NEVER stored — SHA-256 hash only
- Refresh tokens are NEVER stored in plaintext — httpOnly cookie only
- Sensitive fields (connector config, embargo_until) encrypted with Fernet before DB storage
- JWT tenant_id is ALWAYS the source of truth — never client-provided values
"""

import hashlib
import secrets
import uuid
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any

import structlog
from cryptography.fernet import Fernet
from cryptography.fernet import InvalidToken as FernetInvalidToken
from jose import ExpiredSignatureError, JWTError, jwk, jwt
from passlib.context import CryptContext

from app.core.config import settings
from app.core.errors import (
    EncryptionError,
    InvalidToken,
    TokenExpired,
)

logger = structlog.get_logger(__name__)

# ─────────────────────────────────────────────
# PASSWORD HASHING (local accounts only)
# ─────────────────────────────────────────────

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    """Hash a plaintext password with bcrypt. Use for local accounts only."""
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    return pwd_context.verify(plain, hashed)


# ─────────────────────────────────────────────
# API KEY GENERATION AND HASHING
# ─────────────────────────────────────────────

API_KEY_PREFIX = "oc_"  # OpenCivic prefix — makes keys identifiable in logs/secrets scanners
API_KEY_LENGTH = 32  # 32 random bytes = 256 bits of entropy


def generate_api_key() -> tuple[str, str, str]:
    """
    Generate a new API key.

    Returns:
        raw_key: The full key — shown to user ONCE, never stored
        key_hash: SHA-256 hash — stored in DB
        key_prefix: First 8 chars after prefix — shown in UI for identification

    RULE: Store only key_hash in database. key_prefix in display column.
    RULE: raw_key is shown exactly once at creation time — never retrievable.
    """
    raw = secrets.token_urlsafe(API_KEY_LENGTH)
    raw_key = f"{API_KEY_PREFIX}{raw}"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    key_prefix = raw_key[:8]
    return raw_key, key_hash, key_prefix


def hash_api_key(raw_key: str) -> str:
    """Hash an API key for lookup. Used when validating an incoming key."""
    return hashlib.sha256(raw_key.encode()).hexdigest()


def hash_ip_address(ip: str) -> str:
    """SHA-256 hash an IP address. RULE: Raw IPs are NEVER stored."""
    return hashlib.sha256(ip.encode()).hexdigest()


# ─────────────────────────────────────────────
# FIELD-LEVEL ENCRYPTION (Fernet / AES-128-CBC)
# ─────────────────────────────────────────────


@lru_cache(maxsize=1)
def _get_fernet() -> Fernet:
    """
    Return a Fernet instance using the SECRET_KEY.
    Fernet uses AES-128-CBC with HMAC-SHA256 for authenticated encryption.
    """
    # Derive a 32-byte key from SECRET_KEY using SHA-256
    key_bytes = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
    # Fernet requires URL-safe base64-encoded 32-byte key
    import base64

    fernet_key = base64.urlsafe_b64encode(key_bytes)
    return Fernet(fernet_key)


def encrypt_field(plaintext: str | bytes) -> bytes:
    """
    Encrypt a sensitive field before storing in the database.
    Used for: connector.config, webhook.secret, embargo_until, tenant.db_dsn

    Returns encrypted bytes for storage in LargeBinary column.
    """
    try:
        fernet = _get_fernet()
        if isinstance(plaintext, str):
            plaintext = plaintext.encode()
        return fernet.encrypt(plaintext)
    except Exception as e:
        logger.error("field_encryption_failed", error=str(e))
        raise EncryptionError(
            message="Failed to encrypt sensitive field.",
            code="ENCRYPTION_FAILED",
        ) from e


def decrypt_field(ciphertext: bytes) -> str:
    """
    Decrypt a sensitive field retrieved from the database.
    Returns decrypted string.

    RULE: Never log the decrypted value.
    """
    try:
        fernet = _get_fernet()
        return fernet.decrypt(ciphertext).decode()
    except FernetInvalidToken as e:
        logger.error("field_decryption_failed", error="invalid_token")
        raise EncryptionError(
            message="Failed to decrypt field — invalid or corrupted ciphertext.",
            code="DECRYPTION_FAILED",
        ) from e
    except Exception as e:
        logger.error("field_decryption_failed", error=str(e))
        raise EncryptionError(
            message="Failed to decrypt sensitive field.",
            code="DECRYPTION_FAILED",
        ) from e


def encrypt_datetime(dt: datetime) -> bytes:
    """Encrypt a datetime for embargo storage. Returns encrypted bytes."""
    return encrypt_field(dt.isoformat())


def decrypt_datetime(ciphertext: bytes) -> datetime:
    """Decrypt an embargo datetime. Returns UTC datetime."""
    iso_str = decrypt_field(ciphertext)
    return datetime.fromisoformat(iso_str).replace(tzinfo=timezone.utc)


# ─────────────────────────────────────────────
# JWT VALIDATION (Keycloak)
# ─────────────────────────────────────────────


class KeycloakJWTValidator:
    """
    Validates JWTs issued by Keycloak for a specific tenant realm.
    Caches JWKS (public keys) per realm to avoid repeated HTTP calls.
    """

    def __init__(self) -> None:
        self._jwks_cache: dict[str, Any] = {}

    async def get_jwks(self, realm: str) -> dict:
        """
        Fetch and cache the JWKS for a Keycloak realm.
        Keys are cached — Keycloak key rotation triggers cache miss on next validation.
        """
        if realm not in self._jwks_cache:
            import httpx

            url = f"{settings.KEYCLOAK_URL}/realms/{realm}/protocol/openid-connect/certs"
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, timeout=10.0)
                resp.raise_for_status()
                self._jwks_cache[realm] = resp.json()
            logger.info("keycloak_jwks_loaded", realm=realm)
        return self._jwks_cache[realm]

    def invalidate_cache(self, realm: str) -> None:
        """Invalidate cached JWKS for a realm — call on key rotation."""
        self._jwks_cache.pop(realm, None)

    async def validate_token(self, token: str, realm: str) -> dict[str, Any]:
        """
        Validate a JWT against the Keycloak realm's JWKS.

        Returns the decoded claims dict.
        Raises InvalidToken or TokenExpired on failure.

        Claims we extract and trust:
        - sub: Keycloak user ID
        - tenant_id: custom claim added by Keycloak mapper
        - realm_access.roles: Keycloak realm roles
        - preferred_username: human-readable username
        """
        try:
            jwks = await self.get_jwks(realm)

            # Get key ID from token header
            headers = jwt.get_unverified_header(token)
            kid = headers.get("kid")

            # Find matching key in JWKS
            signing_key = None
            for key_data in jwks.get("keys", []):
                if key_data.get("kid") == kid:
                    signing_key = jwk.construct(key_data)
                    break

            if signing_key is None:
                # Key not found — may be due to rotation, invalidate cache and retry once
                self.invalidate_cache(realm)
                jwks = await self.get_jwks(realm)
                for key_data in jwks.get("keys", []):
                    if key_data.get("kid") == kid:
                        signing_key = jwk.construct(key_data)
                        break

            if signing_key is None:
                raise InvalidToken(
                    message="Token signing key not found.",
                    code="SIGNING_KEY_NOT_FOUND",
                )

            claims = jwt.decode(
                token,
                signing_key.to_dict(),
                algorithms=["RS256"],
                options={"verify_aud": False},  # Audience verified per-endpoint
            )

            # Verify token has not been revoked (check blocklist in Valkey)
            await _check_token_blocklist(claims.get("jti", ""))

            return claims

        except ExpiredSignatureError as e:
            raise TokenExpired(
                message="Token has expired. Please refresh your session.",
            ) from e
        except JWTError as e:
            raise InvalidToken(
                message="Invalid token.",
            ) from e


# Module-level validator instance (shared across requests)
jwt_validator = KeycloakJWTValidator()


async def _check_token_blocklist(jti: str) -> None:
    """
    Check if a token has been explicitly revoked (admin force-logout).
    Revoked tokens are added to Valkey blocklist with TTL matching token expiry.
    """
    if not jti:
        return
    from app.core.cache import cache

    is_revoked = await cache.exists(f"token:blocklist:{jti}")
    if is_revoked:
        raise InvalidToken(
            message="Token has been revoked.",
            code="TOKEN_REVOKED",
        )


async def revoke_token(jti: str, ttl_seconds: int) -> None:
    """
    Add a token JTI to the revocation blocklist.
    Used by admin force-logout and session termination.
    TTL should match the token's remaining lifetime.
    """
    from app.core.cache import cache

    await cache.set(f"token:blocklist:{jti}", "1", ex=ttl_seconds)
    logger.info("token_revoked", jti=jti[:8] + "...")  # Log prefix only


def extract_tenant_id_from_claims(claims: dict[str, Any]) -> uuid.UUID:
    """
    Extract tenant_id from JWT claims.

    RULE: This is the ONLY valid source of tenant_id.
    RULE: Never use tenant_id from URL parameters, request body, or query strings.

    The tenant_id claim is added by a Keycloak mapper when the user authenticates.
    """
    tenant_id_str = claims.get("tenant_id")
    if not tenant_id_str:
        raise InvalidToken(
            message="Token does not contain tenant_id claim.",
            code="MISSING_TENANT_CLAIM",
        )
    try:
        return uuid.UUID(tenant_id_str)
    except ValueError as e:
        raise InvalidToken(
            message="Invalid tenant_id in token.",
            code="INVALID_TENANT_CLAIM",
        ) from e


def extract_roles_from_claims(claims: dict[str, Any]) -> list[str]:
    """Extract role list from Keycloak JWT claims."""
    realm_access = claims.get("realm_access", {})
    return realm_access.get("roles", [])
