"""refresh_kling_session.py — Browser Gateway task: refresh Kling AI session cookies.

Chạy trên host (gateway mở camoufox). KHÔNG trong container. Container gọi
run_browser_task("refresh_kling_session").

Flow: load session_state từ DB → new_context(storage_state) → visit 2 URL
→ capture state mới → trả về dict. Container so sánh expiry + save DB.
"""
from __future__ import annotations

from typing import Any

from playwright.async_api import Browser

from ....core.google_oauth._helpers import LogFn
from ._registry import register  # noqa: F401  — side-effect: đăng ký task


@register("refresh_kling_session", engine="camoufox")
async def refresh_kling_session(
    *, browser: Browser, args: dict[str, Any], log_fn: LogFn | None = None,
) -> dict[str, Any]:
    """Visit Kling AI với session_state hiện có để slide cookie expiry.

    args: {"email": str}
    Trả về {"email": str, "ok": True, "cookies": [...]} hoặc raise.
    """
    import json

    from common.database._async import get_account_by_email_async
    from common.database._engine import get_async_session
    from ....config.settings import load_config

    email = args["email"]
    cfg = load_config()
    log = log_fn or (lambda m: None)

    async with get_async_session() as session:
        acc = await get_account_by_email_async(session, "KLING", email)
    if not acc:
        raise ValueError(f"Account không tồn tại: KLING/{email}")
    session_json = acc.get("session_state", "")
    if not session_json:
        raise RuntimeError(f"Không có session_state cho {email}")

    storage_state = json.loads(session_json)
    ctx = await browser.new_context(storage_state=storage_state)
    try:
        page = await ctx.new_page()
        await page.goto(cfg.klingai.refresh_start_url, wait_until="commit", timeout=cfg.klingai.refresh_start_timeout_ms)
        await page.wait_for_timeout(cfg.klingai.refresh_start_wait_ms)
        await page.goto(cfg.klingai.refresh_target_url, wait_until="commit", timeout=cfg.klingai.refresh_target_timeout_ms)
        await page.wait_for_timeout(cfg.klingai.refresh_target_wait_ms)
        new_state = await ctx.storage_state()
    finally:
        await ctx.close()

    log(f"✅ Kling session refreshed cho {email}")
    return {"email": email, "ok": True, "state": new_state}
