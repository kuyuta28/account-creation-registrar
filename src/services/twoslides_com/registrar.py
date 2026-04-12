"""
services/twoslides/registrar.py — 2slides.com account registration flow.

Flow:
  1. Create temp mailbox
  2. Navigate to https://2slides.com/login
  3. Fill email → click Continue
  4. Wait for OTP email → extract 6-digit code
  5. Fill OTP → click Continue
  6. Wait for dashboard
  7. Create API key via /api page
  8. Persist AccountRecord
"""
from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path

from playwright.async_api import Page

from ...config.settings import AppConfig
from common.browser import open_browser
from common.page_utils import dump_debug_html as _dump_debug
from src.core.storage import AccountRecord
from ...mail.client import Mailbox, create_mailbox, wait_for_message
from ..protocols import LogFn, SaveFn
from .api_key import create_api_key, get_credits_via_page

_LOG = logging.getLogger(__name__)


async def register_twoslides(
    cfg: AppConfig,
    log_fn: LogFn,
    save_fn: SaveFn,
) -> AccountRecord | None:
    max_attempts = cfg.register.max_attempts
    for attempt in range(1, max_attempts + 1):
        _all = cfg.mail.providers_for("2slides")
        _testmail = tuple(p for p in _all if "testmail" in p)
        mailbox = await create_mailbox(_testmail or _all, log_fn=log_fn)
        email = mailbox.email
        if attempt > 1:
            log_fn(f"\n🔄 Retry {attempt}/{max_attempts}")
        log_fn(f"📧 Email: {email}")
        log_fn("-" * 50)

        try:
            async with open_browser(cfg) as browser:
                page = await browser.new_page()
                record = await _run(page, mailbox, email, cfg, log_fn)
                if record:
                    await asyncio.to_thread(save_fn, record)
                    log_fn("💾 Saved to DB")
                return record
        except RuntimeError as exc:
            log_fn(f"\n⚠️  {exc}")
            if attempt < max_attempts:
                log_fn("  → Starting over with a fresh email...")
        except Exception:
            _LOG.exception("Unexpected error in twoslides registrar")
            raise

    log_fn("\n❌ Failed after 3 attempts")
    return None


async def _run(page: Page, mailbox: Mailbox, email: str, cfg: AppConfig, log_fn: LogFn) -> AccountRecord | None:
    svc = cfg.twoslides
    t = cfg.timeouts
    debug_dir = cfg.base_dir / "debug"

    log_fn(f"\n[1/4] Opening 2slides login ({svc.login_url})...")
    await page.goto(svc.login_url, timeout=t.page_load * 4)
    await page.wait_for_load_state("domcontentloaded", timeout=t.page_load)
    await page.wait_for_timeout(t.nav_delay)
    await _dump_debug(page, "2slides_01_login.html", debug_dir)

    log_fn(f"\n[2/4] Filling email: {email}")
    await _fill_email(page, email, log_fn)

    # Click Turnstile captcha before send
    await _click_turnstile(page, log_fn, debug_dir)

    await _click_send_otp(page, log_fn)
    await page.wait_for_timeout(svc.post_submit_wait_ms)
    await _dump_debug(page, "2slides_02_after_email.html", debug_dir)

    # Click Turnstile captcha again after page refresh (2slides requires 2nd captcha)
    await _click_turnstile(page, log_fn, debug_dir)

    log_fn(f"\n[3/4] Waiting for OTP email (up to {svc.otp_wait_sec}s)...")
    msg = await wait_for_message(mailbox, from_contains="2slides", timeout=svc.otp_wait_sec, poll_interval=svc.otp_poll_interval, log_fn=log_fn)
    if not msg:
        log_fn("  No mail from '2slides', polling all mail...")
        msg = await wait_for_message(mailbox, timeout=30, poll_interval=svc.otp_poll_interval, log_fn=log_fn)
    if not msg:
        raise RuntimeError("2slides OTP email not received within timeout")

    otp = _extract_otp(msg)
    if not otp:
        raise RuntimeError(f"2slides email arrived but no 6-digit OTP found. Body: {msg.get('body', '')[:200]}")
    log_fn(f"  OTP: {otp}")

    await _fill_otp(page, otp, log_fn)
    await _click_submit_otp(page, log_fn)
    await page.wait_for_timeout(svc.post_submit_wait_ms * 2)
    await _dump_debug(page, "2slides_03_after_otp.html", debug_dir)

    log_fn("\n[4/4] Waiting for 2slides dashboard...")
    await _wait_for_dashboard(page, svc.app_url_contains, t.page_load, log_fn)
    await _dump_debug(page, "2slides_04_dashboard.html", debug_dir)
    log_fn(f"  ✅ Logged in. URL: {page.url}")

    api_key = await create_api_key(page, log_fn, cfg)

    credits = 0
    try:
        credits = await get_credits_via_page(page, log_fn)
    except Exception as exc:  # noqa: BLE001 - best-effort UI action - log and continue
        log_fn(f"  ⚠️ Credits check failed: {exc}")

    return AccountRecord(service="2SLIDES", email=email, password="", api_key=api_key, credits=credits)


# ── pure helpers ──────────────────────────────────────────────────────────────

