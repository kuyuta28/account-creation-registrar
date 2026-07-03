"""
google_oauth/_detect.py — Page state detection.
Pure async function: URL + DOM → GooglePageState enum.
"""
from __future__ import annotations

import logging

from playwright.async_api import (
    Error as PlaywrightError,
    Page,
    TimeoutError as PlaywrightTimeoutError,
)

from common.enums import GooglePageState
from ._constants import CONSENT_BUTTON_LOCATORS, TOTP_INPUT_LOCATORS
from ._helpers import short_url

_log = logging.getLogger(__name__)


async def detect_page_state(page: Page) -> GooglePageState:
    """
    Phân tích URL + DOM để xác định trạng thái hiện tại của trang Google.
    Logging chi tiết từng bước để debug.
    """
    url = page.url
    _log.debug("[detect_state] START url=%s", short_url(url))

    # ─── Non-Google URLs ──────────────────────────────────────────────────
    if "accounts.google.com" not in url:
        if "__/auth/handler" in url:
            _log.debug("[detect_state] → AUTH_HANDLER (non-google, auth_handler in url)")
            return GooglePageState.AUTH_HANDLER
        _log.debug("[detect_state] → DONE (non-google url)")
        return GooglePageState.DONE

    # ─── Wait for page load ───────────────────────────────────────────────
    try:
        await page.wait_for_load_state("domcontentloaded", timeout=15_000)
    except PlaywrightTimeoutError:
        _log.warning("[detect_state] domcontentloaded timeout. URL: %s", short_url(url))

    # Re-read URL (có thể đã redirect trong lúc load)
    url = page.url
    url_path = url.split("?")[0]
    _log.debug("[detect_state] after load: url_path=%s", short_url(url))

    if "accounts.google.com" not in url:
        if "__/auth/handler" in url:
            _log.debug("[detect_state] → AUTH_HANDLER (after load redirect)")
            return GooglePageState.AUTH_HANDLER
        _log.debug("[detect_state] → DONE (after load redirect, non-google)")
        return GooglePageState.DONE

    # ─── Transient redirect pages (SetSID, SetOSID) ──────────────────────
    if "/accounts/SetSID" in url or "/accounts/SetOSID" in url:
        _log.info("[detect_state] Transient SetSID/SetOSID → waiting redirect (15s)...")
        try:
            await page.wait_for_url(
                lambda u: "/accounts/SetSID" not in u and "/accounts/SetOSID" not in u,
                timeout=15_000,
            )
            _log.info("[detect_state] SetSID redirect done → new url=%s", short_url(page.url))
        except PlaywrightTimeoutError:
            _log.warning("[detect_state] SetSID redirect timeout! url=%s", short_url(page.url))
        return await detect_page_state(page)

    # ─── URL-based detection (highest confidence) ─────────────────────────
    if "signin/oauth" in url_path:
        _log.debug("[detect_state] → CONSENT (signin/oauth in path)")
        return GooglePageState.CONSENT

    if "challenge/selection" in url_path:
        _log.debug("[detect_state] → CHALLENGE_SELECTION")
        return GooglePageState.CHALLENGE_SELECTION

    if "challenge/totp" in url_path:
        _log.debug("[detect_state] → CHALLENGE_TOTP (url)")
        return GooglePageState.CHALLENGE_TOTP

    if "challenge/ipp/collect" in url_path:
        # ipp/collect: phone challenge hoặc Authenticator — check body text
        try:
            body_text = await page.inner_text("body", timeout=5_000)
        except (PlaywrightTimeoutError, PlaywrightError):
            body_text = ""
        if any(kw in body_text for kw in ("Authenticator app", "Google Authenticator", "ứng dụng Authenticator")):
            _log.debug("[detect_state] → CHALLENGE_TOTP (ipp/collect + Authenticator text)")
            return GooglePageState.CHALLENGE_TOTP
        _log.debug("[detect_state] → CHALLENGE_PHONE (ipp/collect)")
        return GooglePageState.CHALLENGE_PHONE

    if "challenge/ipp" in url_path:
        _log.debug("[detect_state] → CHALLENGE_PHONE_OTP (challenge/ipp)")
        return GooglePageState.CHALLENGE_PHONE_OTP

    if "challenge/pwd" in url_path:
        _log.debug("[detect_state] → LOGIN_PASSWORD (challenge/pwd)")
        return GooglePageState.LOGIN_PASSWORD

    # Generic challenge — check DOM
    if "challenge" in url_path:
        _log.debug("[detect_state] generic challenge path, checking DOM...")
        totp_loc = page.locator(", ".join(TOTP_INPUT_LOCATORS))
        try:
            await totp_loc.first.wait_for(state="visible", timeout=3_000)
            _log.debug("[detect_state] → CHALLENGE_TOTP (DOM totp input found)")
            return GooglePageState.CHALLENGE_TOTP
        except (PlaywrightTimeoutError, PlaywrightError):
            pass
        pwd_input = page.locator('input[type="password"]:not([name="hiddenPassword"])')
        try:
            await pwd_input.first.wait_for(state="visible", timeout=3_000)
            _log.debug("[detect_state] → LOGIN_PASSWORD (DOM pwd input found)")
            return GooglePageState.LOGIN_PASSWORD
        except (PlaywrightTimeoutError, PlaywrightError):
            pass
        _log.warning("[detect_state] → CHALLENGE_UNKNOWN (generic challenge, no DOM match)")
        return GooglePageState.CHALLENGE_UNKNOWN

    # ─── Login pages (identifier / signin) ────────────────────────────────
    if "identifier" in url_path or "signin" in url_path:
        _log.debug("[detect_state] signin/identifier path, checking DOM...")
        pwd_input = page.locator('input[type="password"]:not([name="hiddenPassword"])')
        try:
            await pwd_input.first.wait_for(state="visible", timeout=2_000)
            _log.debug("[detect_state] → LOGIN_PASSWORD (signin + pwd input)")
            return GooglePageState.LOGIN_PASSWORD
        except (PlaywrightTimeoutError, PlaywrightError):
            pass
        email_input = page.locator('input[type="email"], input[name="identifier"]')
        try:
            await email_input.first.wait_for(state="visible", timeout=10_000)
            _log.debug("[detect_state] → LOGIN_EMAIL (signin + email input)")
            return GooglePageState.LOGIN_EMAIL
        except (PlaywrightTimeoutError, PlaywrightError):
            pass

    # ─── DOM-based fallback (account chooser / consent) ───────────────────
    _log.debug("[detect_state] no URL-based match, checking DOM body text...")
    try:
        body_text = await page.inner_text("body", timeout=5_000)
    except (PlaywrightTimeoutError, PlaywrightError):
        body_text = ""

    if any(kw in body_text for kw in ("Choose an account", "Chọn tài khoản")):
        _log.debug("[detect_state] → ACCOUNT_CHOOSER (body text)")
        return GooglePageState.ACCOUNT_CHOOSER

    if any(kw in body_text for kw in (
        "is requesting access", "wants to access",
        "quyền truy cập", "đang yêu cầu quyền",
    )):
        _log.debug("[detect_state] → CONSENT (body text)")
        return GooglePageState.CONSENT

    consent_btn = page.locator(CONSENT_BUTTON_LOCATORS)
    try:
        if await consent_btn.first.is_visible():
            _log.debug("[detect_state] → CONSENT (consent button visible)")
            return GooglePageState.CONSENT
    except PlaywrightError:
        pass

    _log.warning("[detect_state] → CHALLENGE_UNKNOWN. url=%s body_snippet=%r", short_url(url), body_text[:200])
    return GooglePageState.CHALLENGE_UNKNOWN
