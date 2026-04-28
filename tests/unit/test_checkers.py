"""
unit/test_checkers.py — Tests cho src/checkers/chatgpt.py

Bao phủ:
  - is_expired (pure)
  - _quota_pct (pure)
  - _pick_weekly_window (pure)
  - _parse_token_response (pure, cần fake JWT)
  - refresh_token (async, mock httpx)
  - check_account (async, mock httpx)
"""
from __future__ import annotations

import asyncio
import base64
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch


# ── is_expired ────────────────────────────────────────────────────────────────

class TestIsExpired:
    def _call(self, iso, buffer=300):
        from src.checkers.chatgpt import is_expired
        return is_expired(iso, buffer)

    def test_empty_string_is_expired(self):
        assert self._call("") is True

    def test_none_string_is_expired(self):
        assert self._call(None) is True  # type: ignore

    def test_past_is_expired(self):
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(timespec="seconds")
        assert self._call(past) is True

    def test_far_future_not_expired(self):
        future = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(timespec="seconds")
        assert self._call(future) is False

    def test_within_buffer_is_expired(self):
        # Hết hạn trong 100 giây nữa, buffer=300 → expired
        soon = (datetime.now(timezone.utc) + timedelta(seconds=100)).isoformat(timespec="seconds")
        assert self._call(soon, buffer=300) is True

    def test_beyond_buffer_not_expired(self):
        # Hết hạn trong 600 giây nữa, buffer=300 → chưa expired
        later = (datetime.now(timezone.utc) + timedelta(seconds=600)).isoformat(timespec="seconds")
        assert self._call(later, buffer=300) is False

    def test_invalid_iso_returns_expired(self):
        assert self._call("not-a-date") is True

    def test_naive_datetime_treated_as_utc(self):
        # Naive datetime (không có tzinfo) = UTC
        future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(timespec="seconds")
        assert self._call(future) is False


# ── _pick_weekly_window ───────────────────────────────────────────────────────

class TestPickWeeklyWindow:
    _WEEK = 604800

    def _call(self, rl):
        from src.checkers.chatgpt import _pick_weekly_window
        return _pick_weekly_window(rl)

    def test_none_returns_none(self):
        assert self._call(None) is None

    def test_empty_dict_returns_none(self):
        assert self._call({}) is None

    def test_primary_window_snake_case(self):
        window = {"limit_window_seconds": self._WEEK, "used_percent": 40}
        rl = {"primary_window": window}
        assert self._call(rl) is window

    def test_primary_window_camel_case(self):
        window = {"limitWindowSeconds": self._WEEK, "usedPercent": 40}
        rl = {"primaryWindow": window}
        assert self._call(rl) is window

    def test_secondary_window_used_when_primary_absent(self):
        window = {"limit_window_seconds": self._WEEK}
        rl = {"secondary_window": window}
        assert self._call(rl) is window

    def test_non_weekly_window_skipped(self):
        rl = {"primary_window": {"limit_window_seconds": 86400}}  # daily
        assert self._call(rl) is None

    def test_none_window_value_skipped(self):
        window = {"limit_window_seconds": self._WEEK}
        rl = {"primary_window": None, "secondary_window": window}
        assert self._call(rl) is window


# ── _quota_pct ────────────────────────────────────────────────────────────────

class TestQuotaPct:
    _WEEK = 604800

    def _call(self, rl):
        from src.checkers.chatgpt import _quota_pct
        return _quota_pct(rl)

    def test_none_returns_question_mark(self):
        assert self._call(None) == "?"

    def test_full_quota_100_percent(self):
        window = {"limit_window_seconds": self._WEEK, "used_percent": 100}
        assert self._call({"primary_window": window}) == "0%"

    def test_half_quota(self):
        window = {"limit_window_seconds": self._WEEK, "used_percent": 50}
        assert self._call({"primary_window": window}) == "50%"

    def test_zero_used(self):
        window = {"limit_window_seconds": self._WEEK, "used_percent": 0}
        assert self._call({"primary_window": window}) == "100%"

    def test_limit_reached_returns_100_percent(self):
        assert self._call({"limit_reached": True}) == "100%"

    def test_not_allowed_returns_100_percent(self):
        assert self._call({"allowed": False}) == "100%"

    def test_no_window_no_flags_returns_question_mark(self):
        assert self._call({"some_other_key": 1}) == "?"

    def test_camel_case_used_percent(self):
        window = {"limitWindowSeconds": self._WEEK, "usedPercent": 75}
        assert self._call({"primaryWindow": window}) == "25%"


# ── _parse_token_response ─────────────────────────────────────────────────────

def _make_fake_jwt(account_id: str = "acc_123") -> str:
    """Tạo fake JWT với payload chuẩn (không signed)."""
    payload = {
        "sub": "user_abc",
        "https://api.openai.com/auth": {
            "chatgpt_account_id": account_id
        }
    }
    header = base64.urlsafe_b64encode(b'{"alg":"RS256"}').rstrip(b"=").decode()
    body = base64.urlsafe_b64encode(
        json.dumps(payload).encode()
    ).rstrip(b"=").decode()
    return f"{header}.{body}.fake_sig"


