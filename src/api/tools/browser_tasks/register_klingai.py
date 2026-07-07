"""register_klingai.py — Browser Gateway task: lưu session Kling AI sau user login Google.

Chạy trên host (gateway mở camoufox visible — headless=False do client truyền).
KHÔNG trong container (container không có camoufox binary + cần visible browser
cho user login Google thủ công). Container gọi
run_browser_task("register_klingai", headless=False).

Flow: mở login page → đợi user login Google → detect dashboard → extract email
→ save storage_state vào DB → trả record dict.
"""
from __future__ import annotations

from typing import Any

from playwright.async_api import Browser

from ....core.google_oauth._helpers import LogFn
from ._registry import register  # noqa: F401  — side-effect: đăng ký task


@register("register_klingai", engine="camoufox")
async def register_klingai(
    *, browser: Browser, args: dict[str, Any], log_fn: LogFn | None = None,
) -> dict[str, Any]:
    """Lưu session Kling AI sau khi user login Google (camoufox visible).

    args: {"gmail_hint": str}
    Trả về {"email": str, "ok": True} hoặc {"ok": False} nếu hết timeout.
    """
    import json

    from ....config.settings import load_config
    from ....services.klingai_com.flow import InternalClient, _login_flow

    cfg = load_config()
    log = log_fn or (lambda m: None)
    gmail_hint = args.get("gmail_hint", "")

    ctx = await browser.new_context()
    try:
        page = await ctx.new_page()
        record = await _login_flow(page, ctx, cfg, log, gmail_hint=gmail_hint)
        if record is None:
            return {"ok": False}
        session_state = json.dumps(await ctx.storage_state(), ensure_ascii=False)
        await InternalClient().upsert_account(record, session_state)
    finally:
        await ctx.close()

    log(f"✅ KlingAI session saved cho: {record.email}")
    return {"email": record.email, "ok": True}
