"""Password hashing and interactive prompts (never log plaintext)."""
from __future__ import annotations

import getpass
import hashlib
import hmac
import os
import sys
from typing import NoReturn

PBKDF2_ITERATIONS = 600_000


def die(msg: str, code: int = 1) -> NoReturn:
    print(f"error: {msg}", file=sys.stderr)
    raise SystemExit(code)


def hash_password(
    password: str,
    salt: bytes,
    iterations: int = PBKDF2_ITERATIONS,
) -> str:
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return dk.hex()


def new_salt() -> bytes:
    return os.urandom(16)


def prompt_password(
    prompt: str = "Vault password: ",
    *,
    env_var: str = "VAULT_PASSWORD",
) -> str:
    """Interactive getpass when TTY; else env for local automation."""
    env_pw = os.environ.get(env_var)
    if not sys.stdin.isatty():
        if env_pw:
            return env_pw
        die(
            "no TTY for password prompt. Run from local Hermes TUI/CLI, "
            f"or set {env_var} for local non-interactive use only."
        )
    try:
        return getpass.getpass(prompt)
    except (EOFError, KeyboardInterrupt):
        die("password prompt cancelled")


def prompt_new_password() -> str:
    # Non-interactive: VAULT_NEW_PASSWORD (preferred) or VAULT_PASSWORD.
    if not sys.stdin.isatty():
        a = os.environ.get("VAULT_NEW_PASSWORD") or os.environ.get("VAULT_PASSWORD")
        if not a:
            die(
                "no TTY for new password. Set VAULT_NEW_PASSWORD "
                "(or VAULT_PASSWORD) for local non-interactive use only."
            )
        if len(a) < 8:
            die("password must be at least 8 characters")
        return a
    a = prompt_password("New vault password: ")
    if len(a) < 8:
        die("password must be at least 8 characters")
    b = prompt_password("Confirm vault password: ")
    if a != b:
        die("passwords do not match")
    return a


def verify_against_secrets(secrets: dict[str, str]) -> None:
    salt_hex = secrets.get("VAULT_SALT")
    expected = secrets.get("VAULT_PASSWORD_HASH")
    iters_s = secrets.get("VAULT_PBKDF2_ITERATIONS", str(PBKDF2_ITERATIONS))
    if not salt_hex or not expected:
        die("vault not set up — run: secure_profile.py setup")
    try:
        iterations = int(iters_s)
    except ValueError:
        iterations = PBKDF2_ITERATIONS
    pw = prompt_password("Vault password: ")
    got = hash_password(pw, bytes.fromhex(salt_hex), iterations)
    if not hmac.compare_digest(got, expected):
        die("wrong password")