class TestParseTokenResponse:
    def _call(self, token_data, refresh="orig_refresh"):
        from src.checkers.chatgpt import _parse_token_response
        return _parse_token_response(token_data, refresh)

    def _token_data(self, account_id="acc_123", expires_in=3600, new_refresh=None):
        data = {
            "access_token": _make_fake_jwt(account_id),
            "expires_in": expires_in,
        }
        if new_refresh:
            data["refresh_token"] = new_refresh
        return data

    def test_contains_access_token(self):
        result = self._call(self._token_data())
        assert "access_token" in result
        assert result["access_token"].startswith("eyJ")

    def test_account_id_extracted_from_jwt(self):
        result = self._call(self._token_data(account_id="acc_xyz"))
        assert result["account_id"] == "acc_xyz"

    def test_refresh_token_from_response(self):
        result = self._call(self._token_data(new_refresh="new_tok"), refresh="old_tok")
        assert result["refresh_token"] == "new_tok"

    def test_refresh_token_fallback_to_original(self):
        result = self._call(self._token_data(), refresh="orig")
        assert result["refresh_token"] == "orig"

    def test_expired_field_is_future_iso(self):
        result = self._call(self._token_data(expires_in=3600))
        exp = datetime.fromisoformat(result["expired"])
        assert exp > datetime.now(timezone.utc)

    def test_last_refresh_field_set(self):
        result = self._call(self._token_data())
        assert "last_refresh" in result
        # Phải parse được
        datetime.fromisoformat(result["last_refresh"])

    def test_missing_account_id_defaults_empty(self):
        jwt = _make_fake_jwt("")
        data = {"access_token": jwt, "expires_in": 3600}
        result = self._call(data)
        assert result["account_id"] == ""


# ── refresh_token (async) ─────────────────────────────────────────────────────

class TestRefreshToken:
    def test_returns_dict_on_success(self):
        from src.checkers.chatgpt import refresh_token

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "access_token": _make_fake_jwt("acc_1"),
            "expires_in": 3600,
        }
        with patch("httpx.AsyncClient") as mk:
            mk.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_resp)
            result = asyncio.run(refresh_token("refresh_abc", "client_xyz"))

        assert result is not None
        assert "access_token" in result
        assert result["account_id"] == "acc_1"

    def test_returns_none_on_non_200(self):
        from src.checkers.chatgpt import refresh_token

        mock_resp = MagicMock()
        mock_resp.status_code = 401

        with patch("httpx.AsyncClient") as mk:
            mk.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_resp)
            result = asyncio.run(refresh_token("bad_refresh", "cid"))

        assert result is None

    def test_returns_none_on_exception(self):
        from src.checkers.chatgpt import refresh_token

        with patch("httpx.AsyncClient") as mk:
            mk.return_value.__aenter__.return_value.post = AsyncMock(
                side_effect=Exception("network error")
            )
            result = asyncio.run(refresh_token("rt", "cid"))

        assert result is None


# ── check_account (async) ─────────────────────────────────────────────────────

class TestCheckAccount:
    def _me_resp(self, status=200):
        r = MagicMock()
        r.status_code = status
        r.json.return_value = {"email": "test@example.com", "name": "Test"}
        return r

    def test_valid_account_fresh_token(self):
        from src.checkers.chatgpt import check_account

        future = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(timespec="seconds")
        account = {
            "access_token": _make_fake_jwt(),
            "expired": future,
        }

        with patch("httpx.AsyncClient") as mk:
            mk.return_value.__aenter__.return_value.get = AsyncMock(return_value=self._me_resp(200))
            result = asyncio.run(check_account(account, "client_id"))

        assert result["valid"] is True

    def test_no_access_token_no_refresh_token(self):
        from src.checkers.chatgpt import check_account
        result = asyncio.run(check_account({}, "client_id"))
        assert result["valid"] is False
        assert "no refresh_token" in result["reason"]

    def test_expired_token_tries_refresh_fails(self):
        from src.checkers.chatgpt import check_account

        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(timespec="seconds")
        account = {
            "access_token": _make_fake_jwt(),
            "expired": past,
            "refresh_token": "old_refresh",
        }

        mock_resp = MagicMock()
        mock_resp.status_code = 401

        with patch("httpx.AsyncClient") as mk:
            mk.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_resp)
            result = asyncio.run(check_account(account, "client_id"))

        assert result["valid"] is False

    def test_401_me_response_invalid(self):
        from src.checkers.chatgpt import check_account

        future = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(timespec="seconds")
        account = {"access_token": _make_fake_jwt(), "expired": future}

        with patch("httpx.AsyncClient") as mk:
            mk.return_value.__aenter__.return_value.get = AsyncMock(return_value=self._me_resp(401))
            result = asyncio.run(check_account(account, "client_id"))

        assert result["valid"] is False
        assert "401" in result["reason"]
