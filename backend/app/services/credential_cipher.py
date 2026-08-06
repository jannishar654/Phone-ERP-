import base64
import binascii

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.config.settings import settings


class CredentialCipher:
    """Encrypts tenant credentials with authenticated encryption."""

    def __init__(self, namespace: str = "meta-whatsapp") -> None:
        self.namespace = namespace

    def _key_value(self) -> str:
        if self.namespace == "meta-whatsapp":
            return settings.META_WHATSAPP_TOKEN_ENCRYPTION_KEY.strip()
        return (
            settings.INTEGRATION_CREDENTIAL_ENCRYPTION_KEY
            or settings.META_WHATSAPP_TOKEN_ENCRYPTION_KEY
        ).strip()

    def _key(self) -> bytes:
        value = self._key_value()
        if not value:
            raise RuntimeError("Integration credential encryption is not configured")
        try:
            key = base64.urlsafe_b64decode(value.encode("ascii"))
        except (ValueError, binascii.Error, UnicodeEncodeError) as exc:
            raise RuntimeError("Integration credential encryption key is invalid") from exc
        if len(key) != 32:
            raise RuntimeError("Integration credential encryption key must decode to 32 bytes")
        return key

    def _aad(self, connection_id: str, key_version: int) -> bytes:
        return f"phoneerp:{self.namespace}:{connection_id}:v{key_version}".encode()

    def encrypt(self, connection_id: str, token: str) -> dict:
        if not token:
            raise RuntimeError("Cannot encrypt an empty integration credential")
        key_version = settings.INTEGRATION_CREDENTIAL_KEY_VERSION
        if self.namespace == "meta-whatsapp" or not settings.INTEGRATION_CREDENTIAL_ENCRYPTION_KEY:
            key_version = settings.META_WHATSAPP_TOKEN_KEY_VERSION
        nonce = __import__("os").urandom(12)
        encrypted = AESGCM(self._key()).encrypt(
            nonce,
            token.encode("utf-8"),
            self._aad(connection_id, key_version),
        )
        return {
            "connection_id": connection_id,
            "encrypted_token": base64.urlsafe_b64encode(encrypted).decode("ascii"),
            "token_nonce": base64.urlsafe_b64encode(nonce).decode("ascii"),
            "key_version": key_version,
        }

    def decrypt(self, connection_id: str, credential: dict) -> str:
        key_version = int(credential["key_version"])
        try:
            nonce = base64.urlsafe_b64decode(credential["token_nonce"])
            encrypted = base64.urlsafe_b64decode(credential["encrypted_token"])
            plaintext = AESGCM(self._key()).decrypt(
                nonce,
                encrypted,
                self._aad(connection_id, key_version),
            )
        except Exception as exc:
            raise RuntimeError("Integration credential could not be decrypted") from exc
        return plaintext.decode("utf-8")


credential_cipher = CredentialCipher()
telegram_credential_cipher = CredentialCipher("telegram")
