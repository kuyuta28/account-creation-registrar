"""services/openrouter_ai/registrar.py - OpenRouter registration entrypoint.

Delegate browser work cho Browser Gateway (host camoufox) — container không có
camoufox binary. Gateway task `register_openrouter` tạo mailbox + chạy
`_signup_flow` (xem `flow.py`), trả record dict; container save_fn lưu DB.

Automation recipe tách riêng trong `flow.py` — file này chỉ orchestration.
"""
from __future__ import annotations

import asyncio

from ...config.settings import AppConfig
from src.core.account_record import AccountRecord
from ..protocols import LogFn, SaveFn


async def register_openrouter(
    cfg: AppConfig,
    log_fn: LogFn,
    save_fn: SaveFn,
) -> AccountRecord | None:
    """OpenRouter registration entrypoint (delegate → Browser Gateway)."""
    from common.browser_gateway_client import BrowserGatewayError, run_browser_task

    gateway_url = cfg.api.host_browser_agent_url
    if not gateway_url:
        raise RuntimeError(
            "HOST_BROWSER_AGENT_URL chưa cấu hình — không thể register OpenRouter. "
            "Chạy Browser Gateway trên host (py registrar/tools/host_browser_agent.py)."
        )

    log_fn("🔑 Register OpenRouter (qua gateway)")
    log_fn("-" * 50)

    try:
        result = await run_browser_task(
            gateway_url, "register_openrouter",
            args={},
            on_log=log_fn,
        )
    except BrowserGatewayError as exc:
        raise RuntimeError(f"Gateway register OpenRouter thất bại: {exc}") from exc

    record = AccountRecord(
        service="OPENROUTER",
        email=result["email"],
        password=result["password"],
        api_key=result["api_key"],
    )
    await asyncio.to_thread(save_fn, record)
    log_fn("✅ Saved to DB")
    return record
