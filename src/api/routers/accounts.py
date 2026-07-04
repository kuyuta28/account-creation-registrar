"""
accounts.py — Router: CRUD accounts.
Response: unified ApiResponse envelope.
"""
from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

from ..exceptions import AppError
from ..schemas import ErrorCode, ok
from ..services.account_service import (
    add_account,
    create_service,
    destroy_service,
    get_account,
    has_service,
    list_accounts,
    list_services,
    remove_account,
    remove_disabled_accounts,
    update_account_fields,
)
from ..services.checker_service import (
    check_and_persist,
    get_batch_status,
    get_check_and_clean_or_status,
    get_fix_or_privacy_status,
    get_openrouter_key_detail,
    get_or_privacy_status,
    refresh_kling_session,
    start_batch_check,
    start_check_and_clean_or,
    start_fix_or_privacy,
    start_or_privacy_check,
)
from ..services.sync_service import (
    preview_sync_openrouter_to_cliproxy,
    sync_cliproxy,
    sync_ollama_to_cliproxy,
    sync_openrouter_to_cliproxy,
)
from ..services.ninerouter_sync import (
    preview_sync_ollama_to_9router,
    sync_ollama_to_9router,
)
from ...config.settings import load_config
from ..services.open_browser_service import open_browser_window

_log = logging.getLogger(__name__)
router = APIRouter(prefix="/accounts", tags=["accounts"])


class AddAccountBody(BaseModel):
    service: str
    email: str
    api_key: str | None = ""
    password: str | None = ""
    totp_secret: str | None = ""
    app_password: str | None = ""
    source_email: str | None = ""  # Gmail base nếu email này là alias


class UpdateAccountBody(BaseModel):
    api_key: str | None = None
    password: str | None = None
    disabled: bool | None = None
    credits: int | None = None
    totp_secret: str | None = None
    app_password: str | None = None


@router.get("/services")
async def get_services():
    return ok(await list_services())


@router.get("/service-counts")
async def get_service_counts():
    """Return account counts grouped by service. Powers the sidebar badges
    in the web UI's Accounts page. Best-effort: services with no rows are
    omitted from the response so the client can default missing keys to 0.
    """
    from sqlalchemy import func, select

    from common.database._engine import _Account, get_async_session

    counts: dict[str, int] = {}
    async with get_async_session() as session:
        rows = await session.execute(
            select(_Account.service, func.count(_Account.id)).group_by(_Account.service)
        )
        for service, cnt in rows.all():
            counts[service.upper()] = int(cnt)
    return ok(counts)


class AddServiceBody(BaseModel):
    name: str
    has_registrar: bool = False


@router.post("/services")
async def post_service(body: AddServiceBody):
    name = body.name.strip().upper()
    if not name:
        raise AppError(ErrorCode.VALIDATION, "name is required", 400)
    created = await create_service(name, body.has_registrar)
    if not created:
        raise AppError(ErrorCode.CONFLICT, f"Service '{name}' already exists", 409)
    return ok({"created": True, "name": name})


@router.delete("/services/{name}")
async def del_service(name: str):
    deleted = await destroy_service(name.upper())
    if not deleted:
        raise AppError(ErrorCode.NOT_FOUND, f"Service '{name.upper()}' not found", 404)
    return ok({"deleted": True})


@router.get("")
async def get_accounts(service: str | None = None, page: int | None = None, limit: int | None = None):
    # Defaults
    if limit is None:
        limit = 100
    if page is None:
        page = 1
    offset = (page - 1) * limit
    result = await list_accounts(service, limit=limit, offset=offset)
    return ok({
        "accounts": result["accounts"],
        "total": result["total"],
        "page": page,
        "limit": limit,
        "pages": (result["total"] + limit - 1) // limit if limit > 0 else 0,
    })


# ── Specific routes MUST come BEFORE greedy /{service}/{email:path} ──

@router.post("/add")
async def add_one(body: AddAccountBody):
    if not body.service or not body.email:
        raise AppError(ErrorCode.VALIDATION, "service and email are required", 400)
    if not await has_service(body.service):
        raise AppError(ErrorCode.UNSUPPORTED, f"Unsupported service: {body.service}", 400)
    added = await add_account(
        body.service.upper(), body.email,
        body.api_key or "", body.password or "",
        body.totp_secret or "", body.app_password or "",
        body.source_email or "",
    )
    if not added:
        raise AppError(ErrorCode.CONFLICT, "Account already exists", 409)
    return ok({"created": True})


@router.post("/check")
async def check_one(service: str, email: str):
    result = await check_and_persist(service.upper(), email)
    if "error" in result:
        code = ErrorCode.NOT_FOUND if result["error"] == "not found" else ErrorCode.VALIDATION
        status = 404 if result["error"] == "not found" else 400
        raise AppError(code, result["error"], status)
    return ok(result)


