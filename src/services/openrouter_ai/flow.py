"""services/openrouter_ai/flow.py - OpenRouter signup automation recipe.

Pure browser automation — nhận `page` từ gateway task, không mở browser.
Entrypoint `_signup_flow` chạy full flow signup → magic link → privacy → API key.
"""
from __future__ import annotations

import html as _html
import re
from pathlib import Path
from typing import Any

from ...config.settings import AppConfig
from common.page_utils import dump_debug_html as _dump_debug_html
from src.core.account_record import AccountRecord
from ...mail.client import Mailbox, extract_link, get_message_body, wait_for_message
from ..protocols import LogFn

_VERIFY_FRAG = "verify-email-address"


# -- Browser step helpers -------------------------------------------------

async def _fill_signup_form(page: Any, email: str, password: str) -> None:
    await page.locator("input[name=emailAddress]").fill(email)
    await page.wait_for_timeout(300)
    await page.locator("input[type=password]").fill(password)
    await page.wait_for_timeout(300)
    legal = page.locator('[name="legalAccepted"]')
    try:
        await legal.click(timeout=3_000)
    except Exception:  # noqa: BLE001 - best-effort optional UI action
        await page.evaluate('document.querySelector(\'[name="legalAccepted"]\').click()')
    await page.wait_for_timeout(400)


async def _click_primary_button(page: Any) -> None:
    # dispatch click event trực tiếp để tránh overlay/camoufox block
    clicked = await page.evaluate(
        '() => { const b = document.querySelector(\'[data-localization-key="formButtonPrimary"]\');'
        ' if (!b) return false; b.click(); return true; }'
    )
    if not clicked:
        await page.locator('[data-localization-key="formButtonPrimary"]').click(timeout=10_000)


async def _dump_frames(page: Any, log_fn: LogFn) -> None:
    frames = page.frames
    log_fn(f"  [frames] count={len(frames)}")
    for i, f in enumerate(frames):
        log_fn(f"    [{i}] {f.url[:120]}")


async def _solve_turnstile_real(page: Any, log_fn: LogFn, debug_dir: Path) -> None:
    """Click Turnstile checkbox bang cach lay CF frame tu page.frames roi click element ben trong."""
    log_fn("  Waiting for CF frame...")
    cf_frame = None
    for sec in range(20):
        await page.wait_for_timeout(1_000)
        cf_frames = [f for f in page.frames if "challenges.cloudflare.com" in f.url]
        if cf_frames:
            cf_frame = cf_frames[0]
            log_fn(f"  CF frame at {sec+1}s: {cf_frame.url[:80]}")
            break
    else:
        log_fn("  [WARN] CF frame not found after 20s")
        await _dump_debug_html(page, "or_ts_no_frame.html", debug_dir)
        return

    await page.wait_for_timeout(2_000)
    await _dump_debug_html(page, "or_ts_01_before_click.html", debug_dir)

    for attempt in range(3):
        try:
            await cf_frame.locator("body").click(timeout=10_000)
            log_fn(f"  Turnstile clicked (attempt {attempt+1})")
            await page.wait_for_timeout(3_000)
            await _dump_debug_html(page, f"or_ts_click{attempt+1}.html", debug_dir)
            break
        except Exception as e:  # noqa: BLE001 — best-effort captcha UI action
            log_fn(f"  Turnstile click attempt {attempt+1} failed: {str(e)[:80]}")
            await page.wait_for_timeout(3_000)


async def _already_on_verify(page: Any) -> bool:
    """Check xem page da chuyen sang 'Verify your email' chua (URL hoac content)."""
    if _VERIFY_FRAG in page.url:
        return True
    try:
        txt = await page.inner_text("body", timeout=2_000)
        return "verify your email" in txt.lower()
    except Exception:  # noqa: BLE001 - best-effort UI probe
        return False


