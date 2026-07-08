"""services/cloudflare_com/flow.py - Cloudflare signup automation recipe.

Pure browser automation — nhận `page` từ gateway task, không mở browser.
Entrypoint `_signup_flow` chạy full flow signup → verify email → token.

DOM truth from Camoufox inspection:
  - email   : input[name="email"]  (type="" in rendered DOM)
  - password: input[name="password"] (single field, no confirm)
  - submit  : visible button text "Sign up"
  - turnstile: hidden input cf_challenge_response (must be non-empty before submit)
"""
from __future__ import annotations

import html as _html
import re
import time
from pathlib import Path
from typing import Any

from playwright.async_api import Error as PlaywrightError, TimeoutError as PlaywrightTimeoutError

from ...config.settings import AppConfig
from common.page_utils import dump_debug_html as _dump_debug
from common.page_utils import goto_with_reload_retry
from common.password import generate_password
from src.core.account_record import AccountRecord
from ...mail.client import Mailbox, extract_link, wait_for_message
from ..errors import EmailVerificationError, RetryableRegistrationError, SignupBlockedError
from ..protocols import LogFn


# -- Pure helpers ---------------------------------------------------------

def _extract_account_id(url: str, account_id_regex: str) -> str | None:
    m = re.search(account_id_regex, url)
    return m.group(1) if m else None


# -- Browser step helpers -------------------------------------------------

async def _solve_turnstile(page: Any, log_fn: LogFn, debug_dir: Path) -> None:
    """Click checkbox Turnstile trong CF iframe.

    DOM truth (camoufox 2026-07-04):
      div[data-testid="challenge-widget-container"]
        > label "Let us know you are human"
        > div > div > input[type=hidden][name=cf_challenge_response]  (+ CF iframe inject vào đây)
      CF iframe (challenges.cloudflare.com) rect 448x65, nằm dưới label.
      Checkbox render trong iframe (canvas/shadow, không query được qua DOM) nhưng
      click body iframe ở position left-center ({x:30,y:32}) → cf_challenge_response SET.

    Không dùng captcha API. Lỗi → raise (không fallback).
    """
    log_fn("  Waiting for CF Turnstile frame (renders after 5-10s)...")
    for sec in range(25):
        await page.wait_for_timeout(1_000)
        if any("challenges.cloudflare.com" in f.url for f in page.frames):
            log_fn(f"  CF frame at t={sec+1}s")
            break
    else:
        await _dump_debug(page, "cf_ts_no_frame.html", debug_dir)
        raise RetryableRegistrationError("Turnstile CF frame not found after 25s")

    log_fn("  Waiting for checkbox to render...")
    await page.wait_for_timeout(6_000)
    await _dump_debug(page, "cf_ts_before_click.html", debug_dir)

    # Click checkbox: position left-center của CF iframe body. Turnstile reload/detach
    # iframe giữa chừng → re-fetch frame qua page.frames mỗi click, không cache object.
    log_fn("  Clicking checkbox (left-center of CF frame)...")
    for attempt in range(3):
        cf_frames = [f for f in page.frames if "challenges.cloudflare.com" in f.url]
        if not cf_frames:
            await page.wait_for_timeout(2_000)
            continue
        try:
            await cf_frames[0].locator("body").click(timeout=8_000, position={"x": 30, "y": 32})
            log_fn(f"  Turnstile clicked (attempt {attempt+1})")
            break
        except Exception as e:  # noqa: BLE001 - iframe detach/reload, retry với frame mới
            log_fn(f"  Click attempt {attempt+1} failed: {str(e)[:80]}")
            await page.wait_for_timeout(2_000)
    else:
        await _dump_debug(page, "cf_ts_click_failed.html", debug_dir)
        raise RetryableRegistrationError("Turnstile click failed after 3 attempts")

    log_fn("  Verifying cf_challenge_response...")
    try:
        await page.wait_for_function(
            "() => { const el = document.querySelector('input[name=\"cf_challenge_response\"]'); return el && el.value && el.value.length > 0; }",
            timeout=15_000,
        )
    except PlaywrightTimeoutError as exc:
        await _dump_debug(page, "cf_ts_not_solved.html", debug_dir)
        raise RetryableRegistrationError("Turnstile not solved: cf_challenge_response empty after click") from exc

    resp = await page.evaluate(
        "() => { const el = document.querySelector('input[name=\"cf_challenge_response\"]'); return el ? el.value.length : 0; }"
    )
    log_fn(f"  Turnstile solved (cf_challenge_response {resp} chars)")


