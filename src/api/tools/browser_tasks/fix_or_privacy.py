"""fix_or_privacy.py — Browser Gateway task: enable OpenRouter privacy toggles cho 1 account.

Chạy trên host (gateway mở camoufox). KHÔNG trong container. Container gọi
run_browser_task("fix_or_privacy") per-account (batch concurrent ở container).

Flow: login OpenRouter (email/password) → goto privacy settings → enable toggles
(trừ ZDR keywords) → trả status dict.
"""
from __future__ import annotations

from typing import Any

from playwright.async_api import Browser

from ....core.google_oauth._helpers import LogFn
from ._registry import register  # noqa: F401  — side-effect: đăng ký task


@register("fix_or_privacy", engine="camoufox")
async def fix_or_privacy(
    *, browser: Browser, args: dict[str, Any], log_fn: LogFn | None = None,
) -> dict[str, Any]:
    """Enable privacy toggles cho 1 OpenRouter account.

    args: {"email": str, "password": str}
    Trả về {"email": str, "status": "ok"|"login_failed", "enabled": int}.
    """
    from ....config.settings import load_config
    from ....api.services.checker_service import _fix_privacy_one

    cfg = load_config()
    log = log_fn or (lambda m: None)
    email = args["email"]
    password = args["password"]

    ctx = await browser.new_context()
    try:
        page = await ctx.new_page()
        result = await _fix_privacy_one(page, email, password, cfg.base_dir / "debug")
    finally:
        await ctx.close()

    log(f"✅ fix_or_privacy {email}: {result['status']} (enabled {result.get('enabled', 0)})")
    return {"email": email, **result}
