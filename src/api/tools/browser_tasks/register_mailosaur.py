"""register_mailosaur.py — Browser Gateway task: đăng ký Mailosaur account.

Chạy trên host (gateway mở camoufox). KHÔNG trong container (container không có
camoufox binary). Container gọi run_browser_task("register_mailosaur").

Flow: testmail.app mailbox → signup → OTP → onboard → use-case → framework
→ first inbox → extract SERVER_ID + API key → trả record dict.
"""
from __future__ import annotations

from typing import Any

from playwright.async_api import Browser

from ....core.google_oauth._helpers import LogFn
from ._registry import register  # noqa: F401  — side-effect: đăng ký task


@register("register_mailosaur", engine="camoufox")
async def register_mailosaur(
    *, browser: Browser, args: dict[str, Any], log_fn: LogFn | None = None,
) -> dict[str, Any]:
    """Đăng ký 1 Mailosaur account qua camoufox.

    Trả về {"email","password","api_key","account_id"} hoặc raise.
    """
    from ....config.settings import load_config
    from ....mail._base import MailCfg
    from ....mail.client import create_mailbox
    from ....services.mailosaur_com.flow import _signup_flow

    cfg = load_config()
    log = log_fn or (lambda m: None)

    # Mailosaur cần inbox.testmail.app (mail.tm bị chặn) — DB counting pick namespace.
    all_providers = cfg.mail.providers_for()
    has_testmail = any(p.startswith("testmail.app:") for p in all_providers)
    if not has_testmail:
        raise RuntimeError("Không có testmail.app provider nào trong DB — cần đăng ký TESTMAIL trước")

    mail_cfg = MailCfg(
        cooldown_sec=cfg.mail.cooldown_sec,
        max_consecutive_fails=cfg.mail.max_consecutive_fails,
        testmail_monthly_quota=cfg.mail.testmail_monthly_quota,
    )
    mailbox = await create_mailbox(
        tuple(p for p in all_providers if p.startswith("testmail.app:")),
        cfg=mail_cfg, log_fn=log, service_tag="mailosaur",
    )
    log(f"Email (testmail.app): {mailbox.email}")
    log("-" * 50)

    ctx = await browser.new_context()
    try:
        page = await ctx.new_page()
        record = await _signup_flow(page, mailbox, cfg, log)
    finally:
        await ctx.close()

    log(f"✅ Mailosaur account created: {record.email} (server_id={record.account_id})")
    return {
        "email": record.email,
        "password": record.password,
        "api_key": record.api_key,
        "account_id": record.account_id,
    }
