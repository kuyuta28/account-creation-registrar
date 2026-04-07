"""
unit/test_tts_errors_http.py — Tests cho src/tts_proxy/errors.py và _http.py

Bao phủ:
  - errors.py: exception hierarchy
  - _http.py: _auth_headers, _raise_for_status
"""
from __future__ import annotations

import httpx
import pytest

from src.tts_proxy.errors import ElevenLabsError, RateLimitError
from src.tts_proxy._http import _auth_headers, _raise_for_status


# ── errors.py ─────────────────────────────────────────────────────────────────

class TestErrorHierarchy:
    def test_rate_limit_is_elevenlabs_error(self):
        assert issubclass(RateLimitError, ElevenLabsError)

    def test_elevenlabs_error_is_exception(self):
        assert issubclass(ElevenLabsError, Exception)

    def test_rate_limit_can_be_raised(self):
        with pytest.raises(RateLimitError):
            raise RateLimitError("429 too many requests")

    def test_rate_limit_caught_as_elevenlabs_error(self):
        with pytest.raises(ElevenLabsError):
            raise RateLimitError("429")

    def test_message_preserved(self):
        exc = ElevenLabsError("custom message")
        assert str(exc) == "custom message"


# ── _http.py: _auth_headers ───────────────────────────────────────────────────

class TestAuthHeaders:
    def test_returns_xi_api_key(self):
        headers = _auth_headers("sk_test123")
        assert headers == {"xi-api-key": "sk_test123"}

    def test_different_key(self):
        headers = _auth_headers("sk_another")
        assert headers["xi-api-key"] == "sk_another"

    def test_returns_dict(self):
        assert isinstance(_auth_headers("k"), dict)


# ── _http.py: _raise_for_status ───────────────────────────────────────────────

def _make_resp(status_code: int, text: str = "") -> httpx.Response:
    """Tạo httpx.Response fake để test."""
    return httpx.Response(status_code=status_code, text=text)


class TestRaiseForStatus:
    def test_200_no_raise(self):
        _raise_for_status(_make_resp(200))  # không raise

    def test_201_no_raise(self):
        _raise_for_status(_make_resp(201))

    def test_204_no_raise(self):
        _raise_for_status(_make_resp(204))

    def test_429_raises_rate_limit(self):
        with pytest.raises(RateLimitError):
            _raise_for_status(_make_resp(429))

    def test_429_caught_as_elevenlabs_error(self):
        with pytest.raises(ElevenLabsError):
            _raise_for_status(_make_resp(429))

    def test_400_raises_runtime_error(self):
        with pytest.raises(RuntimeError, match="400"):
            _raise_for_status(_make_resp(400, "bad request"))

    def test_500_raises_runtime_error(self):
        with pytest.raises(RuntimeError, match="500"):
            _raise_for_status(_make_resp(500, "internal server error"))

    def test_404_raises_runtime_error(self):
        with pytest.raises(RuntimeError, match="404"):
            _raise_for_status(_make_resp(404))

    def test_error_message_includes_body(self):
        body = "voice_not_found: abc"
        with pytest.raises(RuntimeError, match="voice_not_found"):
            _raise_for_status(_make_resp(400, body))

    def test_long_body_truncated(self):
        """Body dài hơn 300 chars phải được truncate."""
        long_body = "x" * 500
        try:
            _raise_for_status(_make_resp(400, long_body))
        except RuntimeError as e:
            msg = str(e)
            # Message phải không dài hơn mức hợp lý (300 + overhead)
            assert len(msg) < 400
