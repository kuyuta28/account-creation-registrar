"""register_artificialanalysis.py — Browser Gateway task: đăng ký AA account.

Chạy trên host (gateway mở camoufox). KHÔNG trong container (container không có
camoufox binary). Container gọi run_browser_task("register_artificialanalysis").

Flow: create_mailbox → fill email → magic link → navigate → accept Image Lab terms
→ create API key → save session_state về DB → trả record dict.
"""
from __future__ import annotations

from typing import Any

from playwright.async_api import Browser

from ....core.google_oauth._helpers import LogFn
from ._registry import register  # noqa: F401  — side-effect: đăng ký task


@register("register_artificialanalysis", engine="camoufox")
async def register_artificialanalysis(
    *, browser: Browser, args: dict[str, Any], log_fn: LogFn | None = None,
) -> dict[str, Any]:
    """Đăng ký 1 Artificial Analysis account qua camoufox.

    Trả về {"email","password","api_key"} hoặc raise.
    """
    from common.session import save_session
    from ....config.settings import load_config
    from ....mail._base import MailCfg
    from ....mail.client import create_mailbox
    from ....services.artificialanalysis_ai.flow import _signup_flow

    cfg = load_config()
    log = log_fn or (lambda m: None)

    mail_cfg = MailCfg(
        cooldown_sec=cfg.mail.cooldown_sec,
        max_consecutive_fails=cfg.mail.max_consecutive_fails,
        testmail_monthly_quota=cfg.mail.testmail_monthly_quota,
    )
    mailbox = await create_mailbox(
        cfg.mail.providers_for("artificialanalysis"), cfg=mail_cfg, log_fn=log, service_tag="artificialanalysis",
    )
    email = mailbox.email
    log(f"Email: {email}")
    log("-" * 50)

    ctx = await browser.new_context()
    try:
        page = await ctx.new_page()
        record = await _signup_flow(page, mailbox, email, cfg, log)
        await save_session("ARTIFICIALANALYSIS", email, ctx)
        log("✅ Session saved")
    finally:
        await ctx.close()

    log(f"✅ AA account created: {record.email} (api_key {len(record.api_key)} chars)")
    return {
        "email": record.email,
        "password": record.password,
        "api_key": record.api_key,
    }
