from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from typing import Any

from cryptography.fernet import Fernet


class PasswordManager:
    iterations = 600_000

    def hash_password(self, password: str) -> str:
        salt = secrets.token_bytes(16)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, self.iterations)
        return f"{salt.hex()}:{digest.hex()}"

    def verify_password(self, password: str, password_hash: str) -> bool:
        salt_hex, digest_hex = password_hash.split(":", maxsplit=1)
        expected = bytes.fromhex(digest_hex)
        actual = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt_hex),
            self.iterations,
        )
        return hmac.compare_digest(expected, actual)


class CredentialVault:
    def __init__(self, secret_key: str) -> None:
        digest = hashlib.sha256(secret_key.encode("utf-8")).digest()
        fernet_key = base64.urlsafe_b64encode(digest)
        self._fernet = Fernet(fernet_key)

    def encrypt_json(self, payload: dict[str, Any]) -> str:
        raw = json.dumps(payload, ensure_ascii=True).encode("utf-8")
        return self._fernet.encrypt(raw).decode("utf-8")

    def decrypt_json(self, token: str) -> dict[str, Any]:
        raw = self._fernet.decrypt(token.encode("utf-8"))
        return json.loads(raw.decode("utf-8"))


def generate_session_token() -> str:
    return secrets.token_urlsafe(32)

