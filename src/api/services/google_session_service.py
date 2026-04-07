"""
google_session_service.py — Login Google và lưu storage_state vào mailbox.

Business logic layer — dùng core/google_oauth.py cho tương tác Google.
"""
from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from ...config.settings import load_config
from ...core.database import (
    get_mailboxes,
    get_mailbox_record,
    save_mailbox_google_auth_state,
)
from ...core.google_oauth import (
    GOOGLE_SIGNIN_URL,
    LOGIN_TIMEOUT_MS,
    login_google_on_page,
)
from ...core.storage import db_path

_log = logging.getLogger(__name__)


async def _db_path_async() -> Path:
    cfg = await asyncio.to_thread(load_config)
    return db_path(cfg.base_dir)


async def _login_google_single(email: str, password: str, totp_secret: str) -> str:
    """Login Google cho 1 account, trả về storage_state JSON string."""
    from ...core.browser import open_browser
    cfg = await asyncio.to_thread(load_config)
    async with open_browser(cfg, headless=False) as browser:
        ctx = await browser.new_context()
        page = await ctx.new_page()
        await page.goto(GOOGLE_SIGNIN_URL, wait_until="domcontentloaded")
        await login_google_on_page(page, email, password, totp_secret, db_path=db_path(cfg.base_dir))
        await page.wait_for_url("https://myaccount.google.com/**", timeout=LOGIN_TIMEOUT_MS, wait_until="commit")
        state = await ctx.storage_state()
        await ctx.close()
    return json.dumps(state)


async def refresh_google_session(email: str) -> dict[str, Any]:
    """
    Login Google cho 1 mailbox và lưu storage_state.
    Trả về dict với email + kết quả.
    """
    record = await asyncio.to_thread(get_mailbox_record, await _db_path_async(), email)
    if not record:
        raise ValueError(f"Mailbox không tồn tại: {email!r}")

    password = record.get("password", "")
    if not password:
        raise ValueError(f"Mailbox {email!r} chưa có password Google — không thể login")

    totp_secret = record.get("totp_secret", "")

    _log.info("[google_session] Đang login Google cho %s", email)
    auth_state = await _login_google_single(email, password, totp_secret)

    saved = await asyncio.to_thread(save_mailbox_google_auth_state, await _db_path_async(), email, auth_state)
    if not saved:
        raise RuntimeError(f"Lưu session thất bại cho {email!r}")

    _log.info("[google_session] Đã lưu session cho %s", email)
    return {"email": email, "ok": True}


async def refresh_all_google_sessions() -> list[dict[str, Any]]:
    """
    Login Google cho tất cả mailboxes có password, chạy sequential (tránh block nhiều session cùng lúc).
    Trả về list kết quả từng mailbox.
    """
    mailboxes = await asyncio.to_thread(get_mailboxes, await _db_path_async())
    targets = [m for m in mailboxes if m.get("password") and not m.get("disabled")]

    if not targets:
        return []

    results: list[dict[str, Any]] = []
    for m in targets:
        try:
            result = await refresh_google_session(m["email"])
            results.append(result)
        except Exception as e:  # noqa: BLE001 — batch collector: per-item error isolation, không crash toàn batch
            _log.error("[google_session] Lỗi %s: %s", m["email"], e)
            results.append({"email": m["email"], "ok": False, "error": str(e)})

    return results
