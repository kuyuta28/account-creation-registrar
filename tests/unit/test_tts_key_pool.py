"""
unit/test_tts_key_pool.py — Tests cho src/tts_proxy/key_pool.py

Bao phủ: _parse_quota, load_available_keys, update_quota_after_request.
Không gọi DB thật — mock get_accounts và update_account.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.tts_proxy.key_pool import (
    KeyEntry,
    _parse_quota,
    load_available_keys,
    update_quota_after_request,
)


# ── _parse_quota ──────────────────────────────────────────────────────────────

class TestParseQuota:
    def test_normal_percent(self):
        assert _parse_quota("87%") == 87

    def test_zero(self):
        assert _parse_quota("0%") == 0

    def test_hundred(self):
        assert _parse_quota("100%") == 100

    def test_no_percent_sign(self):
        assert _parse_quota("50") == 50

    def test_empty_string(self):
        assert _parse_quota("") == -1

    def test_none(self):
        assert _parse_quota(None) == -1

    def test_invalid(self):
        assert _parse_quota("abc%") == -1

    def test_whitespace(self):
        assert _parse_quota("  ") == -1


# ── load_available_keys ───────────────────────────────────────────────────────

_ROWS = [
    {"email": "a@b.com", "api_key": "key-a", "quota_pct": "80%", "disabled": False},
    {"email": "b@b.com", "api_key": "key-b", "quota_pct": "50%", "disabled": False},
    {"email": "c@b.com", "api_key": "key-c", "quota_pct": None,  "disabled": False},  # chưa check → -1
    {"email": "d@b.com", "api_key": "key-d", "quota_pct": "0%",  "disabled": False},  # hết quota
    {"email": "e@b.com", "api_key": "key-e", "quota_pct": "90%", "disabled": True},   # disabled
    {"email": "f@b.com", "api_key": None,     "quota_pct": "90%", "disabled": False},  # no api_key
]


def _mock_load(rows=_ROWS):
    """Context manager mock get_accounts + _db_path."""
    m_get = patch("src.tts_proxy.key_pool.get_accounts", return_value=rows)
    m_db  = patch("src.tts_proxy.key_pool._db_path", return_value=Path("/fake.db"))
    return m_get, m_db


class TestLoadAvailableKeys:
    def test_excludes_disabled(self):
        m_get, m_db = _mock_load()
        with m_get, m_db:
            keys = load_available_keys()
        emails = [k.email for k in keys]
        assert "e@b.com" not in emails

    def test_excludes_no_api_key(self):
        m_get, m_db = _mock_load()
        with m_get, m_db:
            keys = load_available_keys()
        emails = [k.email for k in keys]
        assert "f@b.com" not in emails

    def test_excludes_zero_quota(self):
        m_get, m_db = _mock_load()
        with m_get, m_db:
            keys = load_available_keys()
        emails = [k.email for k in keys]
        assert "d@b.com" not in emails

    def test_includes_unset_quota(self):
        """quota_pct=None → -1 → coi như còn đầy, KHÔNG bị loại."""
        m_get, m_db = _mock_load()
        with m_get, m_db:
            keys = load_available_keys()
        emails = [k.email for k in keys]
        assert "c@b.com" in emails

    def test_sorted_best_first(self):
        """Thứ tự: unset(-1→100) > 80 > 50."""
        m_get, m_db = _mock_load()
        with m_get, m_db:
            keys = load_available_keys()
        # c@b.com (quota_pct=-1 sort như 100) phải đứng đầu
        assert keys[0].email == "c@b.com"
        assert keys[1].email == "a@b.com"
        assert keys[2].email == "b@b.com"

    def test_returns_key_entries(self):
        m_get, m_db = _mock_load()
        with m_get, m_db:
            keys = load_available_keys()
        assert all(isinstance(k, KeyEntry) for k in keys)

    def test_empty_db(self):
        m_get, m_db = _mock_load([])
        with m_get, m_db:
            keys = load_available_keys()
        assert keys == []

    def test_all_disabled(self):
        rows = [
            {"email": "x@x.com", "api_key": "k", "quota_pct": "80%", "disabled": True},
        ]
        m_get, m_db = _mock_load(rows)
        with m_get, m_db:
            keys = load_available_keys()
        assert keys == []


# ── update_quota_after_request ────────────────────────────────────────────────

class TestUpdateQuotaAfterRequest:
    @pytest.mark.asyncio
    async def test_updates_db_with_correct_pct(self):
        """5000 used / 10000 limit → 50% remaining."""
        mock_update = MagicMock()
        with (
            patch("src.tts_proxy.key_pool.update_account", mock_update),
            patch("src.tts_proxy.key_pool._db_path", return_value=Path("/fake.db")),
            patch("asyncio.to_thread", new_callable=AsyncMock) as mock_thread,
        ):
            mock_thread.side_effect = lambda fn, *args, **kwargs: fn(*args, **kwargs)
            await update_quota_after_request("a@b.com", 5000, 10000)

        mock_update.assert_called_once_with(
            Path("/fake.db"), "ELEVENLABS", "a@b.com", quota_pct="50%"
        )

    @pytest.mark.asyncio
    async def test_skips_when_char_count_none(self):
        mock_update = MagicMock()
        with patch("src.tts_proxy.key_pool.update_account", mock_update):
            await update_quota_after_request("a@b.com", None, 10000)
        mock_update.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_when_limit_none(self):
        mock_update = MagicMock()
        with patch("src.tts_proxy.key_pool.update_account", mock_update):
            await update_quota_after_request("a@b.com", 5000, None)
        mock_update.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_when_limit_zero(self):
        mock_update = MagicMock()
        with patch("src.tts_proxy.key_pool.update_account", mock_update):
            await update_quota_after_request("a@b.com", 0, 0)
        mock_update.assert_not_called()

    @pytest.mark.asyncio
    async def test_quota_clamps_to_zero_when_over_used(self):
        """char_count_used > limit → remaining = 0 → 0%."""
        mock_update = MagicMock()
        with (
            patch("src.tts_proxy.key_pool.update_account", mock_update),
            patch("src.tts_proxy.key_pool._db_path", return_value=Path("/fake.db")),
            patch("asyncio.to_thread", new_callable=AsyncMock) as mock_thread,
        ):
            mock_thread.side_effect = lambda fn, *args, **kwargs: fn(*args, **kwargs)
            await update_quota_after_request("a@b.com", 15000, 10000)

        _, call_kwargs = mock_update.call_args
        assert call_kwargs["quota_pct"] == "0%"

    @pytest.mark.asyncio
    async def test_does_not_raise_on_db_error(self):
        """Fire-and-forget — DB lỗi không được propagate."""
        with (
            patch("src.tts_proxy.key_pool.update_account", side_effect=RuntimeError("db fail")),
            patch("src.tts_proxy.key_pool._db_path", return_value=Path("/fake.db")),
            patch("asyncio.to_thread", new_callable=AsyncMock) as mock_thread,
        ):
            mock_thread.side_effect = lambda fn, *args, **kwargs: fn(*args, **kwargs)
            # Không raise
            await update_quota_after_request("a@b.com", 1000, 10000)
