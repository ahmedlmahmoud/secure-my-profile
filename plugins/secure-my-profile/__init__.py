"""secure-my-profile — Hermes plugin (engine + slash; Desktop UI is separate).

Slash ``/secure-my-profile`` runs the handler directly (no LLM / no skill).
Password-gated actions on Desktop use the Desktop plugin → plugin_api REST.
Slash status works anywhere; hide/show via slash need a real TTY (CLI) or
the Desktop password dialog.
"""
from __future__ import annotations

import getpass
import sys
from pathlib import Path

_PLUGIN_ROOT = Path(__file__).resolve().parent
if str(_PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_ROOT))

import engine  # noqa: E402
from lib.crypto import VaultError  # noqa: E402

_HELP = """\
/secure-my-profile status              — vault / profile state (no password)
/secure-my-profile setup               — bootstrap (CLI TTY password)
/secure-my-profile hide | lock         — hide profile (CLI TTY or Desktop ⌘K)
/secure-my-profile show | unlock       — restore profile
/secure-my-profile change-password     — rotate hash

Desktop (recommended): ⌘K → Hide / Show / Setup personal profile
  Password dialog → local plugin API on the Hermes host (no skill session).
"""


def _tty_password(prompt: str = "Vault password: ") -> str:
    try:
        if sys.stdin.isatty():
            return getpass.getpass(prompt)
    except Exception:
        pass
    try:
        with open("/dev/tty", "r", encoding="utf-8", errors="replace") as tty:
            try:
                return getpass.getpass(prompt, stream=tty)  # type: ignore[call-arg]
            except TypeError:
                return getpass.getpass(prompt)
    except OSError as exc:
        raise VaultError(
            "no interactive TTY for password. "
            "On Desktop use ⌘K → Hide/Show personal profile (password dialog). "
            f"({exc})",
            code="no_tty",
        ) from exc


def _handle_slash(raw_args: str) -> str:
    parts = (raw_args or "").strip().split()
    sub = (parts[0].lower() if parts else "status")
    try:
        if sub in ("", "status", "st"):
            return engine.format_status_text()
        if sub in ("help", "-h", "--help"):
            return _HELP.strip()
        if sub == "setup":
            force = "--force" in parts
            slug = None
            for i, p in enumerate(parts[1:], start=1):
                if p == "--slug" and i + 1 < len(parts):
                    slug = parts[i + 1]
            pw = _tty_password("New vault password (min 8): ")
            if len(pw) < 8:
                return "error: password must be at least 8 characters"
            confirm = _tty_password("Confirm vault password: ")
            if pw != confirm:
                return "error: passwords do not match"
            result = engine.setup(password=pw, slug=slug, force=force)
            return result.get("message") or str(result)
        if sub in ("hide", "lock"):
            pw = _tty_password()
            result = engine.hide(password=pw)
            return result.get("message") or str(result)
        if sub in ("show", "unlock"):
            pw = _tty_password()
            result = engine.show(password=pw)
            return result.get("message") or str(result)
        if sub in ("change-password", "passwd", "password"):
            cur = _tty_password("Current vault password: ")
            new = _tty_password("New vault password (min 8): ")
            if len(new) < 8:
                return "error: new password must be at least 8 characters"
            conf = _tty_password("Confirm new password: ")
            if new != conf:
                return "error: passwords do not match"
            result = engine.change_password(current_password=cur, new_password=new)
            return result.get("message") or str(result)
        return f"Unknown subcommand: {sub}\n\n{_HELP}"
    except VaultError as exc:
        return f"error: {exc.message}"
    except SystemExit as exc:
        # lib.profile_ops may still call die() → SystemExit in older paths
        return f"error: exited ({exc.code})"
    except Exception as exc:  # noqa: BLE001
        return f"error: {exc}"


def register(ctx) -> None:
    ctx.register_command(
        "secure-my-profile",
        handler=_handle_slash,
        description="Password-gated hide/show for a Hermes named profile",
        args_hint="[status|setup|hide|show|change-password]",
    )