async def _fill_signup_form(page: Any, email: str, password: str, cfg: AppConfig) -> None:
    """Fill the two visible inputs on Cloudflare signup: email + password."""
    cf = cfg.cloudflare
    t = cfg.timeouts

    email_input = page.locator(cf.email_selector).first
    await email_input.wait_for(state="visible", timeout=t.probe_timeout_ms)
    await email_input.fill(email)
    await page.wait_for_timeout(t.short_delay)

    pw_input = page.locator(cf.password_selector).first
    await pw_input.wait_for(state="visible", timeout=t.probe_timeout_ms)
    await pw_input.fill(password)
    await page.wait_for_timeout(t.short_delay)


async def _click_signup_button(page: Any, cfg: AppConfig, log_fn: LogFn) -> None:
    """Click the single visible Sign up button."""
    btn = page.locator(f"button:has-text('{cfg.cloudflare.signup_button_text}')").first
    await btn.wait_for(state="visible", timeout=cfg.timeouts.probe_timeout_ms)
    await btn.click(timeout=10_000)
    log_fn("  Clicked 'Sign up'")


async def _check_signup_blocked(page: Any, log_fn: LogFn) -> None:
    """Warning condition: CF chặn sign-up tạm thời (IP/email/fingerprint bị flag).

    "You are unable to sign up at this time" = block tạm, không fatal — warning
    + cooldown 60s rồi retry với mailbox khác (xử lý ở registrar wrapper).
    """
    blocked = await page.evaluate(
        "() => (document.body.innerText || '').includes('You are unable to sign up at this time')"
    )
    if blocked:
        log_fn("  ⚠️ Cloudflare blocked sign-up (unable to sign up at this time) — cooldown 60s rồi retry")
        raise SignupBlockedError("Cloudflare blocked sign-up: unable to sign up at this time")


async def _check_for_errors(page: Any) -> str | None:
    """Check for inline error messages after signup submit."""
    selectors = ['[role="alert"]', '.c_alert', '[data-testid="form-error"]']
    for sel in selectors:
        try:
            el = page.locator(sel).first
            if await el.is_visible(timeout=1_500):
                txt = await el.inner_text(timeout=1_500)
                return txt.strip()
        except PlaywrightTimeoutError:
            continue
    return None


async def _wait_for_verify_email(mailbox: Mailbox, cfg: AppConfig, log_fn: LogFn) -> str:
    """Wait for Cloudflare verification email and extract verify link."""
    msg = await wait_for_message(
        mailbox,
        from_contains="cloudflare",
        timeout=cfg.cloudflare.verification_wait_sec,
        poll_interval=cfg.timeouts.poll_interval,
        log_fn=log_fn,
    )
    if not msg:
        raise EmailVerificationError("No verification email from Cloudflare")

    log_fn(f"  Subject: {msg.get('subject', 'N/A')}")

    body = msg.get("body", "") or msg.get("text", "") or ""
    html_parts = msg.get("html", [""])
    html_text = html_parts[0] if html_parts else ""

    link = extract_link(body, "cloudflare") or extract_link(html_text, "cloudflare")
    if not link:
        raise EmailVerificationError("Could not extract verify link from email")
    return _html.unescape(link).rstrip(".,;)")


async def _skip_onboarding(page: Any, cfg: AppConfig, log_fn: LogFn) -> None:
    """Click any onboarding skip buttons until none remain."""
    for _ in range(5):
        await page.wait_for_timeout(cfg.cloudflare.onboarding_skip_wait_ms)
        found = False
        for skip_text in cfg.cloudflare.skip_button_texts:
            try:
                btn = page.get_by_role("button", name=skip_text).first
                if await btn.is_visible(timeout=1_500):
                    await btn.click(timeout=5_000)
                    log_fn(f"  Skipped onboarding via '{skip_text}'")
                    found = True
                    break
            except PlaywrightTimeoutError:
                continue
        if not found:
            break


