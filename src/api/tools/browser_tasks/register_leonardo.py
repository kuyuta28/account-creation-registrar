"""register_leonardo.py — Browser Gateway task: đăng ký Leonardo AI account.

Chạy trên host (gateway mở camoufox). KHÔNG trong container (container không có
camoufox binary). Container gọi run_browser_task("register_leonardo").

Flow: mailbox → Leonardo auth state-machine (email/turnstile/code/password/name)
→ dashboard → trả record dict.
"""
from __future__ import annotations

from typing import Any

from playwright.async_api import Browser

from ....core.google_oauth._helpers import LogFn
from ._registry import register  # noqa: F401  — side-effect: đăng ký task


@register("register_leonardo", engine="camoufox")
async def register_leonardo(
    *, browser: Browser, args: dict[str, Any], log_fn: LogFn | None = None,
) -> dict[str, Any]:
    """Đăng ký 1 Leonardo AI account qua camoufox.

    Trả về {"email","password"} hoặc raise.
    """
    from ....config.settings import load_config
    from common.password import generate_password
    from ....mail._base import MailCfg
    from ....mail.client import create_mailbox
    from ....services.leonardo_ai.flow import _run

    cfg = load_config()
    log = log_fn or (lambda m: None)

    mail_cfg = MailCfg(
        cooldown_sec=cfg.mail.cooldown_sec,
        max_consecutive_fails=cfg.mail.max_consecutive_fails,
        testmail_monthly_quota=cfg.mail.testmail_monthly_quota,
    )
    mailbox = await create_mailbox(
        cfg.mail.providers_for("leonardo"), cfg=mail_cfg, log_fn=log, service_tag="leonardo",
    )
    email = mailbox.email
    password = generate_password(cfg.register.password_length)
    log(f"Email: {email}")
    log("Password: ****")
    log("-" * 50)

    ctx = await browser.new_context()
    try:
        page = await ctx.new_page()
        record = await _run(page, mailbox, email, password, cfg, log)
    finally:
        await ctx.close()

    if not record:
        raise RuntimeError("Leonardo signup did not produce a record")
    log(f"✅ Leonardo account created: {record.email}")
    return {
        "email": record.email,
        "password": record.password,
    }
