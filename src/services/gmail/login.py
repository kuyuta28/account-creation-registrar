"""
services/gmail/login.py — Playwright auto-login Google với TOTP 2FA.

Flow (DOM thực tế đã verify):
  1. goto accounts.google.com/signin
  2. Nhập email → Next (input[type="email"] → #identifierNext)
  3. Nhập password → Next (input[name="Passwd"] → #passwordNext)
  4. Trang challenge/selection: click [data-challengetype="6"] (Google Authenticator)
  5. Trang challenge/totp: fill input[name="totpPin"] → Next
  6. Redirect về myaccount.google.com → login thành công
  7. Lưu storage_state vào DB

Public API:
  login(db_path, cfg, email, password, totp_secret) -> None
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from ...config.settings import AppConfig
from common.browser import open_browser
from common.session import save_session as _save_session
from common.totp import generate_totp
from ..protocols import LogFn


_GOOGLE_SIGN_IN = "https://accounts.google.com/signin"

_SEL_EMAIL_INPUT  = 'input[type="email"]'
_SEL_PASS_INPUT   = 'input[name="Passwd"]'
_SEL_EMAIL_NEXT   = '#identifierNext'
_SEL_PASS_NEXT    = '#passwordNext'
_SEL_CHALLENGE_TOTP = '[data-challengetype="6"]'   # Google Authenticator option
_SEL_TOTP_INPUT   = 'input[name="totpPin"]'
_SEL_TOTP_NEXT    = '[id$="Next"]'

_SUCCESS_URL = "myaccount.google.com"


async def login(
    db_path: Path,
    cfg: AppConfig,
    email: str,
    password: str,
    totp_secret: str,
    log_fn: LogFn | None = None,
) -> None:
    """
    Tự động login Google với TOTP 2FA, lưu session vào DB.

    Args:
        db_path:      Đường dẫn SQLite DB.
        cfg:          AppConfig (proxy, headless...).
        email:        Gmail address.
        password:     Mật khẩu Google.
        totp_secret:  Base32 TOTP secret từ Google Authenticator.
        log_fn:       Optional logger function.

    Raises:
        RuntimeError: Nếu login thất bại ở bất kỳ bước nào.
    """
    _log = log_fn or print

    async with open_browser(cfg) as browser:
        context = await browser.new_context()
        page = await context.new_page()

        # Bước 1: Mở trang đăng nhập
        _log(f"[gmail/login] Mở {_GOOGLE_SIGN_IN}")
        await page.goto(_GOOGLE_SIGN_IN, wait_until="domcontentloaded")

        # Bước 2: Nhập email
        await page.locator(_SEL_EMAIL_INPUT).fill(email)
        await page.locator(_SEL_EMAIL_NEXT).click()
        await page.wait_for_load_state("domcontentloaded")
        await asyncio.sleep(1.5)

        # Bước 3: Nhập password
        await page.locator(_SEL_PASS_INPUT).fill(password)
        await page.locator(_SEL_PASS_NEXT).click()
        await page.wait_for_load_state("domcontentloaded")
        await asyncio.sleep(2)

        # Bước 4: Detect và xử lý challenge/selection → click Google Authenticator
        if "challenge/selection" in page.url or "challenge/pwd" in page.url:
            _log("[gmail/login] Trang challenge/selection — click Google Authenticator (type=6)")
            try:
                await page.locator(_SEL_CHALLENGE_TOTP).wait_for(state="visible", timeout=10_000)
                await page.locator(_SEL_CHALLENGE_TOTP).click()
                await page.wait_for_load_state("domcontentloaded")
                await asyncio.sleep(2)
            except PlaywrightTimeoutError:
                raise RuntimeError(
                    f"Không tìm thấy Google Authenticator option — URL: {page.url}"
                )

        # Bước 5: Trang challenge/totp — nhập TOTP code
        if "challenge/totp" in page.url:
            totp_code = generate_totp(totp_secret)
            _log(f"[gmail/login] Nhập TOTP code: {totp_code}")
            await page.locator(_SEL_TOTP_INPUT).wait_for(state="visible", timeout=10_000)
            await page.locator(_SEL_TOTP_INPUT).fill(totp_code)
            await page.locator(_SEL_TOTP_NEXT).first.click()
            await page.wait_for_load_state("domcontentloaded")
            await asyncio.sleep(3)
        else:
            raise RuntimeError(
                f"Không đến được trang TOTP — URL hiện tại: {page.url}"
            )

        # Bước 6: Verify thành công
        if _SUCCESS_URL not in page.url:
            raise RuntimeError(
                f"Google login thất bại — URL sau TOTP: {page.url}"
            )
        _log(f"[gmail/login] Login thành công: {page.url}")

        # Bước 7: Lưu session
        await _save_session(db_path, "GMAIL", email, context)
        _log(f"[gmail/login] Đã lưu session cho {email}")
