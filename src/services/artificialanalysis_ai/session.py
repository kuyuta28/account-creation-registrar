"""
session.py — Playwright session persistence cho Artificial Analysis.

Thin wrapper quanh core/session.py — giữ API cũ để không break runner.py.

Public API:
  save_session(db_path, email, context) → None
  load_session(db_path, email) → dict | None
"""
from __future__ import annotations

from pathlib import Path

from ...core.session import (
    load_session as _load_session,
    save_session as _save_session,
)

_SERVICE = "ARTIFICIALANALYSIS"


async def save_session(db_path: Path, email: str, context) -> None:
    """Lưu Playwright storage_state của context vào DB."""
    await _save_session(db_path, _SERVICE, email, context)


def load_session(db_path: Path, email: str) -> dict | None:
    """Load storage_state từ DB. Trả None nếu chưa có."""
    return _load_session(db_path, _SERVICE, email)
