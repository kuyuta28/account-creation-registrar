"""services/testmail_app/registrar.py — testmail.app registration entrypoint.

Delegate browser work cho Browser Gateway (host camoufox) — container không có
camoufox binary. Gateway task `register_testmail` chạy `_signup_flow` (xem
`flow.py`), trả record dict; container save_fn lưu DB.

Testmail = 1 bảng (accounts_testmail) vừa identity vừa pool pickup. Reg xong
chỉ cần save_fn (insert_account_async) → accounts + accounts_testmail. KHÔNG
upsert mail_providers (đường SQLite legacy đã xóa).

Automation recipe tách riêng trong `flow.py` — file này chỉ orchestration.
"""
from __future__ import annotations

import asyncio

from ...config.settings import AppConfig
from src.core.account_record import AccountRecord
from ..protocols import LogFn, SaveFn


async def register_testmail(
    cfg: AppConfig,
    log_fn: LogFn,
    save_fn: SaveFn,
) -> AccountRecord | None:
    """testmail.app registration entrypoint (delegate → Browser Gateway)."""
    from common.browser_gateway_client import BrowserGatewayError, run_browser_task

    gateway_url = cfg.api.host_browser_agent_url
    if not gateway_url:
        raise RuntimeError(
            "HOST_BROWSER_AGENT_URL chưa cấu hình — không thể register testmail. "
            "Chạy Browser Gateway trên host (py registrar/tools/host_browser_agent.py)."
        )

    max_attempts = cfg.register.max_attempts
    for attempt in range(1, max_attempts + 1):
        if attempt > 1:
            log_fn(f"\n🔄 Retry {attempt}/{max_attempts}")
        log_fn("🔑 Register testmail.app (qua gateway)")
        log_fn("-" * 50)

        try:
            result = await run_browser_task(
                gateway_url, "register_testmail",
                args={},
                on_log=log_fn,
            )
        except BrowserGatewayError as exc:
            log_fn(f"\n⚠️  {exc}")
            if attempt < max_attempts:
                log_fn("  → Retrying with a fresh email...")
                continue
            raise RuntimeError(f"Gateway register testmail thất bại: {exc}") from exc

        record = AccountRecord(
            service="TESTMAIL",
            email=result["email"],
            password="",
            api_key=result["api_key"],
        )
        await asyncio.to_thread(save_fn, record)
        log_fn("✅ Saved to DB")
        return record

    log_fn(f"\n❌ Failed after {max_attempts} attempts")
    return None
