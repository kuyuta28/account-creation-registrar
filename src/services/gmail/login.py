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
  login(cfg, email, password, totp_secret) -> None
"""
from __future__ import annotations

import asyncio

from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from ...config.settings import AppConfig
from common.browser import open_browser
from common.session import save_session as _save_session
from common.totp import generate_totp
from ..protocols import LogFn


async def login(
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
    g = cfg.gmail_login

    async with open_browser(cfg) as browser:
        context = await browser.new_context()
        page = await context.new_page()

        # Bước 1: Mở trang đăng nhập
        _log(f"[gmail/login] Mở {g.signin_url}")
        await page.goto(g.signin_url, wait_until="domcontentloaded")

        # Bước 2: Nhập email
        await page.locator(g.email_input).fill(email)
        await page.locator(g.email_next).click()
        await page.wait_for_load_state("domcontentloaded")
        await asyncio.sleep(g.post_email_delay_sec)

        # Bước 3: Nhập password
        await page.locator(g.password_input).fill(password)
        await page.locator(g.password_next).click()
        await page.wait_for_load_state("domcontentloaded")
        await asyncio.sleep(g.post_password_delay_sec)

        # Bước 4: Detect và xử lý challenge/selection → click Google Authenticator
        if "challenge/selection" in page.url or "challenge/pwd" in page.url:
            _log("[gmail/login] Trang challenge/selection — click Google Authenticator (type=6)")
            try:
                await page.locator(g.challenge_totp).wait_for(state="visible", timeout=g.challenge_visible_timeout_ms)
                await page.locator(g.challenge_totp).click()
                await page.wait_for_load_state("domcontentloaded")
                await asyncio.sleep(g.post_challenge_click_delay_sec)
            except PlaywrightTimeoutError:
                raise RuntimeError(
                    f"Không tìm thấy Google Authenticator option — URL: {page.url}"
                )

        # Bước 5: Trang challenge/totp — nhập TOTP code
        if "challenge/totp" in page.url:
            totp_code = generate_totp(totp_secret)
            _log(f"[gmail/login] Nhập TOTP code: {totp_code}")
            await page.locator(g.totp_input).wait_for(state="visible", timeout=g.totp_visible_timeout_ms)
            await page.locator(g.totp_input).fill(totp_code)
            await page.locator(g.totp_next).first.click()
            await page.wait_for_load_state("domcontentloaded")
            await asyncio.sleep(g.post_totp_delay_sec)
        else:
            raise RuntimeError(
                f"Không đến được trang TOTP — URL hiện tại: {page.url}"
            )

        # Bước 6: Verify thành công
        if g.success_url not in page.url:
            raise RuntimeError(
                f"Google login thất bại — URL sau TOTP: {page.url}"
            )
        _log(f"[gmail/login] Login thành công: {page.url}")

        # Bước 7: Lưu session
        await _save_session("GMAIL", email, context)
        _log(f"[gmail/login] Đã lưu session cho {email}")