async def _check_clerk_errors(page: Any) -> str | None:
    """Check Clerk form cho error messages. Trả error text hoặc None."""
    try:
        err_els = await page.locator('.cl-formFieldError, .cl-formFieldErrorText, .cl-alert').all_inner_texts()
        err_text = " | ".join(e.strip() for e in err_els if e.strip())
        if err_text:
            return err_text
    except Exception:  # noqa: BLE001 - best-effort optional UI action
        pass
    try:
        body = await page.inner_text("body", timeout=2_000)
        lower = body.lower()
        if "temporary email" in lower or "not supported" in lower:
            return "Temporary email services are not supported"
        if "breach" in lower:
            return "Password in breach list"
        if "not allowed" in lower:
            return "Email domain not allowed"
    except Exception:  # noqa: BLE001 - best-effort optional UI action
        pass
    return None


async def _wait_and_submit(page: Any, log_fn: LogFn, debug_dir: Path) -> None:
    """Chờ Clerk auto-submit hoặc button enable rồi click. Clerk thường tự submit sau Turnstile."""
    if await _already_on_verify(page):
        log_fn("  Already on verify page (Clerk auto-submitted)")
        return

    log_fn("  Waiting for button to enable (up to 60s)...")
    try:
        await page.wait_for_function(
            '() => {'
            '  const b = document.querySelector(\'[data-localization-key="formButtonPrimary"]\');'
            '  const onVerify = document.body && document.body.innerText.toLowerCase().includes("verify your email");'
            '  return onVerify || (b && !b.disabled && !b.classList.contains("cl-loading"));'
            '}',
            timeout=60_000,
        )
    except Exception:  # noqa: BLE001 - best-effort UI action
        if await _already_on_verify(page):
            log_fn("  Verify page reached during wait")
            return
        await _dump_debug_html(page, "openrouter_button_locked.html", debug_dir)
        log_fn("  Button still locked after 60s")
        raise RuntimeError("Turnstile not solved - button remained locked after 60s")

    if await _already_on_verify(page):
        log_fn("  Verify page reached (Clerk auto-submitted)")
        return

    log_fn("  Button enabled - clicking")
    await _click_primary_button(page)

    await page.wait_for_timeout(2_000)
    err = await _check_clerk_errors(page)
    if err:
        await _dump_debug_html(page, "openrouter_submit_error.html", debug_dir)
        raise RuntimeError(f"Clerk error after submit: {err}")

    for tick in range(30):
        await page.wait_for_timeout(1_000)
        if await _already_on_verify(page):
            return
        if tick % 5 == 4:
            log_fn(f"  Waiting for verify page... ({tick+1}s)")
            err = await _check_clerk_errors(page)
            if err:
                await _dump_debug_html(page, "openrouter_submit_error.html", debug_dir)
                raise RuntimeError(f"Clerk error after submit: {err}")
    await _dump_debug_html(page, "openrouter_submit_fail.html", debug_dir)
    err = await _check_clerk_errors(page)
    if err:
        raise RuntimeError(f"Clerk error: {err}")
    raise RuntimeError(f"Did not reach verify page after 30s. URL: {page.url}")


async def _fetch_magic_link(mailbox: Mailbox, timeout: int, log_fn: LogFn | None = None) -> str:
    msg = await wait_for_message(mailbox, from_contains="openrouter", timeout=timeout, log_fn=log_fn)
    if not msg:
        raise RuntimeError("No email received from OpenRouter")

    # Mailosaur list endpoint trả body rỗng — phải fetch full message riêng
    msg_id = msg.get("id", "")
    if not msg_id:
        raise RuntimeError("Mail message missing id")
    full_body = await get_message_body(mailbox, msg_id)
    if log_fn:
        log_fn(f"  Fetched full body ({len(full_body)} chars)")

    link = extract_link(full_body, "openrouter.ai")
    if not link:
        raise RuntimeError("Could not extract magic link from email")
    return _html.unescape(link).rstrip(".,;)")


