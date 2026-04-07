"""
key_pool.py — Load ElevenLabs API keys từ DB và chọn key tốt nhất.

Logic chọn key:
  - Loại bỏ: disabled=True hoặc api_key rỗng
  - Loại bỏ: quota_pct = "0%" (hết quota)
  - Ưu tiên: quota_pct cao nhất (nhiều characters_remaining nhất)
  - Chưa check (quota_pct rỗng): coi như còn đầy (-1 → sort như 100%)

Quota update realtime:
  - Sau mỗi TTS request thành công, ElevenLabs trả header x-character-count
  - Gọi update_quota_after_request() để update DB ngay lập tức
  - Không cần chạy checker riêng sau mỗi request
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import NamedTuple

from ..config.settings import load_config
from ..core.database import get_accounts, update_account
from ..core.storage import db_path

_log = logging.getLogger(__name__)


class KeyEntry(NamedTuple):
    email: str
    api_key: str
    quota_pct: int  # 0–100; -1 = chưa check (coi như available)


def _parse_quota(raw: str | None) -> int:
    """Parse "87%" → 87. Rỗng / không hợp lệ → -1."""
    if not raw:
        return -1
    try:
        return int(str(raw).rstrip("%"))
    except ValueError:
        return -1


def _db_path() -> Path:
    return db_path(load_config().base_dir)


def load_available_keys() -> list[KeyEntry]:
    """Load tất cả ELEVENLABS keys còn quota, sorted tốt nhất trước.

    Keys chưa check quota (-1) được coi như 100% — account mới thường còn đầy.
    Keys có quota_pct = 0 bị loại (hết quota tháng này).
    """
    rows = get_accounts(_db_path(), "ELEVENLABS")
    entries = [
        KeyEntry(
            email=r["email"],
            api_key=r["api_key"],
            quota_pct=_parse_quota(r.get("quota_pct")),
        )
        for r in rows
        if not r.get("disabled") and r.get("api_key")
    ]
    available = [e for e in entries if e.quota_pct != 0]
    return sorted(
        available,
        key=lambda e: 100 if e.quota_pct < 0 else e.quota_pct,
        reverse=True,
    )


async def disable_key(email: str) -> None:
    """Đánh dấu disabled=True trong DB cho key bị block (unusual activity, etc.)."""
    try:
        await asyncio.to_thread(
            update_account,
            _db_path(),
            "ELEVENLABS",
            email,
            disabled=True,
        )
        _log.warning("Disabled key %s due to ElevenLabs block", email)
    except Exception as exc:  # noqa: BLE001 - fire-and-forget update - log warning only
        _log.warning("Failed to disable key %s: %s", email, exc)

async def mark_key_error(email: str, reason: str) -> None:
    """Ghi error_message vào DB cho key gặp lỗi không phải unusual activity."""
    try:
        await asyncio.to_thread(
            update_account,
            _db_path(),
            "ELEVENLABS",
            email,
            error_message=reason,
        )
        _log.warning("Marked key %s as error: %s", email, reason)
    except Exception as exc:  # noqa: BLE001 - fire-and-forget update - log warning only
        _log.warning("Failed to mark error for key %s: %s", email, exc)

async def update_quota_after_request(
    email: str,
    char_count_used: int | None,
    char_limit: int | None,
) -> None:
    """Update quota_pct trong DB sau khi dùng 1 TTS request.

    Đọc x-character-count (chars đã dùng tích lũy) và character_limit từ
    headers/user endpoint. Tính quota_pct = remaining / limit * 100.

    Fire-and-forget — gọi bằng asyncio.create_task(), không await trực tiếp.
    """
    if char_count_used is None or char_limit is None or char_limit == 0:
        return
    remaining = max(0, char_limit - char_count_used)
    quota_pct = f"{round(remaining / char_limit * 100)}%"
    try:
        await asyncio.to_thread(
            update_account,
            _db_path(),
            "ELEVENLABS",
            email,
            quota_pct=quota_pct,
        )
        _log.debug("Updated quota for %s → %s", email, quota_pct)
    except Exception as exc:  # noqa: BLE001 - fire-and-forget update - log warning only
        _log.warning("Failed to update quota for %s: %s", email, exc)
