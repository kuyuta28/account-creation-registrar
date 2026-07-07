"""services/artificialanalysis_ai/registrar.py — AA registration entrypoints.

Delegate browser work cho Browser Gateway (host camoufox) — container không có
camoufox binary. Gateway tasks `register_artificialanalysis` / `relogin_aa` chạy
`_signup_flow` / relogin flow (xem `flow.py`), trả record dict; container
save_fn lưu DB.

Automation recipe tách riêng trong `flow.py` — file này chỉ orchestration.
"""
from __future__ import annotations

import asyncio

from ...config.settings import AppConfig
from common.browser_gateway_client import BrowserGatewayError, run_browser_task
from src.core.account_record import AccountRecord
from ..protocols import LogFn, SaveFn


async def relogin_artificialanalysis(
    email: str,
    cfg: AppConfig,
    log_fn: LogFn,
) -> None:
    """Re-login tài khoản AA qua magic link. Cập nhật session_state trong DB.

    Delegate browser work cho Browser Gateway (chạy trên host) — container không
    còn mở camoufox trực tiếp (camoufox binary chỉ có trên host).
    Engine: camoufox. Flow xử lý trong gateway task `relogin_aa`.
    """
    gateway_url = cfg.api.host_browser_agent_url
    if not gateway_url:
        raise RuntimeError(
            "HOST_BROWSER_AGENT_URL chưa cấu hình — không thể relogin AA. "
            "Chạy Browser Gateway trên host (py registrar/tools/host_browser_agent.py)."
        )

    log_fn(f"🔑 Re-login AA: {email} (qua gateway)")
    log_fn("-" * 50)
    try:
        await run_browser_task(
            gateway_url, "relogin_aa",
            args={"email": email},
            on_log=log_fn,
        )
    except BrowserGatewayError as e:
        raise RuntimeError(f"Gateway relogin AA thất bại cho {email}: {e}") from e


async def register_artificialanalysis(
    cfg: AppConfig,
    log_fn: LogFn,
    save_fn: SaveFn,
) -> AccountRecord | None:
    """Artificial Analysis registration entrypoint (delegate → Browser Gateway)."""
    max_attempts = cfg.register.max_attempts
    for attempt in range(1, max_attempts + 1):
        if attempt > 1:
            log_fn(f"\n🔄 Retry {attempt}/{max_attempts}")
        log_fn("🔑 Register Artificial Analysis (qua gateway)")
        log_fn("-" * 50)

        gateway_url = cfg.api.host_browser_agent_url
        if not gateway_url:
            raise RuntimeError(
                "HOST_BROWSER_AGENT_URL chưa cấu hình — không thể register AA. "
                "Chạy Browser Gateway trên host (py registrar/tools/host_browser_agent.py)."
            )

        try:
            result = await run_browser_task(
                gateway_url, "register_artificialanalysis",
                args={},
                on_log=log_fn,
            )
        except BrowserGatewayError as exc:
            log_fn(f"\n⚠️  {exc}")
            if attempt < max_attempts:
                log_fn("  → Retrying with a fresh email...")
                continue
            raise RuntimeError(f"Gateway register AA thất bại: {exc}") from exc

        record = AccountRecord(
            service="ARTIFICIALANALYSIS",
            email=result["email"],
            password=result.get("password", ""),
            api_key=result.get("api_key", ""),
        )
        await asyncio.to_thread(save_fn, record)
        log_fn("✅ Saved to DB")
        return record

    log_fn(f"\n❌ Failed after {max_attempts} attempts")
    return None
