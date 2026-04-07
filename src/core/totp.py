"""
totp.py — TOTP code generator/verifier dùng pyotp.

Dùng cho Google Authenticator (TOTP-based 2FA).

Public API:
  generate_totp(secret) -> str   — sinh mã 6 số hiện tại
  verify_totp(secret, code) -> bool
"""
from __future__ import annotations

import pyotp


def generate_totp(secret: str) -> str:
    """Sinh mã TOTP 6 số từ base32 secret (Google Authenticator format)."""
    return pyotp.TOTP(secret).now()


def verify_totp(secret: str, code: str) -> bool:
    """Verify mã TOTP, chấp nhận lệch ±1 window (30s)."""
    return pyotp.TOTP(secret).verify(code, valid_window=1)
