"""register_testmail.py — Browser Gateway task: đăng ký testmail.app account.

Chạy trên host (gateway mở camoufox). KHÔNG trong container (container không có
camoufox binary). Container gọi run_browser_task("register_testmail").

Flow: mail.tm mailbox → signup form → email verification code → /console/
extract namespace + API key → trả record dict. Container nhận dict + save_fn
lưu DB + upsert mail provider.
"""
from __future__ import annotations

from typing import Any

from playwright.async_api import Browser

from ....core.google_oauth._helpers import LogFn
from ._registry import register  # noqa: F401  — side-effect: đăng ký task


@register("register_testmail", engine="camoufox")
async def register_testmail(
    *, browser: Browser, args: dict[str, Any], log_fn: LogFn | None = None,
) -> dict[str, Any]:
    """Đăng ký 1 testmail.app account qua camoufox.

    Trả về {"email","api_key"} (api_key = "testmail.app:NS:KEY") hoặc raise.
    """
    from ....config.settings import load_config
    from ....mail.client import create_mailbox
    from ....services.testmail_app.flow import _signup_flow

    cfg = load_config()
    log = log_fn or (lambda m: None)

    # register_testmail = sinh namespace mới (refill pool), KHÔNG tiêu quota.
    # Dùng mail.tm làm mailbox nhận verify code từ testmail.app signup.
    mailbox = await create_mailbox(cfg.mail.providers_for("testmail"), log_fn=log)
    log(f"Email (mail.tm): {mailbox.email}")
    log("-" * 50)

    ctx = await browser.new_context()
    try:
        page = await ctx.new_page()
        record = await _signup_flow(page, mailbox, cfg, log)
    finally:
        await ctx.close()

    log(f"✅ testmail account created: {record.email} (api_key {len(record.api_key)} chars)")
    return {
        "email": record.email,
        "api_key": record.api_key,
    }
