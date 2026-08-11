"""Path resolution for default Hermes home and vault layout."""
from __future__ import annotations

import os
from pathlib import Path


def default_hermes_home() -> Path:
    """Root Hermes home that owns profiles/ (never a named profile home)."""
    env = os.environ.get("HERMES_DEFAULT_HOME") or os.environ.get("HERMES_ROOT")
    if env:
        return Path(env).expanduser().resolve()

    current = os.environ.get("HERMES_HOME")
    if current:
        p = Path(current).expanduser().resolve()
        if p.parent.name == "profiles":
            return p.parent.parent
        if p.parent.name != "profiles" and (
            (p / "profiles").is_dir() or (p / "config.yaml").exists()
        ):
            return p

    return (Path.home() / ".hermes").resolve()


def current_hermes_home() -> Path:
    env = os.environ.get("HERMES_HOME")
    if env:
        return Path(env).expanduser().resolve()
    return default_hermes_home()


def vault_dir(root: Path | None = None) -> Path:
    return (root or default_hermes_home()) / "vault"


def profiles_root(root: Path | None = None) -> Path:
    return (root or default_hermes_home()) / "profiles"


def config_path(root: Path | None = None) -> Path:
    return vault_dir(root) / "config.json"


def vault_env_path(root: Path | None = None) -> Path:
    return vault_dir(root) / "vault.env"


def stashed_dir(root: Path | None = None) -> Path:
    return vault_dir(root) / "stashed"


def active_profile_path(root: Path | None = None) -> Path:
    return (root or default_hermes_home()) / "active_profile"


def wrapper_dir() -> Path:
    return Path.home() / ".local" / "bin"


def profile_visible_path(slug: str, root: Path | None = None) -> Path:
    return profiles_root(root) / slug


def profile_stashed_path(slug: str, root: Path | None = None) -> Path:
    return stashed_dir(root) / slug
