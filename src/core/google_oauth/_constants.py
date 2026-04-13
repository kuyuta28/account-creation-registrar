"""
google_oauth/_constants.py — Constants và locator strings cho Google OAuth flow.

URLs và timeouts đọc từ config (cfg.google_oauth), fallback default values
nếu config chưa load. Locator strings là DOM selectors — không chuyển ra config.
"""
from __future__ import annotations

from ...config.settings import load_config


def _cfg():
    """Lazily load config — tránh circular import."""
    return load_config().google_oauth


# URLs và timeouts — đọc từ config. Gọi function mỗi lần dùng để luôn lấy giá trị mới.
GOOGLE_SIGNIN_URL = property(lambda _: _cfg().login_url)  # dùng get_login_url()
GOOGLE_ACCOUNT_URL = property(lambda _: _cfg().myaccount_url)  # dùng get_myaccount_url()


def get_login_url() -> str:
    return _cfg().login_url


def get_myaccount_url() -> str:
    return _cfg().myaccount_url


def get_login_timeout_ms() -> int:
    return _cfg().login_timeout_ms


def get_popup_close_timeout_ms() -> int:
    return _cfg().popup_close_timeout_ms

AUTHENTICATOR_CLICK_LOCATORS = [
    '[data-challengetype="6"]',
    'li[data-challengetype="6"]',
    'div[data-challengetype="6"]',
    'li:has-text("Authenticator")',
    'div[role="link"]:has-text("Authenticator")',
    'li:has-text("Google Authenticator")',
    '[aria-label*="Authenticator" i]',
]

TOTP_INPUT_LOCATORS = [
    'input#totpPin',
    'input[name="totpPin"]',
    'input[aria-label*="code" i]:not(#phoneNumberId)',
    'input[aria-label*="authenticator" i]',
    'input[aria-label*="6-digit" i]',
    'input[autocomplete="one-time-code"]',
]

TRY_ANOTHER_WAY_LOCATORS = (
    'button:has-text("Try another way"), '
    'a:has-text("Try another way"), '
    'button:has-text("Thử cách khác"), '
    'a:has-text("Thử cách khác"), '
    'button:has-text("Cách xác minh khác"), '
    'a:has-text("Cách xác minh khác")'
)

CONSENT_BUTTON_LOCATORS = (
    'button:has-text("Allow"), button:has-text("Continue"), '
    'button:has-text("Đồng ý"), button:has-text("Tiếp tục"), '
    'button:has-text("Cho phép")'
)

PHONE_CLICK_LOCATORS = [
    '[data-challengetype="12"]',
    'li[data-challengetype="12"]',
    'div[data-challengetype="12"]',
    '[data-challengetype="13"]',
    'li[data-challengetype="13"]',
    'div[data-challengetype="13"]',
    'li:has-text("phone")',
    'div[role="link"]:has-text("phone")',
    'li:has-text("text message")',
    'li:has-text("SMS")',
    'li:has-text("Tin nhắn")',
    'li:has-text("điện thoại")',
]