async def _navigate_to_token_page(page: Any, account_id: str, cfg: AppConfig, log_fn: LogFn) -> None:
    """Mở token-create page.

    CF intent: account mới goto thẳng URL /api-tokens/create bị redirect về
    dashboard home (dump truth: title "Cloudflare Dashboard", 0 checkbox).
    Navigate đúng = từ dashboard click sidebar link "Account API Tokens" →
    CF route vào token page. Fail loud nếu không đến.
    """
    url = cfg.cloudflare.token_create_url_template.format(account_id=account_id)
    log_fn("  Navigating to token creation page...")
    t = cfg.timeouts
    debug_dir = cfg.base_dir / "debug"

    # Thử goto URL trước; verify URL thực tế sau navigation (không tin domcontentloaded).
    await page.goto(url, timeout=t.page_load * 2, wait_until="domcontentloaded")
    await page.wait_for_timeout(t.step_delay)

    if "api-tokens/create" not in page.url:
        # CF redirect về dashboard → click sidebar link theo intent CF.
        log_fn(f"  Redirected to dashboard ({page.url}), clicking sidebar 'Account API Tokens'...")
        link = page.get_by_role("link", name="Account API Tokens").first
        await link.wait_for(state="visible", timeout=t.probe_timeout_ms * 5)
        await link.click(timeout=t.probe_timeout_ms * 5)
        try:
            await page.wait_for_url("**/api-tokens/**", timeout=t.page_load * 2)
        except PlaywrightTimeoutError as exc:
            await _dump_debug(page, "cf_token_nav_failed.html", debug_dir)
            raise RetryableRegistrationError(
                f"Click sidebar không đến token page, URL={page.url}"
            ) from exc

    # Token page loaded — đợi React mount form (SPA, render sau domcontentloaded).
    try:
        await page.locator('span[role="checkbox"]').first.wait_for(
            state="visible", timeout=t.probe_timeout_ms * 10,
        )
    except PlaywrightTimeoutError as exc:
        await _dump_debug(page, "cf_token_page_timeout_1.html", debug_dir)
        raise RetryableRegistrationError(
            f"Token page form không render, URL={page.url}"
        ) from exc
    await page.wait_for_timeout(t.step_delay)


async def _select_ai_permissions(page: Any, cfg: AppConfig, log_fn: LogFn) -> None:
    """Select the three required permissions on the token creation page.

    DOM truth (camoufox 2026-07-04): token page là React SPA — form render sau
    domcontentloaded. Mỗi permission = 1 <li> row chứa label text + các
    <span role="checkbox" aria-label="Read|Run|Edit">. Click span → React toggle.
    Verify sau click — fail loud nếu React không set state.
    """
    cf = cfg.cloudflare
    t = cfg.timeouts

    log_fn("  Waiting for permission form to render...")
    try:
        await page.locator('span[role="checkbox"]').first.wait_for(
            state="visible", timeout=t.probe_timeout_ms * 5,
        )
    except PlaywrightTimeoutError as exc:
        raise RetryableRegistrationError("Token permission form did not render") from exc

    permissions = [
        (cf.ai_gateway_run_label, "Run"),
        (cf.ai_search_run_label, "Run"),
        (cf.workers_ai_read_label, "Read"),
    ]

    for label, level in permissions:
        log_fn(f"  Selecting {label} -> {level}")
        try:
            # XPath 1-pass: <li> chứa <span> text=label VÀ có checkbox con (sidebar
            # <li> không có checkbox → tự loại). XPath engine resolve 1 lần.
            checkbox = page.locator(
                f'xpath=//li[.//span[normalize-space()="{label}"]]'
                f'//span[@role="checkbox" and @aria-label="{level}"]'
            ).first
            await checkbox.wait_for(state="visible", timeout=t.probe_timeout_ms)
            await checkbox.scroll_into_view_if_needed(timeout=3_000)
            # Base UI: checkbox span (tabindex=0, role=checkbox) lắng nghe keyboard,
            # KHÔNG phải synthetic click. Toggle chuẩn: focus span + Space.
            await checkbox.focus()
            await checkbox.press("Space")
            await page.wait_for_timeout(t.short_delay)
            is_checked = await checkbox.evaluate(
                "el => el.getAttribute('aria-checked') === 'true' || el.hasAttribute('data-checked')"
            )
            if not is_checked:
                raise RetryableRegistrationError(f"{label} -> {level}: checkbox not checked after click")
        except PlaywrightTimeoutError as exc:
            await _dump_debug(page, f"cf_select_perm_{label}.html", cfg.base_dir / "debug")
            raise RetryableRegistrationError(f"Failed to select {label} permission") from exc


