"""
google_oauth/_constants.py — Constants và locator strings cho Google OAuth flow.
"""
from __future__ import annotations

GOOGLE_SIGNIN_URL = "https://accounts.google.com/signin/v2/identifier"
GOOGLE_ACCOUNT_URL = "https://myaccount.google.com"
LOGIN_TIMEOUT_MS = 60_000
POPUP_CLOSE_TIMEOUT_MS = 30_000

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
