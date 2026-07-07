"""register_openrouter.py — Browser Gateway task: đăng ký OpenRouter account.

Chạy trên host (gateway mở camoufox). KHÔNG trong container (container không có
camoufox binary). Container gọi run_browser_task("register_openrouter").

Flow: mailbox → signup form → Turnstile → magic link email → enable privacy
→ create API key → trả record dict.
"""
from __future__ import annotations

from typing import Any

from playwright.async_api import Browser

from ....core.google_oauth._helpers import LogFn
from ._registry import register  # noqa: F401  — side-effect: đăng ký task


@register("register_openrouter", engine="camoufox")
async def register_openrouter(
    *, browser: Browser, args: dict[str, Any], log_fn: LogFn | None = None,
) -> dict[str, Any]:
    """Đăng ký 1 OpenRouter account qua camoufox.

    Trả về {"email","password","api_key"} hoặc raise.
    """
    from ....config.settings import load_config
    from common.password import generate_password
    from ....mail._base import MailCfg
    from ....mail.client import create_mailbox
    from ....services.openrouter_ai.flow import _signup_flow

    cfg = load_config()
    log = log_fn or (lambda m: None)

    mail_cfg = MailCfg(
        cooldown_sec=cfg.mail.cooldown_sec,
        max_consecutive_fails=cfg.mail.max_consecutive_fails,
        testmail_monthly_quota=cfg.mail.testmail_monthly_quota,
    )
    mailbox = await create_mailbox(
        cfg.mail.providers_for("openrouter"), cfg=mail_cfg, log_fn=log, service_tag="openrouter",
    )
    email = mailbox.email
    password = generate_password(cfg.register.password_length)
    log(f"Email: {email}")
    log("Password: ****")
    log("-" * 50)

    ctx = await browser.new_context()
    try:
        page = await ctx.new_page()
        record = await _signup_flow(page, browser, mailbox, email, password, cfg, log)
    finally:
        await ctx.close()

    log(f"✅ OpenRouter account created: {record.email} (api_key {len(record.api_key)} chars)")
    return {
        "email": record.email,
        "password": record.password,
        "api_key": record.api_key,
    }
