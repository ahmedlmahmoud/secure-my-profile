"""Password-gated hide/show for a Hermes named profile.

All sensitive ops take ``password`` as an explicit argument (never ambient
os.environ, never sticky skill secret). Durable secret on disk is only the
PBKDF2 hash in ``~/.hermes/vault/vault.env``.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any

# Package-local lib/
_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from lib.config import (  # noqa: E402
    ensure_vault_dirs,
    load_config,
    load_vault_secrets,
    save_config,
    touch_action,
    write_vault_env,
)
from lib.crypto import (  # noqa: E402
    PBKDF2_ITERATIONS,
    VaultError,
    die,
    hash_password,
    new_salt,
    verify_password,
)
from lib.paths import (  # noqa: E402
    config_path,
    default_hermes_home,
    profile_stashed_path,
    profile_visible_path,
    vault_dir,
    vault_env_path,
)
from lib.profile_ops import (  # noqa: E402
    best_effort_gateway_stop,
    clear_sticky_if_needed,
    create_profile_if_needed,
    disable_alias,
    ensure_not_inside_target,
    move_profile_from_stash,
    move_profile_to_stash,
    normalize_slug,
    profile_state,
    restore_alias,
)

VAULT_VERSION = 1


def _ok(**extra: Any) -> dict[str, Any]:
    out: dict[str, Any] = {"ok": True}
    out.update(extra)
    return out


def _require_setup(root: Path) -> dict[str, Any]:
    cfg = load_config(root)
    if not cfg.get("setup_complete") or not vault_env_path(root).is_file():
        die("vault not set up — run setup first", code="not_setup")
    return cfg


def status() -> dict[str, Any]:
    root = default_hermes_home()
    cfg = load_config(root)
    secrets_ok = vault_env_path(root).is_file()
    setup = bool(cfg.get("setup_complete")) and secrets_ok
    slug = cfg.get("profile") if cfg else None
    state = profile_state(slug, root) if slug else "unconfigured"
    result: dict[str, Any] = {
        "ok": True,
        "hermes_home": str(root),
        "vault_dir": str(vault_dir(root)),
        "setup_complete": setup,
        "profile": slug,
        "state": state if setup else "unconfigured",
        "last_action_at": cfg.get("last_action_at") if cfg else None,
        "config_path": str(config_path(root)),
    }
    if setup and slug:
        if state == "visible":
            result["path"] = str(profile_visible_path(slug, root))
        elif state == "hidden":
            result["stashed_at"] = str(profile_stashed_path(slug, root))
    return result


def setup(
    *,
    password: str,
    slug: str | None = None,
    force: bool = False,
    create_profile: bool = True,
) -> dict[str, Any]:
    root = default_hermes_home()
    ensure_vault_dirs(root)

    existing = load_config(root)
    if existing.get("setup_complete") and vault_env_path(root).is_file() and not force:
        return _ok(
            already_setup=True,
            profile=existing.get("profile"),
            state=profile_state(existing.get("profile", "personal"), root),
            message="vault already set up; pass force=true to reconfigure",
        )

    if not password or len(password) < 8:
        die("password must be at least 8 characters", code="weak_password")

    resolved = normalize_slug(slug or existing.get("profile") or "personal")
    salt = new_salt()
    digest = hash_password(password, salt)
    write_vault_env(salt.hex(), digest, resolved, root)

    if create_profile:
        state = profile_state(resolved, root)
        if state == "missing":
            create_profile_if_needed(resolved, root)

    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    state_now = profile_state(resolved, root)
    cfg = {
        "version": VAULT_VERSION,
        "profile": resolved,
        "setup_complete": True,
        "state": state_now,
        "created_at": now,
        "last_action_at": now,
        "vault_dir": str(vault_dir(root)),
        "pbkdf2_iterations": PBKDF2_ITERATIONS,
    }
    save_config(cfg, root)
    return _ok(
        profile=resolved,
        state=state_now,
        config=str(config_path(root)),
        secrets=str(vault_env_path(root)),
        message="setup complete",
    )


def hide(*, password: str) -> dict[str, Any]:
    root = default_hermes_home()
    cfg = _require_setup(root)
    slug = normalize_slug(cfg["profile"])
    ensure_not_inside_target(slug, root)
    verify_password(password, load_vault_secrets(root))

    state = profile_state(slug, root)
    if state == "hidden":
        save_config(touch_action(cfg, state="hidden"), root)
        return _ok(profile=slug, state="hidden", message="already hidden")
    if state == "missing":
        die(f"profile {slug!r} not found under profiles/ or vault/stashed/", code="missing")

    best_effort_gateway_stop(slug)
    clear_sticky_if_needed(slug, root)
    move_profile_to_stash(slug, root)

    # Idempotent ghost cleanup: gateway may recreate thin profiles/<slug>/
    ghost = profile_visible_path(slug, root)
    if ghost.exists():
        import shutil

        shutil.rmtree(ghost, ignore_errors=True)

    disable_alias(slug)
    save_config(touch_action(cfg, state="hidden"), root)
    return _ok(
        profile=slug,
        state="hidden",
        stashed_at=str(profile_stashed_path(slug, root)),
        message=f"profile {slug!r} hidden; restart Desktop if list is cached",
    )


def show(*, password: str) -> dict[str, Any]:
    root = default_hermes_home()
    cfg = _require_setup(root)
    slug = normalize_slug(cfg["profile"])
    ensure_not_inside_target(slug, root)
    verify_password(password, load_vault_secrets(root))

    state = profile_state(slug, root)
    if state == "visible":
        save_config(touch_action(cfg, state="visible"), root)
        return _ok(
            profile=slug,
            state="visible",
            path=str(profile_visible_path(slug, root)),
            message="already visible",
        )
    if state == "missing":
        die(f"profile {slug!r} not found under profiles/ or vault/stashed/", code="missing")

    # Drop thin ghost if gateway recreated profiles/<slug>/ (state.db only).
    # Real stashed profiles are large; ghosts are tiny.
    ghost = profile_visible_path(slug, root)
    if ghost.exists():
        try:
            total = sum(f.stat().st_size for f in ghost.rglob("*") if f.is_file())
            if total < 5_000_000:
                import shutil

                shutil.rmtree(ghost, ignore_errors=True)
        except OSError:
            pass

    move_profile_from_stash(slug, root)
    restore_alias(slug)
    save_config(touch_action(cfg, state="visible"), root)
    return _ok(
        profile=slug,
        state="visible",
        path=str(profile_visible_path(slug, root)),
        message=f"profile {slug!r} restored",
    )


def change_password(*, current_password: str, new_password: str) -> dict[str, Any]:
    root = default_hermes_home()
    cfg = _require_setup(root)
    slug = normalize_slug(cfg.get("profile", "personal"))
    verify_password(current_password, load_vault_secrets(root))
    if not new_password or len(new_password) < 8:
        die("new password must be at least 8 characters", code="weak_password")
    salt = new_salt()
    digest = hash_password(new_password, salt)
    write_vault_env(salt.hex(), digest, slug, root)
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    save_config(touch_action(cfg, password_changed_at=now), root)
    return _ok(profile=slug, message="password updated")


def format_status_text(data: dict[str, Any] | None = None) -> str:
    data = data or status()
    lines = [
        f"hermes home:     {data.get('hermes_home')}",
        f"vault dir:       {data.get('vault_dir')}",
        f"setup complete:  {data.get('setup_complete')}",
        f"secured profile: {data.get('profile') or '—'}",
        f"current state:   {data.get('state')}",
        f"last action:     {data.get('last_action_at') or '—'}",
    ]
    if data.get("path"):
        lines.append(f"path:            {data['path']}")
    if data.get("stashed_at"):
        lines.append(f"stashed at:      {data['stashed_at']}")
    if not data.get("setup_complete"):
        lines.append("not configured — use Desktop ⌘K → Setup personal vault")
    return "\n".join(lines)
