"""
session.py — Generic Playwright session persistence cho mọi service.

Lưu/load Playwright storage_state (cookies + localStorage + sessionStorage)
vào cột session_state trong bảng accounts của SQLite DB.

Public API:
  save_session(db_path, service, email, context) -> None
  load_session(db_path, service, email) -> dict | None
  has_session(db_path, service, email) -> bool
"""
from __future__ import annotations

import json
from pathlib import Path

from .database import get_account_by_email, update_account


async def save_session(db_path: Path, service: str, email: str, context) -> None:
    """Lưu Playwright storage_state của context vào DB.

    Args:
        db_path:  Đường dẫn SQLite DB.
        service:  Service tag (ví dụ: "KLINGAI", "ARTIFICIALANALYSIS").
        email:    Email định danh account.
        context:  Playwright BrowserContext đang active.
    """
    state = await context.storage_state()
    update_account(
        db_path,
        service.upper(),
        email,
        session_state=json.dumps(state, ensure_ascii=False),
    )


def load_session(db_path: Path, service: str, email: str) -> dict | None:
    """Load storage_state từ DB.

    Returns:
        dict phù hợp cho `browser.new_context(storage_state=...)`.
        None nếu chưa có session được lưu.

    Raises:
        RuntimeError: nếu account không tồn tại trong DB.
    """
    row = get_account_by_email(db_path, service.upper(), email)
    if not row:
        raise RuntimeError(f"Account không tồn tại trong DB: {service}/{email}")
    raw = row.get("session_state", "")
    if not raw:
        return None
    return json.loads(raw)


def has_session(db_path: Path, service: str, email: str) -> bool:
    """Kiểm tra account có session được lưu chưa."""
    row = get_account_by_email(db_path, service.upper(), email)
    if not row:
        return False
    return bool(row.get("session_state", ""))
