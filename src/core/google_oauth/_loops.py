"""
google_oauth/_loops.py — Reactive state machine loops.
handle_oauth_popup(): cho OAuth popup window.
login_google_on_page(): cho full Google login trên page chính.
"""
from __future__ import annotations

import logging
import pathlib
import time as _time

from playwright.async_api import (
    Page,
    TimeoutError as PlaywrightTimeoutError,
)

from common.enums import GooglePageState
from ._constants import get_login_timeout_ms, get_popup_close_timeout_ms, _cfg
from ._detect import detect_page_state
from ._handlers import (
    handle_account_chooser,
    handle_challenge_phone,
    handle_challenge_phone_otp,
    handle_challenge_selection,
    handle_challenge_totp,
    handle_challenge_unknown,
    handle_consent,
    handle_login_email,
    handle_login_password,
)
from ._helpers import LogFn, dump_page_html, short_url, wait_url_change

_log = logging.getLogger(__name__)


async def handle_oauth_popup(
    popup: Page,
    *,
    email: str = "",
    password: str = "",
    totp_secret: str = "",
    db_path: pathlib.Path | None = None,
    timeout_ms: int | None = None,
    log_fn: LogFn | None = None,
) -> None:
    """
    Reactive loop xử lý Google OAuth popup.
    Detect page state → dispatch handler → wait for transition → repeat.
    """
    def _emit(msg: str) -> None:
        _log.info("[popup] %s", msg)
        if log_fn:
            log_fn(f"  [popup] {msg}")

    _timeout_ms = timeout_ms if timeout_ms is not None else get_popup_close_timeout_ms()
    try:
        cfg = _cfg()
        await popup.wait_for_load_state("domcontentloaded", timeout=_timeout_ms)

        deadline = _time.monotonic() + (_timeout_ms * cfg.popup_deadline_multiplier / 1000)
        max_iterations = cfg.popup_max_iterations
        iteration = 0
        resolved_phone: str = ""

        while not popup.is_closed():
            iteration += 1
            if iteration > max_iterations:
                await dump_page_html(popup, "popup_max_iterations", log_fn)
                raise RuntimeError(f"OAuth popup vượt quá {max_iterations} iterations")

            if _time.monotonic() > deadline:
                await dump_page_html(popup, "popup_deadline_timeout", log_fn)
                raise RuntimeError(f"OAuth popup không hoàn tất sau {_timeout_ms * 3}ms")

            state = await detect_page_state(popup)
            _emit(f"[iter={iteration}] state={state.value}, url={short_url(popup.url)}")

            if state == GooglePageState.DONE:
                _emit("DONE — waiting for popup to close...")
                try:
                    await popup.wait_for_event("close", timeout=cfg.popup_close_event_timeout_ms)
                    _emit("popup closed ✓")
                except PlaywrightTimeoutError:
                    if popup.is_closed():
                        break
                    continue
                break

            if state == GooglePageState.AUTH_HANDLER:
                if email:
                    _emit("Auth handler + fresh login — waiting for redirect to Google...")
                    try:
                        await popup.wait_for_url(
                            lambda u: "accounts.google.com" in u,
                            timeout=cfg.auth_handler_redirect_timeout_ms,
                            wait_until="commit",
                        )
                        _emit(f"Redirected to Google: {short_url(popup.url)}")
                    except PlaywrightTimeoutError:
                        await dump_page_html(popup, "auth_handler_no_redirect", log_fn)
                        raise RuntimeError(
                            f"Auth handler không redirect sang Google sau {cfg.auth_handler_redirect_timeout_ms // 1000}s"
                        )
                    continue
                _emit("Auth handler — waiting for close...")
                try:
                    await popup.wait_for_event("close", timeout=cfg.popup_close_event_timeout_ms)
                    _emit("popup closed ✓")
                    break
                except PlaywrightTimeoutError:
                    _emit("popup chưa đóng, re-checking state...")
                    continue

            if state == GooglePageState.ACCOUNT_CHOOSER:
                _emit("→ Handling ACCOUNT_CHOOSER")
                await handle_account_chooser(popup, log_fn)
                await wait_url_change(popup, timeout_ms=timeout_ms)
                _emit(f"After chooser → url={short_url(popup.url)}")
                continue

            if state == GooglePageState.CONSENT:
                _emit("→ Handling CONSENT")
                await handle_consent(popup, log_fn)
                if popup.is_closed():
                    _emit("popup closed after consent ✓")
                    break
                await wait_url_change(popup, timeout_ms=timeout_ms)
                _emit(f"After consent → url={short_url(popup.url)}")
                continue

            if state == GooglePageState.CHALLENGE_TOTP:
                _emit("→ Handling CHALLENGE_TOTP")
                await handle_challenge_totp(popup, totp_secret, log_fn)
                await wait_url_change(popup)
                _emit(f"After TOTP → url={short_url(popup.url)}")
                continue

            if state == GooglePageState.CHALLENGE_SELECTION:
                _emit("→ Handling CHALLENGE_SELECTION")
                await handle_challenge_selection(popup, totp_secret, log_fn)
                await wait_url_change(popup)
                _emit(f"After selection → url={short_url(popup.url)}")
                continue

            if state == GooglePageState.CHALLENGE_PHONE:
                _emit("→ Handling CHALLENGE_PHONE")
                resolved_phone = await handle_challenge_phone(popup, db_path, log_fn)
                await wait_url_change(popup)
                _emit(f"After phone → url={short_url(popup.url)}")
                continue

            if state == GooglePageState.CHALLENGE_PHONE_OTP:
                _emit("→ Handling CHALLENGE_PHONE_OTP")
                await handle_challenge_phone_otp(popup, resolved_phone, log_fn)
                await wait_url_change(popup)
                _emit(f"After phone OTP → url={short_url(popup.url)}")
                continue

            if state == GooglePageState.CHALLENGE_UNKNOWN:
                _emit("→ Handling CHALLENGE_UNKNOWN")
                await handle_challenge_unknown(popup, totp_secret, log_fn=log_fn)
                await wait_url_change(popup)
                _emit(f"After unknown → url={short_url(popup.url)}")
                continue

            if state == GooglePageState.LOGIN_EMAIL:
                if not email:
                    await dump_page_html(popup, "popup_login_email_no_creds", log_fn)
                    raise RuntimeError(
                        "OAuth popup hiển thị trang login email nhưng không có email credentials. "
                        "Bật use_google_session=true hoặc truyền email/password."
                    )
                _emit(f"Login email → typing {email}")
                await handle_login_email(popup, email, log_fn)
                try:
                    await popup.locator(
                        'input[type="password"]:not([name="hiddenPassword"])'
                    ).first.wait_for(state="visible", timeout=cfg.password_visible_timeout_ms)
                except PlaywrightTimeoutError:
                    pass
                continue

            if state == GooglePageState.LOGIN_PASSWORD:
                if not password:
                    await dump_page_html(popup, "popup_login_password_no_creds", log_fn)
                    raise RuntimeError(
                        "OAuth popup hiển thị trang password nhưng không có password."
                    )
                _emit("Login password → typing...")
                await handle_login_password(popup, password, log_fn)
                await wait_url_change(popup, timeout_ms=cfg.password_next_timeout_ms)
                continue

        if popup.is_closed():
            _emit("popup đã đóng thành công ✓")

    except PlaywrightTimeoutError as e:
        _emit(f"timeout: {e}")
        await dump_page_html(popup, "popup_timeout", log_fn)
        raise RuntimeError(f"OAuth popup timeout: {e}")
    except Exception as e:
        from playwright._impl._errors import TargetClosedError
        if isinstance(e, TargetClosedError):
            _emit("popup closed during operation — OAuth likely succeeded ✓")
        else:
            raise


