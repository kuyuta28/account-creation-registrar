"""
relogin_aa.py — Browser Gateway task: re-login Artificial Analysis qua magic link.

Chạy trên host (gateway mở browser camoufox). KHÔNG trong container.
Flow: fill email → magic link testmail → navigate → accept Image Lab terms → save session.

Tái dùng flow helpers từ src.services.artificialanalysis_ai.registrar (FP modules,
nhận page/mailbox/cfg qua args — pure, không mở browser).
"""
from __future__ import annotations

from typing import Any

from playwright.async_api import Browser

from ....core.google_oauth._helpers import LogFn
from ._registry import register  # noqa: F401  — side-effect: đăng ký task


@register("relogin_aa", engine="camoufox")
async def relogin_aa(
    *, browser: Browser, args: dict[str, Any], log_fn: LogFn | None = None,
) -> dict[str, Any]:
    """Re-login AA cho 1 email (testmail.app). Lưu session_state + check_status=valid.

    args: {"email": str}
    Trả về {"email": str, "ok": True} hoặc raise.
    """
    import asyncio
    import json

    from common.database._async import update_account_async
    from common.database._engine import get_async_session
    from ....config.settings import load_config
    from ....services.artificialanalysis_ai.flow import (
        _fetch_magic_link,
        _fill_email_and_submit,
        _navigate_magic_link,
        _reconstruct_testmail_mailbox,
    )

    email = args["email"]
    cfg = load_config()
    t = cfg.timeouts
    aa_cfg = cfg.artificialanalysis
    log = log_fn or (lambda m: None)

    mailbox = _reconstruct_testmail_mailbox(email, cfg, log)

    ctx = await browser.new_context()
    try:
        page = await ctx.new_page()

        log(f"[1/4] Opening {aa_cfg.login_url}...")
        await page.goto(aa_cfg.login_url, timeout=t.page_load * 2, wait_until="domcontentloaded")
        await page.wait_for_timeout(t.nav_delay)

        log("[2/4] Filling email & submitting...")
        await _fill_email_and_submit(page, email, log)
        await page.wait_for_timeout(aa_cfg.post_submit_wait_ms)
        log("  Magic link sent — waiting for email")

        log(f"[3/4] Waiting for magic link (up to {aa_cfg.magic_link_wait_sec}s)...")
        link = await _fetch_magic_link(mailbox, aa_cfg.magic_link_wait_sec, log)
        log(f"  Link: {link[:80]}...")

        log("[4/4] Navigating magic link...")
        await _navigate_magic_link(page, link, aa_cfg.base_url, t.page_load, log)

        state = await ctx.storage_state()
    finally:
        await ctx.close()

    async with get_async_session() as session:
        await update_account_async(
            session, "ARTIFICIALANALYSIS", email,
            {"session_state": json.dumps(state, ensure_ascii=False), "check_status": "valid"},
        )

    log(f"✅ Session refreshed + check_status = valid cho {email}")
    return {"email": email, "ok": True}
