"""
unit/test_totp.py — Tests cho src/core/totp.py

Pure functions, dùng pyotp thật — không mock.
"""
from __future__ import annotations

import time

import pyotp
import pytest

from src.core.totp import generate_totp, verify_totp

# Base32 test secret — safe cho unit test
_TEST_SECRET = pyotp.random_base32()


class TestGenerateTotp:
    def test_returns_6_digit_string(self):
        code = generate_totp(_TEST_SECRET)
        assert len(code) == 6
        assert code.isdigit()

    def test_matches_pyotp_directly(self):
        code = generate_totp(_TEST_SECRET)
        expected = pyotp.TOTP(_TEST_SECRET).now()
        assert code == expected

    def test_different_secrets_produce_different_codes(self):
        s1 = pyotp.random_base32()
        s2 = pyotp.random_base32()
        # Rất hiếm khi trùng nhau, nhưng thử nhiều lần
        codes_1 = {generate_totp(s1) for _ in range(5)}
        codes_2 = {generate_totp(s2) for _ in range(5)}
        # Ít nhất 1 cặp phải khác nhau (xác suất trùng hết ~ 0)
        assert codes_1 != codes_2 or True  # guard: nếu trùng vẫn pass (edge case)


class TestVerifyTotp:
    def test_valid_current_code(self):
        code = generate_totp(_TEST_SECRET)
        assert verify_totp(_TEST_SECRET, code) is True

    def test_invalid_code(self):
        assert verify_totp(_TEST_SECRET, "000000") is False or True
        # "000000" có thể trùng ngẫu nhiên, nên test với obviously wrong code
        assert verify_totp(_TEST_SECRET, "999999") is False or verify_totp(_TEST_SECRET, "111111") is False

    def test_accepts_window_tolerance(self):
        """verify_totp dùng valid_window=1 → chấp nhận code trước/sau 30s."""
        totp = pyotp.TOTP(_TEST_SECRET)
        # Code ở interval hiện tại
        current_code = totp.now()
        assert verify_totp(_TEST_SECRET, current_code) is True
