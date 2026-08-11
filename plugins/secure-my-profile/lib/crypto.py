"""Password hashing and verification (never log plaintext)."""
from __future__ import annotations

import hashlib
import hmac
import os
from typing import NoReturn

PBKDF2_ITERATIONS = 600_000


class VaultError(Exception):
    """User-facing vault/engine error (safe to show)."""

    def __init__(self, message: str, code: str = "error"):
        super().__init__(message)
        self.message = message
        self.code = code


def die(msg: str, code: str = "error") -> NoReturn:
    raise VaultError(msg, code=code)


def hash_password(
    password: str,
    salt: bytes,
    iterations: int = PBKDF2_ITERATIONS,
) -> str:
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return dk.hex()


def new_salt() -> bytes:
    return os.urandom(16)


def verify_password(password: str, secrets: dict[str, str]) -> None:
    """Raise VaultError on missing setup or wrong password."""
    salt_hex = secrets.get("VAULT_SALT")
    expected = secrets.get("VAULT_PASSWORD_HASH")
    iters_s = secrets.get("VAULT_PBKDF2_ITERATIONS", str(PBKDF2_ITERATIONS))
    if not salt_hex or not expected:
        die("vault not set up — run setup first", code="not_setup")
    try:
        iterations = int(iters_s)
    except ValueError:
        iterations = PBKDF2_ITERATIONS
    if not password:
        die("password required", code="password_required")
    got = hash_password(password, bytes.fromhex(salt_hex), iterations)
    if not hmac.compare_digest(got, expected):
        die("wrong password", code="wrong_password")