async def login_google_on_page(
    page: Page,
    email: str,
    password: str,
    totp_secret: str,
    *,
    db_path: pathlib.Path | None = None,
    log_fn: LogFn | None = None,
) -> None:
    """
    Full Google login: email → password → challenge → verify redirect.
    Dùng cho google session refresh.
    """
    def _emit(msg: str) -> None:
        _log.info("[google_login] %s", msg)
        if log_fn:
            log_fn(f"  [google_login] {msg}")

    await page.wait_for_url(
        lambda url: "accounts.google.com" in url,
        timeout=get_login_timeout_ms(), wait_until="commit",
    )
    await page.wait_for_load_state("domcontentloaded")

    cfg = _cfg()
    max_iterations = cfg.login_max_iterations
    iteration = 0
    resolved_phone: str = ""

    while iteration < max_iterations:
        iteration += 1
        state = await detect_page_state(page)
        _emit(f"[iter={iteration}] state={state.value}, url={short_url(page.url)}")

        if state == GooglePageState.DONE:
            _emit(f"Login complete, URL: {short_url(page.url)}")
            return

        if state == GooglePageState.LOGIN_EMAIL:
            _emit("→ Handling LOGIN_EMAIL")
            await handle_login_email(page, email, log_fn)
            try:
                await page.locator(
                    'input[type="password"]:not([name="hiddenPassword"])'
                ).first.wait_for(state="visible", timeout=cfg.password_visible_timeout_ms)
            except PlaywrightTimeoutError:
                pass
            continue

        if state == GooglePageState.LOGIN_PASSWORD:
            _emit("→ Handling LOGIN_PASSWORD")
            await handle_login_password(page, password, log_fn)
            await wait_url_change(page, timeout_ms=cfg.password_next_timeout_ms)
            _emit(f"After password → url={short_url(page.url)}")
            continue

        if state == GooglePageState.ACCOUNT_CHOOSER:
            _emit("→ Handling ACCOUNT_CHOOSER")
            await handle_account_chooser(page, log_fn)
            await wait_url_change(page)
            continue

        if state == GooglePageState.CONSENT:
            _emit("→ Handling CONSENT")
            await handle_consent(page, log_fn)
            await wait_url_change(page)
            _emit(f"After consent → url={short_url(page.url)}")
            continue

        if state == GooglePageState.CHALLENGE_TOTP:
            _emit("→ Handling CHALLENGE_TOTP")
            await handle_challenge_totp(page, totp_secret, log_fn)
            await wait_url_change(page)
            _emit(f"After TOTP → url={short_url(page.url)}")
            continue

        if state == GooglePageState.CHALLENGE_SELECTION:
            _emit("→ Handling CHALLENGE_SELECTION")
            await handle_challenge_selection(page, totp_secret, log_fn)
            await wait_url_change(page)
            _emit(f"After selection → url={short_url(page.url)}")
            continue

        if state == GooglePageState.CHALLENGE_PHONE:
            _emit("→ Handling CHALLENGE_PHONE")
            resolved_phone = await handle_challenge_phone(page, db_path, log_fn)
            await wait_url_change(page)
            _emit(f"After phone → url={short_url(page.url)}")
            continue

        if state == GooglePageState.CHALLENGE_PHONE_OTP:
            _emit("→ Handling CHALLENGE_PHONE_OTP")
            await handle_challenge_phone_otp(page, resolved_phone, log_fn)
            await wait_url_change(page)
            _emit(f"After phone OTP → url={short_url(page.url)}")
            continue

        if state == GooglePageState.CHALLENGE_UNKNOWN:
            _emit("→ Handling CHALLENGE_UNKNOWN")
            await handle_challenge_unknown(page, totp_secret, log_fn=log_fn)
            await wait_url_change(page)
            _emit(f"After unknown → url={short_url(page.url)}")
            continue

        if state == GooglePageState.AUTH_HANDLER:
            _emit("→ Auth handler in login flow — waiting...")
            await page.wait_for_timeout(3_000)
            continue

    raise RuntimeError(f"Google login vượt quá {max_iterations} iterations. URL: {short_url(page.url)}")