async def _navigate_magic_link(page: Any, link: str, timeout_ms: int, log_fn: LogFn, debug_dir: Path) -> None:
    """Mở magic link trên CÙNG page (camoufox ko share session giữa pages), chờ redirect."""
    await page.goto(link, timeout=timeout_ms * 2, wait_until="domcontentloaded")
    await page.wait_for_timeout(3_000)

    # Trang clerk verify co Turnstile checkbox - click no
    for sec in range(15):
        cf_frames = [f for f in page.frames if "challenges.cloudflare.com" in f.url]
        if cf_frames:
            log_fn(f"  Magic link page: CF frame found at {sec+1}s")
            await page.wait_for_timeout(2_000)
            try:
                await cf_frames[0].locator("body").click(timeout=10_000)
                log_fn("  Magic link page: clicked CF checkbox")
            except Exception as e:  # noqa: BLE001 - best-effort UI action
                log_fn(f"  Magic link page: click error (normal): {e}")
            break
        await page.wait_for_timeout(1_000)

    for _ in range(30):
        await page.wait_for_timeout(1_000)
        url = page.url.lower()
        if "openrouter.ai" in url and "clerk." not in url:
            log_fn(f"  Magic link redirected to: {page.url[:100]}")
            await page.wait_for_timeout(3_000)
            return
    await _dump_debug_html(page, "magic_link_stuck.html", debug_dir)
    raise RuntimeError(f"Still on auth page after magic link (30s). URL: {page.url}")


async def _enable_privacy_options(page: Any, timeout_ms: int, log_fn: LogFn, debug_dir: Path, or_cfg: Any = None) -> None:
    """Bật privacy toggles trên /settings/privacy."""
    _privacy_url = or_cfg.privacy_settings_url if or_cfg else "https://openrouter.ai/settings/privacy"
    log_fn("  Navigating to /settings/privacy...")
    await page.goto(_privacy_url, timeout=timeout_ms * 2, wait_until="domcontentloaded")
    await page.wait_for_timeout(2_000)
    await _dump_debug_html(page, "openrouter_privacy_page.html", debug_dir)

    # Dismiss survey popup nếu có (xuất hiện ngay sau login)
    survey = page.locator("text='Where did you first hear about OpenRouter?'")
    if await survey.is_visible(timeout=2000):
        log_fn("  Survey popup detected, dismissing...")
        await page.locator("text='Other / Not sure'").click()
        await page.wait_for_timeout(500)
        await page.locator("button:has-text('Continue')").click()
        await page.wait_for_timeout(1500)
        log_fn("  Survey dismissed")

    # "You're all set!" popup xuất hiện sau survey — đóng lại rồi để step 8 tạo key
    allset = page.locator("text=\"You're all set!\"")
    if await allset.is_visible(timeout=2000):
        log_fn("  'You're all set!' popup detected, closing with Escape...")
        await page.keyboard.press("Escape")
        await page.wait_for_timeout(500)

    toggles = page.locator('button[role="switch"]')
    count = await toggles.count()
    log_fn(f"  Found {count} toggles on privacy page")

    for i in range(count):
        toggle = toggles.nth(i)
        state = await toggle.get_attribute("data-state")
        label = await toggle.get_attribute("aria-label") or f"toggle-{i}"
        # Skip ZDR — chỉ bật những toggle liên quan đến training/logging/discount
        if "zdr" in label.lower() or "zero data retention" in label.lower():
            log_fn(f"  Skipping ZDR toggle: {label}")
            continue
        if state != "checked":
            log_fn(f"  Enabling: {label}")
            await toggle.click()
            await page.wait_for_timeout(1500)
        else:
            log_fn(f"  Already enabled: {label}")

    await _dump_debug_html(page, "openrouter_privacy_done.html", debug_dir)


