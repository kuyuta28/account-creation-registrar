"""
google_oauth/_handlers.py — State handlers.
Mỗi function xử lý đúng 1 GooglePageState (SRP).
"""
from __future__ import annotations

import logging
import re
import time as _time

import pyotp
from playwright.async_api import (
    Page,
    TimeoutError as PlaywrightTimeoutError,
)

from ._constants import (
    AUTHENTICATOR_CLICK_LOCATORS,
    CONSENT_BUTTON_LOCATORS,
    PHONE_CLICK_LOCATORS,
    TOTP_INPUT_LOCATORS,
    TRY_ANOTHER_WAY_LOCATORS,
    get_login_timeout_ms,
    _cfg,
)
from ._helpers import LogFn, dump_page_html, emit_log, safe_wait, short_url

_log = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# Login handlers
# ══════════════════════════════════════════════════════════════════════════════


async def handle_login_email(
    page: Page, email: str, log_fn: LogFn | None = None,
) -> None:
    """Nhập email và click Next."""
    email_input = page.locator('input[type="email"], input[name="identifier"]')
    await email_input.wait_for(state="visible", timeout=get_login_timeout_ms())
    await email_input.fill(email)
    next_btn = page.locator(
        "#identifierNext button, "
        "button:has-text('Next'), button:has-text('Tiep theo'), "
        "button:has-text('Tiếp theo')"
    )
    await next_btn.first.click()
    emit_log(f"Email filled: {email} → Next clicked", log_fn)


async def handle_login_password(
    page: Page, password: str, log_fn: LogFn | None = None,
) -> None:
    """Nhập password và click Next."""
    cfg = _cfg()
    pwd_input = page.locator('input[type="password"]:not([name="hiddenPassword"])').first
    await pwd_input.wait_for(state="visible", timeout=cfg.password_visible_timeout_ms)
    await pwd_input.fill(password)
    pwd_next = page.locator(
        "#passwordNext button, "
        "button:has-text('Next'), button:has-text('Tiep theo'), "
        "button:has-text('Tiếp theo')"
    )
    await pwd_next.first.wait_for(state="visible", timeout=cfg.password_next_timeout_ms)
    await pwd_next.first.click()
    emit_log("Password filled → Next clicked", log_fn)


# ══════════════════════════════════════════════════════════════════════════════
# Account chooser & consent
# ══════════════════════════════════════════════════════════════════════════════


async def handle_account_chooser(
    page: Page, log_fn: LogFn | None = None,
) -> None:
    """Click account đầu tiên trong danh sách."""
    cfg = _cfg()
    account_btn = page.locator('div[data-identifier][role="link"]').first
    await account_btn.wait_for(state="visible", timeout=cfg.account_chooser_timeout_ms)
    identifier = await account_btn.get_attribute("data-identifier")
    await account_btn.click(timeout=cfg.account_chooser_click_timeout_ms, force=True)
    emit_log(f"Account chooser → selected: {identifier}", log_fn)
    await safe_wait(page)


async def handle_consent(
    page: Page, log_fn: LogFn | None = None,
) -> None:
    """Click Allow/Continue trên consent screen."""
    emit_log(f"Consent page detected. URL: {short_url(page.url)}", log_fn)
    await dump_page_html(page, "consent_page", log_fn)
    allow_btn = page.locator(CONSENT_BUTTON_LOCATORS)
    cfg = _cfg()
    try:
        await allow_btn.first.wait_for(state="visible", timeout=cfg.consent_timeout_ms)
        btn_text = await allow_btn.first.inner_text()
        emit_log(f"Consent → clicking button: {btn_text!r}", log_fn)
        await allow_btn.first.click(force=True)
        emit_log("Consent → Allow clicked ✓", log_fn)
        await safe_wait(page)
    except PlaywrightTimeoutError:
        emit_log("Consent → no Allow/Continue button found (auto-approved or popup closing)", log_fn)


# ══════════════════════════════════════════════════════════════════════════════
# Challenge handlers
# ══════════════════════════════════════════════════════════════════════════════