@router.post("/check-all")
async def check_all(service: str | None = None):
    result = await start_batch_check(service)
    if "error" in result:
        if result["error"] == "already running":
            raise AppError(ErrorCode.ALREADY_RUNNING, "Batch check already running", 409)
        raise AppError(ErrorCode.VALIDATION, result["error"], 400)
    return ok(result)


@router.get("/check-all/status")
async def check_all_status():
    return ok(await get_batch_status())


@router.post("/check-openrouter-privacy")
async def check_openrouter_privacy():
    result = await start_or_privacy_check()
    if "error" in result:
        if result["error"] == "already running":
            raise AppError(ErrorCode.ALREADY_RUNNING, "Privacy check already running", 409)
        raise AppError(ErrorCode.VALIDATION, result["error"], 400)
    return ok(result)


@router.get("/check-openrouter-privacy/status")
async def check_openrouter_privacy_status():
    return ok(await get_or_privacy_status())


@router.post("/check-and-clean-openrouter")
async def check_and_clean_openrouter_endpoint():
    """Test từng OR key với real API call (minimax), xóa dead keys khỏi DB + CLIProxy."""
    result = await start_check_and_clean_or()
    if "error" in result:
        if result["error"] == "already running":
            raise AppError(ErrorCode.ALREADY_RUNNING, "Check-and-clean already running", 409)
        raise AppError(ErrorCode.VALIDATION, result["error"], 400)
    return ok(result)


@router.get("/check-and-clean-openrouter/status")
async def check_and_clean_openrouter_status():
    return ok(await get_check_and_clean_or_status())


@router.post("/fix-openrouter-privacy")
async def fix_openrouter_privacy_endpoint():
    """Login vào từng OR account (Playwright), bật tất cả privacy toggles."""
    result = await start_fix_or_privacy()
    if "error" in result:
        if result["error"] == "already running":
            raise AppError(ErrorCode.ALREADY_RUNNING, "Fix privacy already running", 409)
        raise AppError(ErrorCode.VALIDATION, result["error"], 400)
    return ok(result)


@router.get("/fix-openrouter-privacy/status")
async def fix_openrouter_privacy_status():
    return ok(await get_fix_or_privacy_status())


class RefreshKlingBody(BaseModel):
    email: str


@router.post("/refresh-kling-session")
async def refresh_kling_session_endpoint(body: RefreshKlingBody):
    """Visit app.klingai.com với session hiện có để refresh cookie expiry."""
    result = await refresh_kling_session(body.email)
    if "error" in result:
        raise AppError(ErrorCode.NOT_FOUND, result["error"], 404)
    return ok(result)


@router.post("/key-detail")
async def key_detail(service: str, api_key: str):
    if service.upper() != "OPENROUTER":
        raise AppError(ErrorCode.UNSUPPORTED, f"key-detail not supported for {service}", 400)
    result = await get_openrouter_key_detail(api_key)
    if not result.get("valid"):
        raise AppError(ErrorCode.VALIDATION, result.get("error", "invalid key"), 400)
    return ok(result)


@router.delete("/bulk-delete-disabled")
async def bulk_delete_disabled(service: str = "ALL"):
    """Xóa tất cả disabled/invalid/error accounts. service=ALL (default) → mọi service."""
    deleted = await remove_disabled_accounts(service)
    return ok({"deleted": deleted})


@router.post("/sync-cliproxy")
async def sync_cliproxy_endpoint():
    result = await sync_cliproxy()
    if "error" in result:
        raise AppError(ErrorCode.INTERNAL, result["error"], 500)
    return ok(result)


class SyncOpenRouterBody(BaseModel):
    emails: list[str] | None = None


@router.post("/sync-openrouter-cliproxy/preview")
async def sync_openrouter_cliproxy_preview_endpoint(body: SyncOpenRouterBody):
    """Xem trước danh sách OPENROUTER sẽ được sync."""
    try:
        result = await preview_sync_openrouter_to_cliproxy(account_emails=body.emails)
        return ok(result)
    except (FileNotFoundError, ValueError, RuntimeError, OSError) as e:
        _log.error("sync-openrouter-cliproxy/preview failed: %s", e)
        raise AppError(ErrorCode.INTERNAL, str(e), 500)


@router.post("/sync-openrouter-cliproxy")
async def sync_openrouter_cliproxy_endpoint(body: SyncOpenRouterBody):
    try:
        result = await sync_openrouter_to_cliproxy(account_emails=body.emails)
    except FileNotFoundError as e:
        raise AppError(ErrorCode.NOT_FOUND, str(e), 404)
    return ok(result)


