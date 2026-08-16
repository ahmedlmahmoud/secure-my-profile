"""Profile move, alias, gateway, and sticky-default helpers."""
from __future__ import annotations

import os
import re
import shutil
import stat
import subprocess
import sys
from pathlib import Path

from .crypto import VaultError, die  # VaultError re-export for callers; die raises it
from .paths import (
    active_profile_path,
    current_hermes_home,
    profile_stashed_path,
    profile_visible_path,
    profiles_root,
    stashed_dir,
    wrapper_dir,
)

PROFILE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
RESERVED = frozenset({"hermes", "test", "tmp", "root", "sudo", "default", "vault"})


def normalize_slug(name: str) -> str:
    name = name.strip().lower()
    if not name:
        die("profile slug cannot be empty")
    if name == "default":
        die("cannot secure the default profile")
    if name in RESERVED:
        die(f"profile slug {name!r} is reserved")
    if not PROFILE_ID_RE.match(name):
        die(f"invalid slug {name!r}; must match [a-z0-9][a-z0-9_-]{{0,63}}")
    return name


def evict_visible_aside(slug: str, root: Path) -> Path:
    """Move profiles/<slug> aside as a timestamped ghost backup. Never rmtree."""
    import time

    src = profile_visible_path(slug, root)
    if not src.exists():
        die(f"cannot evict missing visible profile {slug!r}")
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    dest = stashed_dir(root) / f"{slug}.ghost-{stamp}"
    n = 0
    while dest.exists():
        n += 1
        dest = stashed_dir(root) / f"{slug}.ghost-{stamp}-{n}"
    stashed_dir(root).mkdir(parents=True, exist_ok=True)
    print(f"evicting leftover visible {src} -> {dest}")
    try:
        shutil.move(str(src), str(dest))
    except OSError as exc:
        die(f"ghost evict failed: {exc}")
    return dest


def profile_state(slug: str, root: Path | None = None) -> str:
    """Return 'visible' | 'hidden' | 'missing'.

    Stash is source of truth. If vault/stashed/<slug> exists, state is
    **hidden** even when profiles/<slug> also exists (gateway often recreates
    an empty ghost; treating that as visible hid the real sessions).
    """
    if profile_stashed_path(slug, root).is_dir():
        return "hidden"
    if profile_visible_path(slug, root).is_dir():
        return "visible"
    return "missing"


def ensure_not_inside_target(slug: str, root: Path) -> None:
    cur = current_hermes_home()
    visible = profile_visible_path(slug, root).resolve()
    stashed = profile_stashed_path(slug, root).resolve()
    for target in (visible, stashed):
        if cur == target or str(cur).startswith(str(target) + os.sep):
            die(
                f"refusing to run while HERMES_HOME is the secured profile ({cur}).\n"
                f"Switch to default first: hermes profile use default\n"
                f"Then re-run from the default agent."
            )


def best_effort_gateway_stop(slug: str) -> None:
    hermes = shutil.which("hermes")
    if not hermes:
        return
    try:
        subprocess.run(
            [hermes, "-p", slug, "gateway", "stop"],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        pass


def clear_sticky_if_needed(slug: str, root: Path) -> None:
    path = active_profile_path(root)
    if not path.is_file():
        return
    try:
        current = path.read_text(encoding="utf-8").strip().lower()
    except OSError:
        return
    if current != slug:
        return
    try:
        path.write_text("default\n", encoding="utf-8")
        print(f"sticky default was {slug!r}; reset to default")
    except OSError as exc:
        print(f"warning: could not reset sticky default: {exc}", file=sys.stderr)


def disable_alias(slug: str) -> None:
    """Replace ~/.local/bin/<slug> with a locked bash stub (macOS/Linux)."""
    path = wrapper_dir() / slug
    if not path.exists() and not path.is_symlink():
        return

    stub = (
        "#!/usr/bin/env bash\n"
        f'echo "Profile {slug!r} is locked by secure-my-profile." >&2\n'
        'echo "Unlock with: Desktop ⌘K → Show personal, or /secure-my-profile show" >&2\n'
        "exit 1\n"
    )
    try:
        bak = path.with_suffix(path.suffix + ".secure-bak")
        if path.is_file() and not bak.exists():
            try:
                shutil.copy2(path, bak)
            except OSError:
                pass
        path.write_text(stub, encoding="utf-8")
        mode = path.stat().st_mode
        path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        print(f"alias {path} replaced with locked stub")
    except OSError as exc:
        print(f"warning: could not rewrite alias {path}: {exc}", file=sys.stderr)


def restore_alias(slug: str) -> None:
    path = wrapper_dir() / slug
    bak = path.with_suffix(path.suffix + ".secure-bak")
    if bak.is_file():
        try:
            shutil.move(str(bak), str(path))
            mode = path.stat().st_mode
            path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
            print(f"alias {path} restored from backup")
            return
        except OSError as exc:
            print(f"warning: could not restore alias backup: {exc}", file=sys.stderr)

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "#!/usr/bin/env bash\n"
            f'exec hermes -p {slug} "$@"\n',
            encoding="utf-8",
        )
        mode = path.stat().st_mode
        path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        print(f"alias {path} recreated")
    except OSError as exc:
        print(f"warning: could not recreate alias: {exc}", file=sys.stderr)


def create_profile_if_needed(slug: str, root: Path | None = None) -> None:
    target = profile_visible_path(slug, root)
    if target.is_dir():
        print(f"profile {slug!r} already exists at {target}")
        return
    hermes = shutil.which("hermes")
    if not hermes:
        die(
            f"hermes CLI not found and profile {slug!r} does not exist.\n"
            f"Install hermes or create the profile manually, then re-run setup."
        )
    print(f"creating profile {slug!r} ...")
    result = subprocess.run(
        [hermes, "profile", "create", slug],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        if target.is_dir():
            print("profile appeared after create attempt")
            return
        err = (result.stderr or result.stdout or "").strip()
        die(f"hermes profile create failed: {err or result.returncode}")
    print(f"created profile {slug!r}")
    if result.stdout.strip():
        print(result.stdout.strip())


def move_profile_to_stash(slug: str, root: Path) -> None:
    src = profile_visible_path(slug, root)
    dst = profile_stashed_path(slug, root)
    if dst.exists():
        die(f"stash path already exists: {dst}")
    stashed_dir(root).mkdir(parents=True, exist_ok=True)
    print(f"moving {src} -> {dst}")
    try:
        shutil.move(str(src), str(dst))
    except OSError as exc:
        die(f"move failed: {exc}")


def move_profile_from_stash(slug: str, root: Path) -> None:
    src = profile_stashed_path(slug, root)
    dst = profile_visible_path(slug, root)
    if dst.exists():
        die(f"profiles path already exists: {dst}")
    profiles_root(root).mkdir(parents=True, exist_ok=True)
    print(f"moving {src} -> {dst}")
    try:
        shutil.move(str(src), str(dst))
    except OSError as exc:
        die(f"move failed: {exc}")