async def _review_and_create_token(page: Any, cfg: AppConfig, log_fn: LogFn) -> None:
    """Click Review token, then Create token."""
    t = cfg.timeouts
    review_btn = page.get_by_role("button", name=cfg.cloudflare.review_button_text).first
    await review_btn.click(timeout=10_000)
    log_fn("  Clicked 'Review token'")
    await page.wait_for_timeout(t.step_delay)

    create_btn = page.get_by_role("button", name=cfg.cloudflare.create_button_text).first
    await create_btn.click(timeout=10_000)
    log_fn("  Clicked 'Create token'")
    await page.wait_for_timeout(t.step_delay)


async def _extract_api_token(page: Any, cfg: AppConfig, log_fn: LogFn, debug_dir: Path) -> str:
    """Extract the API token displayed after creation.

    CF API token format: cfat_<40+ chars>. Token hiển thị trong modal sau click
    'Create token', render sau 1-3s. Poll body text cho regex cfat_ — không đoán
    selector vì modal DOM thay đổi.
    """
    cf = cfg.cloudflare
    token_re = re.compile(cf.token_regex)

    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        try:
            page_text = await page.inner_text("body", timeout=2_000)
        except PlaywrightError:
            page_text = ""
        m = token_re.search(page_text)
        if m:
            token = m.group(0)
            log_fn(f"  Token extracted: {token[:12]}...")
            return token
        await page.wait_for_timeout(1_000)

    await _dump_debug(page, "cf_token_not_found.html", debug_dir)
    raise RetryableRegistrationError("Could not extract API token after creation")


# -- Main flow ------------------------------------------------------------