async def _create_api_key(page: Any, timeout_ms: int, log_fn: LogFn, debug_dir: Path, or_cfg: Any = None) -> str:
    try:
        _keys_url = or_cfg.keys_settings_url if or_cfg else "https://openrouter.ai/settings/keys"
        log_fn("  Navigating to /settings/keys...")
        await page.goto(_keys_url, timeout=timeout_ms * 2, wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)
        log_fn(f"  Keys page URL: {page.url}")
        await _dump_debug_html(page, "openrouter_keys_page.html", debug_dir)

        try:
            survey = page.locator("text='Where did you first hear about OpenRouter?'")
            if await survey.is_visible(timeout=2000):
                log_fn("  Survey popup detected, dismissing...")
                await page.locator("text='Other / Not sure'").click()
                await page.wait_for_timeout(500)
                await page.locator("button:has-text('Continue')").click()
                await page.wait_for_timeout(1500)
                log_fn("  Survey dismissed")
            else:
                log_fn("  No survey popup")
        except Exception:  # noqa: BLE001 - best-effort UI action
            log_fn("  No survey popup")

        log_fn("  Clicking Create button...")
        await page.evaluate(
            "() => { const btn = [...document.querySelectorAll('button')]"
            ".find(b => b.textContent.trim() === 'Create' && !b.disabled);"
            " if (btn) btn.click(); }"
        )
        log_fn("  Waiting for key name input...")
        await page.wait_for_selector("input[placeholder*='Chatbot']", timeout=8000)
        await page.wait_for_timeout(300)
        log_fn("  Filling key name: 'default'")
        await page.locator("input[placeholder*='Chatbot']").first.fill("default")
        await page.wait_for_timeout(400)

        log_fn("  Clicking Create (confirm)...")
        await page.evaluate(
            "() => { const creates = [...document.querySelectorAll('button')]"
            ".filter(b => b.textContent.trim() === 'Create' && !b.disabled);"
            " if (creates.length) creates[creates.length - 1].click(); }"
        )

        log_fn("  Polling for API key (up to 30s)...")
        for tick in range(60):
            await page.wait_for_timeout(500)
            text = await page.evaluate(
                "() => {"
                " const parts = [document.body.innerText];"
                " document.querySelectorAll('input,textarea,code').forEach(el => {"
                "   const v = el.value || el.textContent || '';"
                "   if (v) parts.push(v);"
                " });"
                " return parts.join('\\n');"
                "}"
            )
            found = re.findall(or_cfg.api_key_regex, text)
            if found:
                log_fn(f"  API key found after {(tick+1)*0.5:.1f}s: {found[0][:20]}...")
                return found[0]
            if tick % 10 == 9:
                log_fn(f"  Still polling... ({(tick+1)*0.5:.0f}s)")

        await _dump_debug_html(page, "openrouter_apikey.html", debug_dir)
        raise RuntimeError("OpenRouter API key not found on page after creation")

    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError(f"API key creation failed: {exc}") from exc


# -- Main flow ------------------------------------------------------------

async def _signup_flow(
    page: Any,
    browser: Any,
    mailbox: Mailbox,
    email: str,
    password: str,
    cfg: AppConfig,
    log_fn: LogFn,
) -> AccountRecord:
    t = cfg.timeouts
    or_cfg = cfg.openrouter
    debug_dir = cfg.base_dir / "debug"

    log_fn(f"\n[1/8] Opening {or_cfg.signup_url}...")
    await page.goto(or_cfg.signup_url, timeout=t.page_load * 2, wait_until="domcontentloaded")
    await page.wait_for_timeout(2000)
    await _dump_debug_html(page, "or_01_loaded.html", debug_dir)

    log_fn("\n[2/8] Filling form...")
    await _fill_signup_form(page, email, password)
    await _dump_debug_html(page, "or_02_filled.html", debug_dir)

    log_fn("\n[3/8] Clicking Continue...")
    await _click_primary_button(page)
    await page.wait_for_timeout(500)
    await _dump_debug_html(page, "or_03_after_continue.html", debug_dir)
    await _dump_frames(page, log_fn)

    log_fn("\n[4/8] Clicking Turnstile checkbox...")
    await _solve_turnstile_real(page, log_fn, debug_dir)

    log_fn("\n[5/8] Submitting form...")
    await _wait_and_submit(page, log_fn, debug_dir)
    log_fn("  Verification page reached")

    log_fn(f"\n[6/8] Waiting for magic link (up to {t.email_wait}s)...")
    link = await _fetch_magic_link(mailbox, t.email_wait, log_fn=log_fn)
    log_fn(f"  Link: {link[:80]}...")
    await _navigate_magic_link(page, link, t.page_load, log_fn, debug_dir)
    log_fn(f"  Logged in -> {page.url}")

    log_fn("\n[7/8] Enabling privacy options...")
    await _enable_privacy_options(page, t.page_load, log_fn, debug_dir, or_cfg)

    log_fn("\n[8/8] Creating API key...")
    api_key = await _create_api_key(page, t.page_load, log_fn, cfg.base_dir / "debug", or_cfg)

    return AccountRecord(
        service="OPENROUTER",
        email=email,
        password=password,
        api_key=api_key,
    )
