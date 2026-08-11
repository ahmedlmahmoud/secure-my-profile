"""Vault config.json and vault.env (hash-only secrets)."""
from __future__ import annotations

import json
import stat
import time
from pathlib import Path
from typing import Any

from .crypto import PBKDF2_ITERATIONS, die
from .paths import config_path, vault_dir, vault_env_path


def load_config(root: Path | None = None) -> dict[str, Any]:
    path = config_path(root)
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        die(f"corrupt vault config at {path}: {exc}")


def save_config(cfg: dict[str, Any], root: Path | None = None) -> None:
    path = config_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(cfg, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.chmod(stat.S_IRUSR | stat.S_IWUSR)
    tmp.replace(path)


def touch_action(cfg: dict[str, Any], **extra: Any) -> dict[str, Any]:
    cfg = dict(cfg)
    cfg["last_action_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    cfg.update(extra)
    return cfg


def parse_env_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        out[key.strip()] = val.strip().strip('"').strip("'")
    return out


def load_vault_secrets(root: Path | None = None) -> dict[str, str]:
    return parse_env_file(vault_env_path(root))


def write_vault_env(
    salt_hex: str,
    hash_hex: str,
    slug: str,
    root: Path | None = None,
    iterations: int = PBKDF2_ITERATIONS,
) -> None:
    path = vault_env_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = (
        "# Managed by secure-my-profile — hash only, never plaintext password\n"
        f"VAULT_SALT={salt_hex}\n"
        f"VAULT_PASSWORD_HASH={hash_hex}\n"
        f"VAULT_PROFILE={slug}\n"
        f"VAULT_PBKDF2_ITERATIONS={iterations}\n"
    )
    path.write_text(body, encoding="utf-8")
    path.chmod(stat.S_IRUSR | stat.S_IWUSR)


def ensure_vault_dirs(root: Path | None = None) -> Path:
    vdir = vault_dir(root)
    vdir.mkdir(parents=True, exist_ok=True)
    (vdir / "stashed").mkdir(parents=True, exist_ok=True)
    try:
        vdir.chmod(stat.S_IRWXU)
    except OSError:
        pass
    return vdir
