"""
google_oauth/ — Google OAuth / 2FA / consent / popup handling.

Generic, reusable across ALL services that integrate Google sign-in.
Pure async functions, no service-specific logic, no DB access.

Architecture:
  - _detect.py    → detect_page_state(page) → GooglePageState enum
  - _handlers.py  → Mỗi state có 1 handler riêng biệt (SRP)
  - _loops.py     → handle_oauth_popup(), login_google_on_page()
  - _helpers.py   → dump_page_html(), short_url(), safe_wait()
  - _constants.py → URL patterns, locator strings, timeouts
"""
from __future__ import annotations

# Re-export public API — callers chỉ cần:
#   from ...core.google_oauth import handle_oauth_popup, login_google_on_page, ...
from ._constants import (
    GOOGLE_ACCOUNT_URL,
    GOOGLE_SIGNIN_URL,
    LOGIN_TIMEOUT_MS,
    POPUP_CLOSE_TIMEOUT_MS,
)
from ._detect import detect_page_state
from ._helpers import LogFn, dump_page_html, short_url
from ._loops import handle_oauth_popup, login_google_on_page

__all__ = [
    "GOOGLE_ACCOUNT_URL",
    "GOOGLE_SIGNIN_URL",
    "LOGIN_TIMEOUT_MS",
    "POPUP_CLOSE_TIMEOUT_MS",
    "LogFn",
    "detect_page_state",
    "dump_page_html",
    "handle_oauth_popup",
    "login_google_on_page",
    "short_url",
]