async def _signup_flow(page: Any, mailbox: Mailbox, cfg: AppConfig, log_fn: LogFn) -> AccountRecord:
    """Execute the full Cloudflare registration flow."""
    t = cfg.timeouts
    debug_dir = cfg.base_dir / "debug"
    debug_dir.mkdir(parents=True, exist_ok=True)

    email = mailbox.email
    password = generate_password(cfg.register.password_length)

    # [1] Open signup page — goto_with_reload_retry: probe email input, reload hard + retry nếu chậm.
    log_fn(f"\n[1/9] Opening {cfg.cloudflare.signup_url}...")
    await goto_with_reload_retry(
        page,
        cfg.cloudflare.signup_url,
        probe=lambda p: p.locator(cfg.cloudflare.email_selector).first.wait_for(
            state="visible", timeout=t.goto_probe_timeout_ms,
        ),
        probe_timeout_ms=t.goto_probe_timeout_ms,
        goto_timeout_ms=t.page_load * 3,
        log_fn=log_fn,
        debug_dir=debug_dir,
        debug_tag="cf_signup",
    )
    await page.wait_for_timeout(t.step_delay)
    await _dump_debug(page, "cf_01_signup.html", debug_dir)

    # [2] Fill form (email + password)
    log_fn("\n[2/9] Filling signup form...")
    await _fill_signup_form(page, email, password, cfg)
    await _dump_debug(page, "cf_02_filled.html", debug_dir)

    # [3] Solve Turnstile — phải solve TRƯỚC khi submit.
    log_fn("\n[3/9] Solving Turnstile (Verify you are human)...")
    await _solve_turnstile(page, log_fn, debug_dir)
    await _dump_debug(page, "cf_03_turnstile.html", debug_dir)

    # [4] Click Sign up
    log_fn("\n[4/9] Clicking Sign up...")
    await _click_signup_button(page, cfg, log_fn)
    await page.wait_for_timeout(cfg.cloudflare.post_submit_wait_ms)
    await _dump_debug(page, "cf_04_clicked.html", debug_dir)

    # [5] Wait for redirect to verify/confirm-email prompt
    log_fn("\n[5/9] Waiting for verification prompt...")
    for _ in range(5):
        await page.wait_for_timeout(2_000)
        if "confirm-email" in page.url or "verify" in page.url:
            log_fn(f"  Redirected: {page.url}")
            break
    await _dump_debug(page, "cf_05_submitted.html", debug_dir)

    err = await _check_for_errors(page)
    if err:
        raise RetryableRegistrationError(f"Signup form error: {err}")

    await _check_signup_blocked(page, log_fn)

    if "confirm-email" in page.url or "verify" in page.url:
        log_fn(f"  Redirected to verification prompt: {page.url}")

    # [6] Wait for verification email
    log_fn("\n[6/9] Waiting for verification email...")
    verify_link = await _wait_for_verify_email(mailbox, cfg, log_fn)
    log_fn(f"  Verify link: {verify_link[:80]}...")

    # [7] Open verify link — cùng page (cookie session đăng ký còn). CF verify
    # token là 1 lần dùng → KHÔNG reload hard. 2 case:
    #   case 1: pass luôn → redirect dash.cloudflare.com/{hex32}/home/overview
    #   case 2: redirect về /login → fill email+pass + click Log in → hex32
    log_fn("\n[7/9] Opening verify link...")
    await page.goto(verify_link, wait_until="domcontentloaded", timeout=t.page_load * 2)

    cf = cfg.cloudflare
    verify_deadline = time.monotonic() + (cf.verify_redirect_timeout_ms / 1000)
    hex32_re = re.compile(cf.account_id_regex)
    signin_re = re.compile(cf.signin_url_pattern)

    while time.monotonic() < verify_deadline:
        url = page.url
        if hex32_re.search(url):
            log_fn(f"  ✅ Verified — dashboard: {url}")
            break
        if signin_re.search(url):
            log_fn("  Verify redirect → signin. Filling email + password...")
            await _fill_signup_form(page, email, password, cfg)
            login_btn = page.locator(f"button:has-text('{cf.login_button_text}')").first
            await login_btn.wait_for(state="visible", timeout=t.probe_timeout_ms)
            await login_btn.click(timeout=10_000)
            log_fn(f"  Clicked '{cf.login_button_text}'")
            continue
        await page.wait_for_timeout(1_000)
    else:
        await _dump_debug(page, "cf_no_redirect.html", debug_dir)
        raise RetryableRegistrationError(f"Verify link không redirect sau dashboard: {page.url}")
    await _dump_debug(page, "cf_05_verified.html", debug_dir)

    # [8] Skip onboarding
    log_fn("\n[8/9] Skipping onboarding...")
    await _skip_onboarding(page, cfg, log_fn)

    account_id = _extract_account_id(page.url, cfg.cloudflare.account_id_regex)
    if not account_id:
        await _dump_debug(page, "cf_no_account_id.html", debug_dir)
        raise RetryableRegistrationError(f"Could not extract account_id from URL: {page.url}")
    log_fn(f"  account_id: {account_id}")

    # [9] Create API token
    log_fn("\n[9/9] Creating API token...")
    await _navigate_to_token_page(page, account_id, cfg, log_fn)
    await _dump_debug(page, "cf_06_token_page.html", debug_dir)
    await _select_ai_permissions(page, cfg, log_fn)
    await _review_and_create_token(page, cfg, log_fn)

    api_key = await _extract_api_token(page, cfg, log_fn, debug_dir)
    log_fn(f"  Token extracted ({len(api_key)} chars)")

    return AccountRecord(
        service="CLOUDFLARE",
        email=email,
        password=password,
        api_key=api_key,
        account_id=account_id,
    )
