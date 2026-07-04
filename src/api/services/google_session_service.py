"""
google_session_service.py — Login Google và lưu storage_state vào mailbox.

Business logic layer — delegate browser work cho Browser Gateway (chạy trên host).
Không còn mở browser trực tiếp trong container.
"""
from __future__ import annotations

import logging
from typing import Any

from ...config.settings import load_config
from common.browser_gateway_client import BrowserGatewayError, run_browser_task
from common.database._async import (
    get_mailboxes_async,
)

_log = logging.getLogger(__name__)


async def refresh_google_session(email: str) -> dict[str, Any]:
    """
    Login Google cho 1 mailbox qua Browser Gateway (engine=edge, host).
    Handler login_gmail tự capture storage_state và lưu DB.
    """
    cfg = load_config()
    gateway_url = cfg.api.host_browser_agent_url
    if not gateway_url:
        raise RuntimeError(
            "HOST_BROWSER_AGENT_URL chưa cấu hình — không thể login Google. "
            "Chạy Browser Gateway trên host (py registrar/tools/host_browser_agent.py)."
        )

    _log.info("[google_session] Đang login Google cho %s qua gateway", email)
    try:
        result = await run_browser_task(
            gateway_url, "login_gmail",
            args={"email": email},
            on_log=lambda m: _log.info("[google_session/%s] %s", email, m),
        )
    except BrowserGatewayError as e:
        _log.error("[google_session] Gateway lỗi cho %s: %s", email, e)
        raise

    _log.info("[google_session] Đã lưu session cho %s", email)
    return {"email": email, "ok": True, **result}


async def refresh_all_google_sessions() -> list[dict[str, Any]]:
    """
    Login Google cho tất cả mailboxes có password, chạy song song qua gateway
    (gateway có semaphore giới hạn concurrency).
    """
    import asyncio
    from common.database._engine import get_async_session

    async with get_async_session() as session:
        mailboxes = await get_mailboxes_async(session)
    targets = [m for m in mailboxes if m.get("password") and not m.get("disabled")]

    if not targets:
        return []

    async def _one(email: str) -> dict[str, Any]:
        try:
            return await refresh_google_session(email)
        except Exception as e:  # noqa: BLE001 — batch: per-item isolation
            _log.error("[google_session] Lỗi %s: %s", email, e)
            return {"email": email, "ok": False, "error": str(e)}

    return await asyncio.gather(*[_one(m["email"]) for m in targets])
