"""Backend for secure-my-profile — mounted at /api/plugins/secure-my-profile/.

Password is request-scoped in the JSON body only. Never written to .env or
parent os.environ. Runs inside the dashboard/gateway process on the Hermes host.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

# Engine lives one level up from dashboard/
_PLUGIN_ROOT = Path(__file__).resolve().parent.parent
if str(_PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_ROOT))

import engine  # noqa: E402
from lib.crypto import VaultError  # noqa: E402

router = APIRouter()


class PasswordBody(BaseModel):
    password: str = Field(..., min_length=1)


class SetupBody(BaseModel):
    password: str = Field(..., min_length=8)
    slug: Optional[str] = "personal"
    force: bool = False
    create_profile: bool = True


class ChangePasswordBody(BaseModel):
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8)


def _http_err(exc: VaultError) -> HTTPException:
    status = 400
    if exc.code == "wrong_password":
        status = 401
    elif exc.code == "not_setup":
        status = 409
    elif exc.code == "password_required":
        status = 400
    return HTTPException(status_code=status, detail={"ok": False, "error": exc.message, "code": exc.code})


@router.get("/status")
async def api_status() -> dict[str, Any]:
    try:
        return engine.status()
    except VaultError as exc:
        raise _http_err(exc) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail={"ok": False, "error": str(exc)}) from exc


@router.post("/setup")
async def api_setup(body: SetupBody) -> dict[str, Any]:
    try:
        return engine.setup(
            password=body.password,
            slug=body.slug,
            force=body.force,
            create_profile=body.create_profile,
        )
    except VaultError as exc:
        raise _http_err(exc) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail={"ok": False, "error": str(exc)}) from exc


@router.post("/hide")
async def api_hide(body: PasswordBody) -> dict[str, Any]:
    try:
        return engine.hide(password=body.password)
    except VaultError as exc:
        raise _http_err(exc) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail={"ok": False, "error": str(exc)}) from exc


@router.post("/show")
async def api_show(body: PasswordBody) -> dict[str, Any]:
    try:
        return engine.show(password=body.password)
    except VaultError as exc:
        raise _http_err(exc) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail={"ok": False, "error": str(exc)}) from exc


@router.post("/change-password")
async def api_change_password(body: ChangePasswordBody) -> dict[str, Any]:
    try:
        return engine.change_password(
            current_password=body.current_password,
            new_password=body.new_password,
        )
    except VaultError as exc:
        raise _http_err(exc) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail={"ok": False, "error": str(exc)}) from exc
