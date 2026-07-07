"""services/mailosaur_com/registrar.py — Mailosaur registration entrypoint.

Delegate browser work cho Browser Gateway (host camoufox) — container không có
camoufox binary. Gateway task `register_mailosaur` chọn testmail.app provider +
chạy `_signup_flow` (xem `flow.py`), trả record dict; container save_fn lưu DB.

Mailosaur = account 2 mặt (identity accounts_mailosaur + pool mail_providers).
Reg xong save_fn (insert_account_async) → accounts + accounts_mailosaur.
Pool pickup (mail_providers) dùng cho service khác — sync qua Postgres async,
KHÔNG qua SQLite path (đã xóa).

Automation recipe tách riêng trong `flow.py` — file này chỉ orchestration.
"""
from __future__ import annotations

import asyncio

from ...config.settings import AppConfig
from src.core.account_record import AccountRecord
from ..protocols import LogFn, SaveFn


async def register_mailosaur(
    cfg: AppConfig,
    log_fn: LogFn,
    save_fn: SaveFn,
) -> AccountRecord | None:
    """Mailosaur registration entrypoint (delegate → Browser Gateway)."""
    from common.browser_gateway_client import BrowserGatewayError, run_browser_task

    gateway_url = cfg.api.host_browser_agent_url
    if not gateway_url:
        raise RuntimeError(
            "HOST_BROWSER_AGENT_URL chưa cấu hình — không thể register Mailosaur. "
            "Chạy Browser Gateway trên host (py registrar/tools/host_browser_agent.py)."
        )

    log_fn("🔑 Register Mailosaur (qua gateway)")
    log_fn("-" * 50)

    try:
        result = await run_browser_task(
            gateway_url, "register_mailosaur",
            args={},
            on_log=log_fn,
        )
    except BrowserGatewayError as exc:
        raise RuntimeError(f"Gateway register Mailosaur thất bại: {exc}") from exc

    record = AccountRecord(
        service="MAILOSAUR",
        email=result["email"],
        password=result["password"],
        api_key=result["api_key"],
        account_id=result["account_id"],
    )
    await asyncio.to_thread(save_fn, record)
    log_fn("\n✅ Đăng ký thành công!")
    log_fn(f"   Email:     {record.email}")
    log_fn(f"   API key:   {record.api_key[:20]}...")
    log_fn(f"   Server ID: {record.account_id}")
    return record