async def _click_turnstile(page: Page, log_fn: LogFn, debug_dir: Path) -> None:
    """Click Cloudflare Turnstile captcha checkbox."""
    log_fn("  Waiting for Turnstile...")
    await page.wait_for_timeout(2_000)

    # Find CF challenge iframe
    cf_frames = [f for f in page.frames if "challenges.cloudflare.com" in f.url]
    if not cf_frames:
        log_fn("  [WARN] Turnstile frame not found — skipping")
        return

    cf_frame = cf_frames[0]
    log_fn(f"  Found Turnstile frame: {cf_frame.url[:60]}...")
    await _dump_debug(page, "2slides_turnstile_before.html", debug_dir)

    # Click on the checkbox area (left side of Turnstile widget)
    for attempt in range(3):
        try:
            # Get iframe bounding box and click on left side (checkbox position)
            iframe_el = await cf_frame.frame_element()
            box = await iframe_el.bounding_box()
            if box:
                # Click at left-center of iframe (checkbox is on the left)
                x = box['x'] + 30  # 30px from left edge
                y = box['y'] + box['height'] / 2
                await page.mouse.click(x, y)
                log_fn(f"  Turnstile clicked at ({x:.0f}, {y:.0f}) (attempt {attempt+1})")
            else:
                await cf_frame.locator("body").click(timeout=5_000)
                log_fn(f"  Turnstile clicked (attempt {attempt+1})")
            await page.wait_for_timeout(2_000)
            await _dump_debug(page, f"2slides_turnstile_after_{attempt+1}.html", debug_dir)
            break
        except Exception as e:  # noqa: BLE001 — best-effort captcha UI action: retry is valid for timing issues
            log_fn(f"  Turnstile click attempt {attempt+1} failed: {str(e)[:60]}")
            await page.wait_for_timeout(2_000)


async def _fill_email(page: Page, email: str, log_fn: LogFn) -> None:
    selectors = [
        "input[type='email']",
        "input[name='email']",
        "input[placeholder*='email' i]",
        "input[placeholder*='mail' i]",
        "input[type='text']",
    ]
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            if await loc.is_visible():
                await loc.fill(email)
                log_fn(f"  Filled email via '{sel}'")
                return
        except Exception:  # noqa: BLE001 — best-effort optional UI action
            pass
    raise RuntimeError("Could not find email input on 2slides login page")


async def _click_send_otp(page: Page, log_fn: LogFn) -> None:
    """Click 'Send' button để gửi OTP — KHÔNG click Google hay Continue."""
    clicked = await page.evaluate("""() => {
        for (const btn of document.querySelectorAll('button')) {
            const t = (btn.innerText || '').trim().toLowerCase();
            if (t === 'send' || t === 'send code') {
                btn.click();
                return t;
            }
        }
        return null;
    }""")
    if clicked:
        log_fn(f"  Clicked '{clicked}'")
    else:
        log_fn("  ⚠️ No 'Send' button found — pressing Enter")
        await page.keyboard.press("Enter")


async def _click_submit_otp(page: Page, log_fn: LogFn) -> None:
    """Click 'Continue →' button để submit OTP — skip Google button."""
    clicked = await page.evaluate("""() => {
        for (const btn of document.querySelectorAll('button')) {
            const t = (btn.innerText || '').trim().toLowerCase();
            if (t.includes('google')) continue;
            if (t.includes('continue') || t.includes('submit') || t.includes('sign in') || t.includes('login') || t.includes('verify')) {
                btn.click();
                return t;
            }
        }
        return null;
    }""")
    if clicked:
        log_fn(f"  Clicked '{clicked}'")
    else:
        log_fn("  ⚠️ No 'Continue' button found — pressing Enter")
        await page.keyboard.press("Enter")


async def _fill_otp(page: Page, otp: str, log_fn: LogFn) -> None:
    # Try OTP input boxes (may be individual digit inputs or single input)
    # Single input approach
    selectors = [
        "input[type='number']",
        "input[placeholder*='code' i]",
        "input[placeholder*='otp' i]",
        "input[placeholder*='verif' i]",
        "input[autocomplete='one-time-code']",
        "input[name='code']",
        "input[name='otp']",
    ]
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            if await loc.is_visible():
                await loc.fill(otp)
                log_fn(f"  Filled OTP via '{sel}'")
                return
        except Exception:  # noqa: BLE001 — best-effort optional UI action
            pass

    # Split digit inputs (common pattern: 6 separate <input maxlength=1>)
    digit_inputs = page.locator("input[maxlength='1']")
    if await digit_inputs.count() >= len(otp):
        for i, ch in enumerate(otp):
            await digit_inputs.nth(i).fill(ch)
        log_fn(f"  Filled OTP via {await digit_inputs.count()} individual digit inputs")
        return

    # Generic text fallback
    try:
        inp = page.locator("input[type='text']").first
        if await inp.is_visible():
            await inp.fill(otp)
            log_fn("  Filled OTP via generic text input")
            return
    except Exception:  # noqa: BLE001 — best-effort optional UI action
        pass

    raise RuntimeError("Could not find OTP input on 2slides page")


async def _wait_for_dashboard(page: Page, contains: str, timeout_ms: int, log_fn: LogFn) -> None:
    try:
        await page.wait_for_url(f"**/{contains}/**", timeout=timeout_ms * 2, wait_until="commit")
    except Exception:  # noqa: BLE001 - best-effort optional UI action
        pass
    # Accept any URL that left the /login page
    url = page.url
    if "login" in url.lower():
        # Wait a bit more
        try:
            await page.wait_for_function(
                "() => !window.location.href.includes('login')",
                timeout=timeout_ms,
            )
        except Exception:  # noqa: BLE001 - best-effort optional UI action
            pass
    if "login" in page.url.lower():
        raise RuntimeError(f"Still on login page after OTP submission. URL: {page.url}")


def _extract_otp(msg: dict) -> str | None:
    """Extract 6-digit OTP from email text/body."""
    body: str = msg.get("body", "") or msg.get("text", "") or msg.get("subject", "")
    # 6-digit standalone number
    matches = re.findall(r"\b(\d{6})\b", body)
    return matches[0] if matches else None
