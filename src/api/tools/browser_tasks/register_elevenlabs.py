"""register_elevenlabs.py — Browser Gateway task: đăng ký ElevenLabs account.

Chạy trên host (gateway mở camoufox). KHÔNG trong container (container không có
camoufox binary). Container gọi run_browser_task("register_elevenlabs").

Flow: load Google storage_state từ DB (nếu use_session) → inject vào context →
"Sign up with Google" → OAuth popup → dashboard → create API key →
save storage_state mới về DB → trả record dict.
"""
from __future__ import annotations

from typing import Any

from playwright.async_api import Browser

from ....core.google_oauth._helpers import LogFn
from ._registry import register  # noqa: F401  — side-effect: đăng ký task


@register("register_elevenlabs", engine="camoufox")
async def register_elevenlabs(
    *, browser: Browser, args: dict[str, Any], log_fn: LogFn | None = None,
) -> dict[str, Any]:
    """Đăng ký 1 ElevenLabs account qua Google OAuth (camoufox).

    args: {"email": str, "use_session": bool}
    Trả về {"email","password","api_key"} hoặc raise.
    """
    import json

    from common.database._async import get_mailbox_record_async
    from common.database._engine import get_async_session
    from ....config.settings import load_config
    from ....mail.client import create_mailbox
    from ....services.elevenlabs_io.flow import _signup_flow

    cfg = load_config()
    log = log_fn or (lambda m: None)

    email = args["email"]
    use_session = bool(args.get("use_session", True))

    # Lấy mailbox record (password, totp, google_auth_state) từ DB
    async with get_async_session() as session:
        mailbox_record = await get_mailbox_record_async(session, email)
    if not mailbox_record:
        raise ValueError(f"Mailbox không tồn tại: {email!r}")

    # Reconstruct Mailbox từ DB record (create_mailbox đã chạy ở container).
    # _signup_flow chỉ cần email/password/totp_secret cho OAuth popup.
    from ....mail._base import Mailbox
    mailbox = Mailbox(
        email=email,
        token=mailbox_record.get("token", ""),
        account_id=mailbox_record.get("account_id", ""),
        base_url=mailbox_record.get("base_url", ""),
        provider=mailbox_record.get("provider", ""),
        password=mailbox_record.get("password", ""),
        totp_secret=mailbox_record.get("totp_secret", ""),
        phone=mailbox_record.get("phone", ""),
    )

    state_json = ""
    if use_session:
        state_json = mailbox_record.get("google_auth_state", "")
        if not state_json:
            raise RuntimeError(
                f"No Google session found for {email} — "
                "chạy 'Login Google Session' trước để lưu session vào DB"
            )
        log(f"  ✓ Google session loaded ({len(state_json)} bytes)")

    ctx = await browser.new_context(
        **({"storage_state": json.loads(state_json)} if state_json else {})
    )
    try:
        page = await ctx.new_page()
        record = await _signup_flow(page, ctx, mailbox, cfg, log)
    finally:
        await ctx.close()

    log(f"✅ ElevenLabs account created: {record.email} (api_key {len(record.api_key)} chars)")
    return {
        "email": record.email,
        "password": record.password,
        "api_key": record.api_key,
    }
