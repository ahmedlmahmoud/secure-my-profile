#!/usr/bin/env python3
"""CLI entry: password-gated hide/show for a Hermes named profile.

Subcommands: setup | status | hide|lock | show|unlock | change-password

Secrets live only as a salted PBKDF2 hash in ~/.hermes/vault/vault.env.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

# Allow `python3 scripts/secure_profile.py` without installing a package.
_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

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
    die,
    hash_password,
    new_salt,
    prompt_new_password,
    verify_against_secrets,
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


def cmd_setup(args: argparse.Namespace) -> int:
    root = default_hermes_home()
    ensure_vault_dirs(root)

    existing = load_config(root)
    if existing.get("setup_complete") and not args.force:
        print(
            f"vault already set up for profile {existing.get('profile')!r}.\n"
            f"Use --force to reconfigure, or: secure_profile.py change-password"
        )
        return 0

    if args.slug:
        slug = normalize_slug(args.slug)
    elif sys.stdin.isatty():
        raw = input("Profile slug [personal]: ").strip() or "personal"
        slug = normalize_slug(raw)
    else:
        slug = normalize_slug(os.environ.get("VAULT_PROFILE", "personal"))

    print(f"setting up secure profile {slug!r}")
    password = prompt_new_password()
    salt = new_salt()
    digest = hash_password(password, salt)
    del password

    write_vault_env(salt.hex(), digest, slug, root)

    if not args.no_create_profile:
        state = profile_state(slug, root)
        if state == "missing":
            create_profile_if_needed(slug, root)
        elif state == "hidden":
            print(f"profile {slug!r} is currently hidden (stashed); leave as-is")
        else:
            print(f"profile {slug!r} already visible")

    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    cfg = {
        "version": VAULT_VERSION,
        "profile": slug,
        "setup_complete": True,
        "state": profile_state(slug, root),
        "created_at": now,
        "last_action_at": now,
        "vault_dir": str(vault_dir(root)),
        "pbkdf2_iterations": PBKDF2_ITERATIONS,
    }
    save_config(cfg, root)

    print("setup complete")
    print(f"  config:  {config_path(root)}")
    print(f"  secrets: {vault_env_path(root)} (chmod 600, hash only)")
    print(f"  profile state: {cfg['state']}")
    print("next: /secure-my-profile hide   when you want it off the list")

    if args.hide_now and cfg["state"] == "visible":
        print("re-enter password to hide now...")
        return cmd_hide(args)
    return 0


def cmd_status(_args: argparse.Namespace) -> int:
    root = default_hermes_home()
    cfg = load_config(root)
    secrets_ok = vault_env_path(root).is_file()
    print(f"default hermes home: {root}")
    print(f"vault dir:           {vault_dir(root)}")
    print(f"setup complete:      {bool(cfg.get('setup_complete')) and secrets_ok}")
    if not cfg:
        print("not configured — run: /secure-my-profile setup")
        return 1
    slug = cfg.get("profile", "?")
    state = profile_state(slug, root) if slug != "?" else "unknown"
    print(f"secured profile:     {slug}")
    print(f"current state:       {state}")
    print(f"config state field:  {cfg.get('state', '?')}")
    print(f"last action:         {cfg.get('last_action_at', '?')}")
    if state == "visible":
        print(f"path:                {profile_visible_path(slug, root)}")
    elif state == "hidden":
        print(f"stashed at:          {profile_stashed_path(slug, root)}")
    else:
        print("path:                (missing both visible and stashed)")
    return 0


def _require_setup(root: Path) -> dict:
    cfg = load_config(root)
    if not cfg.get("setup_complete"):
        die("vault not set up — run: secure_profile.py setup")
    return cfg


def cmd_hide(_args: argparse.Namespace) -> int:
    root = default_hermes_home()
    cfg = _require_setup(root)
    slug = normalize_slug(cfg["profile"])
    ensure_not_inside_target(slug, root)
    verify_against_secrets(load_vault_secrets(root))

    state = profile_state(slug, root)
    if state == "hidden":
        print(f"profile {slug!r} is already hidden")
        save_config(touch_action(cfg, state="hidden"), root)
        return 0
    if state == "missing":
        die(f"profile {slug!r} not found under profiles/ or vault/stashed/")

    print(f"stopping gateway for {slug!r} (best-effort)...")
    best_effort_gateway_stop(slug)
    clear_sticky_if_needed(slug, root)
    move_profile_to_stash(slug, root)
    disable_alias(slug)
    save_config(touch_action(cfg, state="hidden"), root)
    print(f"profile {slug!r} hidden from Hermes profile list")
    print("restart Hermes Desktop if it still shows a cached list")
    return 0


def cmd_show(_args: argparse.Namespace) -> int:
    root = default_hermes_home()
    cfg = _require_setup(root)
    slug = normalize_slug(cfg["profile"])
    ensure_not_inside_target(slug, root)
    verify_against_secrets(load_vault_secrets(root))

    state = profile_state(slug, root)
    if state == "visible":
        print(f"profile {slug!r} is already visible at {profile_visible_path(slug, root)}")
        save_config(touch_action(cfg, state="visible"), root)
        return 0
    if state == "missing":
        die(f"profile {slug!r} not found under profiles/ or vault/stashed/")

    move_profile_from_stash(slug, root)
    restore_alias(slug)
    save_config(touch_action(cfg, state="visible"), root)
    print(f"profile {slug!r} restored")
    print(f"open with: hermes -p {slug} chat")
    print(f"or:        {slug} chat")
    return 0


def cmd_change_password(_args: argparse.Namespace) -> int:
    root = default_hermes_home()
    cfg = _require_setup(root)
    slug = normalize_slug(cfg.get("profile", "personal"))
    print("verify current password...")
    verify_against_secrets(load_vault_secrets(root))
    print("set new password...")
    password = prompt_new_password()
    salt = new_salt()
    digest = hash_password(password, salt)
    del password
    write_vault_env(salt.hex(), digest, slug, root)
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    save_config(touch_action(cfg, password_changed_at=now), root)
    print("password updated")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="secure_profile.py",
        description="Password-gated hide/show for a Hermes personal profile.",
    )
    sub = p.add_subparsers(dest="command", required=True)

    setup = sub.add_parser("setup", help="Bootstrap vault + optional profile")
    setup.add_argument("--slug", help="Profile slug (default: personal)")
    setup.add_argument(
        "--no-create-profile",
        action="store_true",
        help="Do not run hermes profile create",
    )
    setup.add_argument(
        "--hide-now",
        action="store_true",
        help="Hide the profile immediately after setup",
    )
    setup.add_argument(
        "--force",
        action="store_true",
        help="Re-run setup even if already configured",
    )
    setup.set_defaults(func=cmd_setup)

    st = sub.add_parser("status", help="Show vault / profile state")
    st.set_defaults(func=cmd_status)

    for name in ("hide", "lock"):
        h = sub.add_parser(name, help="Password-gate and hide profile from list")
        h.set_defaults(func=cmd_hide)

    for name in ("show", "unlock"):
        s = sub.add_parser(name, help="Password-gate and restore profile")
        s.set_defaults(func=cmd_show)

    cp = sub.add_parser("change-password", help="Rotate vault password hash")
    cp.set_defaults(func=cmd_change_password)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args) or 0)
    except BrokenPipeError:
        return 0


if __name__ == "__main__":
    sys.exit(main())
