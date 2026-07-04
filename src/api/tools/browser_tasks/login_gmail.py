"""
login_gmail.py — Browser Gateway task: login Google cho 1 mailbox.

Chạy trên host (gateway mở browser camoufox). Capture storage_state, lưu DB.
"""
from __future__ import annotations

from typing import Any

from playwright.async_api import Browser

from ....core.google_oauth._helpers import LogFn
from ._registry import register


@register("login_gmail", engine="camoufox")
async def login_gmail(
    *, browser: Browser, args: dict[str, Any], log_fn: LogFn | None = None,
) -> dict[str, Any]:
    """
    Login Google cho 1 mailbox, capture storage_state, lưu DB.
    args: {"email": str}
    Trả về {"email": str, "ok": True} hoặc raise.
    """
    import json

    from common.database._async import (
        get_mailbox_record_async,
        save_mailbox_google_auth_state_async,
    )
    from common.database._engine import get_async_session
    from ....core.google_oauth import login_google_on_page
    from ....core.google_oauth._constants import get_login_url, get_login_timeout_ms

    email = args["email"]

    async with get_async_session() as session:
        record = await get_mailbox_record_async(session, email)
    if not record:
        raise ValueError(f"Mailbox không tồn tại: {email!r}")
    password = record.get("password", "")
    if not password:
        raise ValueError(f"Mailbox {email!r} chưa có password Google — không thể login")
    totp_secret = record.get("totp_secret", "")

    ctx = await browser.new_context()
    try:
        page = await ctx.new_page()
        await page.goto(get_login_url(), wait_until="domcontentloaded")
        await login_google_on_page(page, email, password, totp_secret, log_fn=log_fn)
        await page.wait_for_url(
            lambda u: "accounts.google.com" not in u,
            timeout=get_login_timeout_ms(), wait_until="commit",
        )
        state = await ctx.storage_state()
    finally:
        await ctx.close()

    auth_state = json.dumps(state)
    async with get_async_session() as session:
        saved = await save_mailbox_google_auth_state_async(session, email, auth_state)
    if not saved:
        raise RuntimeError(f"Lưu session thất bại cho {email!r}")

    return {"email": email, "ok": True}
