"""register_cloudflare.py — Browser Gateway task: đăng ký Cloudflare account.

Chạy trên host (gateway mở camoufox). KHÔNG trong container (container không có
camoufox binary). Container gọi run_browser_task("register_cloudflare").

Flow: testmail mailbox → sign-up → solve Turnstile → verify email → skip onboarding
→ tạo API token → trả record dict. Container nhận dict + save_fn lưu DB.
"""
from __future__ import annotations

from typing import Any

from playwright.async_api import Browser

from ....core.google_oauth._helpers import LogFn
from ._registry import register  # noqa: F401  — side-effect: đăng ký task


@register("register_cloudflare", engine="camoufox")
async def register_cloudflare(
    *, browser: Browser, args: dict[str, Any], log_fn: LogFn | None = None,
) -> dict[str, Any]:
    """Đăng ký 1 Cloudflare account qua camoufox.

    Trả về {"email","password","api_key","account_id"} hoặc raise.
    """
    from ....config.settings import load_config
    from ....mail.client import create_mailbox
    from ....services.cloudflare_com.registrar import _signup_flow

    cfg = load_config()
    log = log_fn or (lambda m: None)

    providers = cfg.mail.providers_for("cloudflare")
    mailbox = await create_mailbox(providers, log_fn=log)
    log(f"Email: {mailbox.email}")
    log("-" * 50)

    ctx = await browser.new_context()
    try:
        page = await ctx.new_page()
        record = await _signup_flow(page, mailbox, cfg, log)
    finally:
        await ctx.close()

    log(f"✅ Cloudflare account created: {record.email} (api_key {len(record.api_key)} chars)")
    return {
        "email": record.email,
        "password": record.password,
        "api_key": record.api_key,
        "account_id": record.account_id,
    }