async def handle_challenge_totp(
    page: Page, totp_secret: str, log_fn: LogFn | None = None,
) -> None:
    """Nhập TOTP code vào challenge page."""
    if not totp_secret.strip():
        await dump_page_html(page, "challenge_totp_no_secret", log_fn)
        raise RuntimeError(
            f"Google yêu cầu TOTP nhưng không có totp_secret. URL: {short_url(page.url)}"
        )
    secret_clean = totp_secret.replace(" ", "").upper()
    await _fill_totp(page, secret_clean, log_fn)
    await safe_wait(page)


async def handle_challenge_selection(
    page: Page, totp_secret: str, log_fn: LogFn | None = None,
) -> None:
    """Challenge selection page — thử Authenticator trước, nếu không thì Phone."""
    await dump_page_html(page, "challenge_selection", log_fn)

    # Ưu tiên Authenticator nếu có TOTP secret
    if totp_secret.strip():
        try:
            await _click_authenticator_option(page, log_fn)
            emit_log("Challenge selection → Authenticator clicked", log_fn)
            await safe_wait(page)
            url_after = page.url
            if "challenge/selection" not in url_after:
                return  # Đã chuyển trang thành công
            emit_log("Authenticator click không chuyển trang, thử Phone...", log_fn)
        except RuntimeError:
            emit_log("Authenticator option không có, thử Phone...", log_fn)

    # Chọn Phone option
    await _click_phone_option(page, log_fn)
    emit_log("Challenge selection → Phone clicked", log_fn)
    await safe_wait(page)


async def handle_challenge_phone(
    page: Page,
    log_fn: LogFn | None = None,
) -> str:
    """
    challenge/ipp/collect — Google yêu cầu xác nhận số điện thoại đã đăng ký.
    Auto-detect SIM từ 2 số cuối Google hiển thị trên trang.
    Fill số thật vào input, click Send. Trả về resolved phone number.
    """
    from common.database._async import get_sms_phones_async
    from common.database._engine import get_async_session

    await dump_page_html(page, "challenge_phone_collect", log_fn)

    # Extract 2 số cuối từ hint Google hiển thị
    page_text = await page.locator("body").inner_text()
    hint_match = re.search(r'[\u2022•\*](\d{2})(?=[.\s,;!?\)]|$)', page_text)
    if not hint_match:
        await dump_page_html(page, "challenge_phone_no_hint", log_fn)
        raise RuntimeError(
            f"Không tìm thấy hint số điện thoại (2 số cuối) trên trang. "
            f"URL: {short_url(page.url)} | snippet: {page_text[:300]!r}"
        )

    last_two = hint_match.group(1)
    emit_log(f"Google phone hint: 2 số cuối = {last_two!r}", log_fn)

    async with get_async_session() as session:
        phones = await get_sms_phones_async(session)
    active_phones = [p["phone"] for p in phones if not p.get("disabled")]
    matched = [p for p in active_phones if p.endswith(last_two)]

    if not matched:
        raise RuntimeError(
            f"Không tìm thấy SIM kết thúc bằng '{last_two}' trong DB. "
            f"SIMs đang có: {active_phones}"
        )
    if len(matched) > 1:
        raise RuntimeError(
            f"Có nhiều SIM kết thúc bằng '{last_two}': {matched}. "
            "Đổi số cuối cho mỗi SIM để phân biệt."
        )

    resolved_phone = matched[0]
    emit_log(f"Resolved SIM: {resolved_phone!r}", log_fn)

    cfg = _cfg()
    phone_input = page.locator('input#phoneNumberId, input[name="phoneNumber"], input[aria-label*="phone" i]')
    await phone_input.first.wait_for(state="visible", timeout=cfg.phone_input_timeout_ms)
    await phone_input.first.click(force=True)
    await page.wait_for_timeout(200)
    await phone_input.first.fill(resolved_phone)

    send_btn = page.locator(
        'button:has-text("Send"), button:has-text("Gửi"), '
        'button[type="submit"]'
    )
    await send_btn.first.wait_for(state="visible", timeout=cfg.phone_send_timeout_ms)
    await send_btn.first.click(force=True)
    emit_log(f"Phone challenge → filled {resolved_phone!r}, clicked Send", log_fn)
    await safe_wait(page)
    await dump_page_html(page, "challenge_phone_after_send", log_fn)
    return resolved_phone


