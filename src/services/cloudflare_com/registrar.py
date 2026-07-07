"""services/cloudflare_com/registrar.py - Cloudflare registration entrypoint.

Delegate browser work cho Browser Gateway (host camoufox) — container không có
camoufox binary. Gateway task `register_cloudflare` chạy `_signup_flow` (xem
`flow.py`), trả record dict; container save_fn lưu DB + add vào 9Router.

Automation recipe tách riêng trong `flow.py` — file này chỉ orchestration
(invoke gateway + persist + post-registration hooks).
"""
from __future__ import annotations

import asyncio

from ...config.settings import AppConfig
from src.core.account_record import AccountRecord
from ..protocols import LogFn, SaveFn


async def register_cloudflare(
    cfg: AppConfig,
    log_fn: LogFn,
    save_fn: SaveFn,
) -> AccountRecord | None:
    """Cloudflare registration entrypoint (delegate → Browser Gateway)."""
    from common.browser_gateway_client import BrowserGatewayError, run_browser_task

    gateway_url = cfg.api.host_browser_agent_url
    if not gateway_url:
        raise RuntimeError(
            "HOST_BROWSER_AGENT_URL chưa cấu hình — không thể register Cloudflare. "
            "Chạy Browser Gateway trên host (py registrar/tools/host_browser_agent.py)."
        )

    max_attempts = cfg.register.max_attempts
    for attempt in range(1, max_attempts + 1):
        if attempt > 1:
            log_fn(f"\nRetry attempt {attempt}/{max_attempts}")
        log_fn("🔑 Register Cloudflare (qua gateway)")
        log_fn("-" * 50)

        try:
            result = await run_browser_task(
                gateway_url, "register_cloudflare",
                args={},
                on_log=log_fn,
            )
        except BrowserGatewayError as exc:
            msg = str(exc)
            if "Email verification" in msg and attempt < max_attempts:
                log_fn(f"\nEmail verification failed: {exc}")
                log_fn("  Retrying with fresh mailbox...")
                continue
            if "RetryableRegistration" in msg and attempt < max_attempts:
                log_fn(f"\nRegistration error: {exc}")
                log_fn("  Retrying...")
                continue
            raise RuntimeError(f"Gateway register Cloudflare thất bại: {exc}") from exc

        record = AccountRecord(
            service="CLOUDFLARE",
            email=result["email"],
            password=result["password"],
            api_key=result["api_key"],
            account_id=result["account_id"],
        )
        await asyncio.to_thread(save_fn, record)
        log_fn("\nSaved to DB")

        await _add_to_9router(record, gateway_url, log_fn)
        return record

    log_fn(f"\nFailed after {max_attempts} attempts")
    return None


async def _add_to_9router(
    record: AccountRecord, gateway_url: str, log_fn: LogFn,
) -> None:
    """Add CF account vừa tạo vào 9Router dashboard (qua gateway task).

    9Router Check verify token qua CF API: valid → Save, invalid → set
    check_status=invalid trên base table. Gateway error → raise (không nuốt).
    """
    from common.browser_gateway_client import BrowserGatewayError, run_browser_task
    from common.database._async import update_account_async
    from common.database._engine import get_async_session

    log_fn("\n[9Router] Add account...")
    try:
        result = await run_browser_task(
            gateway_url, "add_cf_to_9router",
            args={
                "email": record.email,
                "api_key": record.api_key,
                "account_id": record.account_id,
            },
            on_log=log_fn,
        )
    except BrowserGatewayError as exc:
        raise RuntimeError(f"9Router add thất bại: {exc}") from exc

    if result.get("valid"):
        log_fn("[9Router] ✅ valid + saved")
        return

    # Token invalid → mark account lỗi trên base table (DB-only field, không qua AccountRecord).
    log_fn("[9Router] ⚠ check = invalid → check_status=invalid")
    async with get_async_session() as session:
        await update_account_async(
            session, "CLOUDFLARE", record.email, {"check_status": "invalid"},
        )
