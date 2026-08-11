"""Password hashing, interactive prompts, and one-shot env scrub (never log plaintext)."""
from __future__ import annotations

import getpass
import hashlib
import hmac
import os
import re
import stat
import sys
from pathlib import Path
from typing import NoReturn

PBKDF2_ITERATIONS = 600_000

# Env vars that may carry the vault password for one-shot chat/CLI use.
# Scrubbed after every command so Hermes secret.request does not "stick"
# the unlock password in ~/.hermes/.env like a permanent API key.
PASSWORD_ENV_KEYS = ("VAULT_PASSWORD", "VAULT_NEW_PASSWORD")


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
    """Interactive getpass when TTY; else env for local / chat secret-capture.

    Chat path: Hermes Desktop/TUI ``secret.request`` stores the value in
    process env / ``.env`` under ``env_var`` without exposing it to the model.
    Callers MUST scrub via :func:`scrub_password_env` after use.
    """
    env_pw = os.environ.get(env_var)
    if not sys.stdin.isatty():
        if env_pw:
            return env_pw
        die(
            "no TTY for password prompt. On Desktop/TUI re-run the slash command "
            "and complete the secure secret dialog (or set "
            f"{env_var} for local non-interactive use only)."
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
                "no TTY for new password. On Desktop/TUI complete the secure "
                "secret dialog for VAULT_NEW_PASSWORD or VAULT_PASSWORD, "
                "or set those env vars for local non-interactive use only."
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
    # Drop local reference ASAP (best-effort; Python strings are immutable).
    del pw
    if not hmac.compare_digest(got, expected):
        die("wrong password")


def _scrub_dotenv_keys(env_path: Path, keys: tuple[str, ...]) -> bool:
    """Remove KEY= lines from a dotenv file. Returns True if file changed."""
    if not env_path.is_file():
        return False
    try:
        original = env_path.read_text(encoding="utf-8")
    except OSError:
        return False

    keyset = set(keys)
    out_lines: list[str] = []
    changed = False
    # Match KEY or export KEY at line start; do not print values.
    pattern = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=")
    for line in original.splitlines(keepends=True):
        m = pattern.match(line)
        if m and m.group(1) in keyset:
            changed = True
            continue
        out_lines.append(line)

    if not changed:
        return False

    text = "".join(out_lines)
    tmp = env_path.with_suffix(env_path.suffix + ".scrub-tmp")
    try:
        tmp.write_text(text, encoding="utf-8")
        try:
            tmp.chmod(stat.S_IRUSR | stat.S_IWUSR)
        except OSError:
            pass
        tmp.replace(env_path)
    except OSError:
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass
        return False
    return True


def scrub_password_env(*, hermes_home: Path | None = None) -> None:
    """One-shot cleanup: drop vault password from process env and dotenv files.

    Hermes skill secret-capture persists values into ``~/.hermes/.env`` so the
    model never sees them. For an *unlock* password that must not be memorized,
    we delete those keys after every hide/show/setup/change-password so the next
    slash invocation re-prompts via ``secret.request``.
    """
    for key in PASSWORD_ENV_KEYS:
        if key in os.environ:
            os.environ.pop(key, None)

    candidates: list[Path] = []
    if hermes_home is not None:
        candidates.append(Path(hermes_home) / ".env")
    # Default layout + common symlink target (never log contents).
    home = Path.home()
    candidates.append(home / ".hermes" / ".env")
    dabbo = home / "dabbo-state" / ".hermes" / ".env"
    if dabbo not in candidates:
        candidates.append(dabbo)

    seen: set[Path] = set()
    for path in candidates:
        try:
            resolved = path.resolve()
        except OSError:
            resolved = path
        if resolved in seen:
            continue
        seen.add(resolved)
        _scrub_dotenv_keys(path, PASSWORD_ENV_KEYS)