async def handle_challenge_phone_otp(
    page: Page,
    phone: str,
    log_fn: LogFn | None = None,
) -> None:
    """
    challenge/ipp/... — Google đã gửi OTP qua SMS, cần nhập code.
    Đợi SMS đến qua sms_webhook, extract OTP, nhập vào.
    """
    await dump_page_html(page, "challenge_phone_otp", log_fn)

    if not phone.strip():
        raise RuntimeError(
            f"challenge/ipp OTP page nhưng không có phone để nhận SMS. URL: {short_url(page.url)}"
        )

    from ...mail.providers.sms_webhook import make_mailbox, wait_for_message

    emit_log(f"Waiting for SMS OTP on {phone!r}...", log_fn)
    cfg = _cfg()
    box = make_mailbox(phone)
    wait_start = _time.monotonic()
    msg = await wait_for_message(
        box,
        from_contains="",
        body_contains="",
        timeout=cfg.sms_otp_timeout_sec,
        poll_interval=cfg.sms_otp_poll_interval_sec,
        after_monotonic=wait_start,
    )

    if msg is None:
        cfg = _cfg()
        raise RuntimeError(
            f"Timeout {cfg.sms_otp_timeout_sec}s chờ SMS OTP cho số {phone!r}. "
            "Kiểm tra API server đang chạy và SmsForwarder đã cấu hình đúng webhook."
        )

    # Extract 6-digit OTP từ text — Google gửi dạng "G-123456 is your..."
    sms_text = msg.get("text", "") if isinstance(msg, dict) else ""
    match = re.search(r'G-(\d{6})', sms_text) or re.search(r'\b(\d{6})\b', sms_text)
    if not match:
        raise RuntimeError(
            f"Không tìm thấy OTP 6 chữ số trong SMS: {sms_text!r}"
        )
    otp_code = match.group(1)
    emit_log(f"SMS OTP received: {otp_code}", log_fn)

    otp_input = page.locator(
        'input[type="tel"], input[type="text"], '
        'input[aria-label*="code" i], input[aria-label*="verification" i]'
    )
    cfg2 = _cfg()
    await otp_input.first.wait_for(state="visible", timeout=cfg2.otp_input_timeout_ms)
    await otp_input.first.click(force=True)
    await page.wait_for_timeout(200)
    await otp_input.first.fill(otp_code)

    next_btn = page.locator(
        'button:has-text("Next"), button:has-text("Tiếp theo"), '
        'button:has-text("Verify"), button:has-text("Xác minh"), '
        'button[type="submit"]'
    )
    await next_btn.first.wait_for(state="visible", timeout=cfg2.otp_next_timeout_ms)
    await next_btn.first.click(force=True)
    emit_log(f"Phone OTP {otp_code} submitted → Next clicked", log_fn)
    await safe_wait(page)
    await dump_page_html(page, "challenge_phone_otp_after_submit", log_fn)


async def handle_challenge_unknown(
    page: Page, totp_secret: str, log_fn: LogFn | None = None,
) -> None:
    """
    Unknown challenge — thử click 'Try another way' để về selection page.
    """
    current_url = short_url(page.url)
    emit_log(f"⚠ Unknown challenge. URL: {current_url}", log_fn)
    await dump_page_html(page, "challenge_unknown", log_fn)

    if not totp_secret.strip():
        raise RuntimeError(
            f"Google challenge page không nhận diện được và không có totp_secret. URL: {current_url}"
        )

    emit_log("Trying 'Try another way' button...", log_fn)
    await _click_try_another_way(page, log_fn)
    emit_log("Unknown challenge → 'Try another way' clicked ✓", log_fn)


