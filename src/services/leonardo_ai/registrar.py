"""services/leonardo_ai/registrar.py - Leonardo registration entrypoint.

Delegate browser work cho Browser Gateway (host camoufox) — container không có
camoufox binary. Gateway task `register_leonardo` tạo mailbox + chạy `_run`
(state-machine signup, xem `flow.py`), trả record dict; container save_fn lưu DB.

Automation recipe tách riêng trong `flow.py` — file này chỉ orchestration.
"""
from __future__ import annotations

import asyncio

from ...config.settings import AppConfig
from src.core.account_record import AccountRecord
from ..protocols import LogFn, SaveFn


async def register_leonardo(
    cfg: AppConfig,
    log_fn: LogFn,
    save_fn: SaveFn,
) -> AccountRecord | None:
    """Leonardo registration entrypoint (delegate → Browser Gateway)."""
    from common.browser_gateway_client import BrowserGatewayError, run_browser_task

    gateway_url = cfg.api.host_browser_agent_url
    if not gateway_url:
        raise RuntimeError(
            "HOST_BROWSER_AGENT_URL chưa cấu hình — không thể register Leonardo. "
            "Chạy Browser Gateway trên host (py registrar/tools/host_browser_agent.py)."
        )

    max_attempts = cfg.register.max_attempts
    for attempt in range(1, max_attempts + 1):
        if attempt > 1:
            log_fn(f"\nRetry {attempt}/{max_attempts}")
        log_fn("🔑 Register Leonardo (qua gateway)")
        log_fn("-" * 50)

        try:
            result = await run_browser_task(
                gateway_url, "register_leonardo",
                args={},
                on_log=log_fn,
            )
        except BrowserGatewayError as exc:
            log_fn(f"\n{exc}")
            if attempt < max_attempts:
                log_fn("  Starting over with a fresh email...")
                continue
            raise RuntimeError(f"Gateway register Leonardo thất bại: {exc}") from exc

        record = AccountRecord(
            service="LEONARDO",
            email=result["email"],
            password=result["password"],
        )
        await asyncio.to_thread(save_fn, record)
        log_fn("💾 Saved to DB")
        return record

    log_fn(f"\n❌ Failed after {max_attempts} attempts")
    return None
