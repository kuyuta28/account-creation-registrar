"""
internal.py — Internal API router for service-to-service communication.

Registrar exposes this so Mail-Service and AA-Proxy can call it.
Protected by X-Internal-Key header.
"""
from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException

from ..schemas import ok

router = APIRouter(prefix="/internal", tags=["internal"])


_INTERNAL_KEY = os.getenv("INTERNAL_API_KEY", "ccs-internal")


async def _require_internal_key(x_internal_key: str | None = Header(default=None)) -> str:
    """Validate internal API key. Returns key if valid, raises 403 otherwise."""
    if x_internal_key is None or x_internal_key != _INTERNAL_KEY:
        raise HTTPException(status_code=403, detail="Forbidden")
    return x_internal_key


# ── Account Operations ─────────────────────────────────────────────────────────

@router.get("/accounts/{service}/{email}")
async def internal_get_account(
    service: str,
    email: str,
    _key: str = Depends(_require_internal_key),
):
    """Get account by service and email. Used by Mail-Service and AA-Proxy."""
    from ..services.account_service import get_account
    acc = await get_account(service.upper(), email)
    if not acc:
        raise HTTPException(status_code=404, detail="Account not found")
    return ok(acc)


@router.post("/accounts/upsert")
async def internal_upsert_account(
    body: dict[str, Any],
    _key: str = Depends(_require_internal_key),
):
    """Create or update account. Used by services that create accounts."""
    from ..services.account_service import add_account
    service = body.get("service", "").upper()
    email = body.get("email", "")
    api_key = body.get("api_key", "")
    password = body.get("password", "")
    if not service or not email:
        raise HTTPException(status_code=400, detail="service and email required")
    added = await add_account(
        service,
        email,
        api_key=api_key,
        password=password,
    )
    return ok({"created": added})


@router.patch("/accounts/{service}/{email}")
async def internal_update_account(
    service: str,
    email: str,
    body: dict[str, Any],
    _key: str = Depends(_require_internal_key),
):
    """Update account fields. Used by AA-Proxy after generating API key."""
    from ..services.account_service import update_account_fields
    updated = await update_account_fields(service.upper(), email, **body)
    if not updated:
        raise HTTPException(status_code=404, detail="Account not found")
    return ok({"updated": True})


@router.get("/accounts")
async def internal_list_accounts(
    service: str | None = None,
    _key: str = Depends(_require_internal_key),
):
    """List accounts, optionally filtered by service. Used by AA-Proxy and Mail-Service."""
    from ..services.account_service import list_accounts as _list
    accounts = await _list(service)
    return ok(accounts)


@router.delete("/accounts/{service}/{email}")
async def internal_delete_account(
    service: str,
    email: str,
    _key: str = Depends(_require_internal_key),
):
    """Delete account. Used by services cleanup."""
    from ..services.account_service import remove_account as _delete
    deleted = await _delete(service.upper(), email)
    if not deleted:
        raise HTTPException(status_code=404, detail="Account not found")
    return ok({"deleted": True})


@router.put("/accounts/{service}/{email}/session")
async def internal_save_session(
    service: str,
    email: str,
    body: dict[str, Any],
    _key: str = Depends(_require_internal_key),
):
    """Save session_state for an account. Used by AA-Proxy to persist Playwright session."""
    from ..services.account_service import update_account_fields
    session_state = body.get("session_state", "")
    updated = await update_account_fields(service.upper(), email, session_state=session_state)
    if not updated:
        raise HTTPException(status_code=404, detail="Account not found")
    return ok({"updated": True})


# ── Health Check ──────────────────────────────────────────────────────────────

@router.get("/health")
async def internal_health(_key: str = Depends(_require_internal_key)):
    """Health check for internal services."""
    return ok({"status": "healthy"})