@router.post("/sync-ollama-cliproxy")
async def sync_ollama_cliproxy_endpoint():
    try:
        result = await sync_ollama_to_cliproxy()
    except FileNotFoundError as e:
        raise AppError(ErrorCode.NOT_FOUND, str(e), 404)
    return ok(result)


class Sync9routerBody(BaseModel):
    emails: list[str] | None = None


@router.post("/sync-ollama-9router/preview")
async def sync_ollama_9router_preview_endpoint(body: Sync9routerBody):
    """Xem trước danh sách Ollama accounts sẽ được sync sang 9router."""
    try:
        result = await preview_sync_ollama_to_9router(
            account_emails=body.emails or None,
        )
        return ok(result)
    except (FileNotFoundError, ValueError, RuntimeError, OSError) as e:
        _log.error("sync-ollama-9router/preview failed: %s", e)
        raise AppError(ErrorCode.INTERNAL, str(e), 500)


@router.post("/sync-ollama-9router")
async def sync_ollama_9router_endpoint(body: Sync9routerBody):
    """Sync Ollama accounts từ DB sang 9router db.json."""
    try:
        result = await sync_ollama_to_9router(
            account_emails=body.emails or None,
        )
        return ok(result)
    except (FileNotFoundError, ValueError, RuntimeError, OSError) as e:
        _log.error("sync-ollama-9router failed: %s", e)
        raise AppError(ErrorCode.INTERNAL, str(e), 500)


# ── Auth sync ────────────────────────────────────────────────────────────────

@router.post("/sync-auth")
async def sync_auth_endpoint(target_dir: str | None = None):
    """Sync exported auth JSON files từ auth/ ra target_dir (hoặc từ config nếu không truyền)."""
    import asyncio
    from ...config.settings import load_config
    from src.core.account_record import Repo, repo_sync_auth
    cfg = load_config()
    repo = Repo(base_dir=cfg.base_dir, auth_sync=cfg.auth_sync, cliproxy_sync=cfg.cliproxy_sync)
    dest = Path(target_dir) if target_dir else None
    synced = await asyncio.to_thread(repo_sync_auth, repo, dest)
    return ok({"synced": len(synced), "files": [str(p) for p in synced]})


# ── Kling session capture ─────────────────────────────────────────────────────

_KLING_SESSION_TOOL = Path(__file__).parent.parent / "tools" / "kling_session_tool.py"


class KlingSessionBody(BaseModel):
    gmail_hint: str | None = None


@router.post("/kling-session")
async def kling_session(body: KlingSessionBody):
    """Mở browser để capture Kling AI session sau khi user login Google thủ công."""
    args = [sys.executable, str(_KLING_SESSION_TOOL)]
    if body.gmail_hint:
        args.append(body.gmail_hint)
    subprocess.Popen(args, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0)
    return ok({"launched": True, "note": "Browser đã mở — đăng nhập Google vào Kling AI để lưu session."})


# ── Greedy path routes ────────────────────────────────────────────────────────


class OpenBrowserBody(BaseModel):
    service: str
    email: str
    url: str | None = None


@router.post("/open-browser")
async def open_browser(body: OpenBrowserBody):
    _log.info("open_browser request: service=%s email=%s url=%s", body.service, body.email, body.url)
    acc = await get_account(body.service.upper(), body.email)
    if not acc:
        _log.warning("open_browser: account not found — service=%s email=%s", body.service, body.email)
        raise AppError(ErrorCode.NOT_FOUND, "Account not found", 404)
    if not acc.get("session_state"):
        _log.warning("open_browser: no session_state — service=%s email=%s", body.service, body.email)
        raise AppError(ErrorCode.VALIDATION, "Account has no saved session", 400)
    cfg = load_config()
    result = await open_browser_window(
        body.service.upper(),
        body.email,
        cfg.api.host_browser_agent_url,
        body.url,
    )
    return ok(result)


@router.get("/{service}/{email:path}")
async def get_one(service: str, email: str):
    acc = await get_account(service.upper(), email)
    if not acc:
        raise AppError(ErrorCode.NOT_FOUND, "Account not found", 404)
    return ok(acc)


@router.patch("/{service}/{email:path}")
async def patch_account(service: str, email: str, body: UpdateAccountBody):
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if not fields:
        raise AppError(ErrorCode.VALIDATION, "No fields to update", 400)
    updated = await update_account_fields(service.upper(), email, **fields)
    if not updated:
        raise AppError(ErrorCode.NOT_FOUND, "Account not found", 404)
    return ok({"updated": True})


@router.delete("/{service}/{email:path}")
async def delete_one(service: str, email: str):
    deleted = await remove_account(service.upper(), email)
    if not deleted:
        raise AppError(ErrorCode.NOT_FOUND, "Account not found", 404)
    return ok({"deleted": True})