# ══════════════════════════════════════════════════════════════════════════════
# Internal helpers
# ══════════════════════════════════════════════════════════════════════════════


async def _fill_totp(page: Page, secret_clean: str, log_fn: LogFn | None = None) -> None:
    """Find TOTP input, fill OTP code, click Next."""
    cfg = _cfg()
    totp_input = None
    for loc in TOTP_INPUT_LOCATORS:
        candidate = page.locator(loc)
        try:
            await candidate.first.wait_for(state="visible", timeout=cfg.totp_candidate_timeout_ms)
            totp_input = candidate.first
            break
        except PlaywrightTimeoutError:
            continue

    if totp_input is None:
        await dump_page_html(page, "totp_input_not_found", log_fn)
        raise RuntimeError(f"Không tìm thấy ô nhập TOTP. URL: {short_url(page.url)}")

    otp_code = pyotp.TOTP(secret_clean).now()
    await totp_input.click(force=True)
    await page.wait_for_timeout(200)
    await totp_input.fill(otp_code)
    await page.wait_for_timeout(500)

    next_btn = page.locator(
        "#totpNext button, "
        "button:has-text('Next'), button:has-text('Tiếp theo'), "
        "button:has-text('Verify'), button:has-text('Xác minh')"
    )
    await next_btn.first.wait_for(state="visible", timeout=cfg.totp_next_timeout_ms)
    await next_btn.first.click(force=True)
    emit_log(f"TOTP filled: {otp_code} → Next clicked", log_fn)
    await safe_wait(page)


async def _click_authenticator_option(page: Page, log_fn: LogFn | None = None) -> None:
    """Click 'Google Authenticator' trên trang challenge/selection."""
    cfg = _cfg()
    await page.wait_for_load_state("domcontentloaded", timeout=cfg.page_load_timeout_ms)
    for loc_str in AUTHENTICATOR_CLICK_LOCATORS:
        candidate = page.locator(loc_str)
        try:
            await candidate.first.wait_for(state="visible", timeout=cfg.authenticator_probe_timeout_ms)
            await candidate.first.click(force=True)
            emit_log(f"Đã click Authenticator via: {loc_str}", log_fn)
            return
        except PlaywrightTimeoutError:
            continue
    await dump_page_html(page, "authenticator_not_found", log_fn)
    raise RuntimeError(f"Không click được Authenticator option. URL: {short_url(page.url)}")


async def _click_phone_option(page: Page, log_fn: LogFn | None = None) -> None:
    """Click phone/SMS option trên trang challenge/selection."""
    cfg = _cfg()
    await page.wait_for_load_state("domcontentloaded", timeout=cfg.page_load_timeout_ms)
    for loc_str in PHONE_CLICK_LOCATORS:
        candidate = page.locator(loc_str)
        try:
            await candidate.first.wait_for(state="visible", timeout=cfg.phone_probe_timeout_ms)
            await candidate.first.click(force=True)
            emit_log(f"Đã click Phone via: {loc_str}", log_fn)
            return
        except PlaywrightTimeoutError:
            continue
    await dump_page_html(page, "phone_option_not_found", log_fn)
    raise RuntimeError(f"Không click được Phone option trên selection page. URL: {short_url(page.url)}")


async def _click_try_another_way(page: Page, log_fn: LogFn | None = None) -> None:
    """Click 'Try another way' → quay lại selection."""
    cfg = _cfg()
    try_another = page.locator(TRY_ANOTHER_WAY_LOCATORS)
    try:
        await try_another.first.wait_for(state="visible", timeout=cfg.try_another_way_timeout_ms)
        await try_another.first.click(force=True)
        emit_log("Clicked 'Try another way'", log_fn)
        await safe_wait(page)
    except PlaywrightTimeoutError:
        await dump_page_html(page, "try_another_way_not_found", log_fn)
        raise RuntimeError(
            f"Không tìm thấy 'Try another way' button. URL: {short_url(page.url)}"
        )
