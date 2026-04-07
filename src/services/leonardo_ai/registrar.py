"""
services/leonardo/registrar.py - Leonardo AI registration flow.
"""
from __future__ import annotations

import asyncio
import logging
import random
import re

from playwright.async_api import Page

from ...config.settings import AppConfig
from ...core.browser import open_browser
from ...core.page_utils import dump_debug_html as _dump_debug, safe_text
from ...core.password import generate_password
from ...core.storage import AccountRecord
from ...mail.client import Mailbox, create_mailbox, wait_for_message
from ..protocols import LogFn, SaveFn

_LOG = logging.getLogger(__name__)

_FIRST = [
    "Alex", "Jordan", "Taylor", "Morgan", "Casey", "Riley", "Jamie", "Drew",
    "Avery", "Quinn", "Sam", "Blake", "Cameron", "Dylan", "Emery", "Finley",
]
_LAST = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
    "Wilson", "Moore", "Anderson", "Thomas", "Jackson", "White", "Harris", "Martin",
]


async def register_leonardo(
    cfg: AppConfig,
    log_fn: LogFn,
    save_fn: SaveFn,
) -> AccountRecord | None:
    max_attempts = cfg.register.max_attempts
    for attempt in range(1, max_attempts + 1):
        mailbox = await create_mailbox(cfg.mail.providers_for("leonardo"), log_fn=log_fn)
        email = mailbox.email
        password = generate_password(cfg.register.password_length)
        if attempt > 1:
            log_fn(f"\nRetry {attempt}/{max_attempts}")
        log_fn(f"📧 Email:    {email}")
        log_fn("   Password: ****")
        log_fn("-" * 50)

        try:
            async with open_browser(cfg) as browser:
                page = await browser.new_page()
                record = await _run(page, mailbox, email, password, cfg, log_fn)
                if record:
                    await asyncio.to_thread(save_fn, record)
                    log_fn("💾 Saved to DB")
                return record
        except RuntimeError as exc:
            log_fn(f"\n{exc}")
            if attempt < max_attempts:
                log_fn("  Starting over with a fresh email...")
        except Exception:
            _LOG.exception("Unexpected error in leonardo registrar")
            raise

    log_fn(f"\n❌ Failed after {max_attempts} attempts")
    return None


async def _run(page: Page, mailbox: Mailbox, email: str, password: str, cfg: AppConfig, log_fn: LogFn) -> AccountRecord | None:
    leo = cfg.leonardo
    t = cfg.timeouts
    debug_dir = cfg.base_dir / "debug"
    code: str | None = None
    full_name = _random_full_name()
    step = 0

    log_fn(f"\n[1/?] Opening Leonardo auth page ({leo.login_url})...")
    await page.goto(leo.login_url, timeout=t.page_load * 4)
    await page.wait_for_load_state("domcontentloaded", timeout=t.page_load)
    await page.wait_for_timeout(t.nav_delay)
    await _dump_debug(page, f"leonardo_step_{step:02d}_init.html", debug_dir)
    step += 1

    for state_no in range(45):
        url = page.url
        text = await safe_text(page)
        log_fn(f"  [state {state_no:02d}] {url[:120]}")

        if _is_dashboard(url, leo.app_url_contains):
            log_fn("  Reached Leonardo dashboard")
            await _dump_debug(page, "leonardo_dashboard.html", debug_dir)
            await _dismiss_getting_started(page, log_fn)
            await _dump_debug(page, "leonardo_after_getting_started.html", debug_dir)
            return AccountRecord(service="LEONARDO", email=email, password=password)

        if "verify you are a human" in text.lower():
            await _click_turnstile(page, log_fn)
            await _dump_debug(page, f"leonardo_step_{step:02d}_turnstile.html", debug_dir)
            await _try_continue(page, log_fn)
            await page.wait_for_timeout(leo.post_submit_wait_ms)
            step += 1
            continue

        if await _has_email_input(page):
            await _fill_email(page, email, log_fn)
            await _try_continue(page, log_fn)
            await page.wait_for_timeout(leo.post_submit_wait_ms)
            await _dump_debug(page, f"leonardo_step_{step:02d}_email.html", debug_dir)
            step += 1
            continue

        if await _can_choose_email_method(page, text):
            await _click_email_method(page, log_fn)
            await page.wait_for_timeout(t.short_delay)
            await _dump_debug(page, f"leonardo_step_{step:02d}_email_method.html", debug_dir)
            step += 1
            continue

        if await _is_code_page(page, text):
            if code is None:
                log_fn("  Waiting for Leonardo verification code email...")
                msg = await wait_for_message(mailbox, from_contains=leo.verification_sender, timeout=leo.otp_wait_sec, poll_interval=leo.otp_poll_interval, log_fn=log_fn)
                if not msg:
                    raise RuntimeError("Leonardo verification email not received within timeout")
                code = _extract_verification_code(msg)
                if not code:
                    raise RuntimeError("Leonardo verification email arrived but no code was found")
                log_fn(f"  Verification code: {code}")
            await _fill_code(page, code, log_fn)
            await page.wait_for_timeout(leo.post_submit_wait_ms)
            await _dump_debug(page, f"leonardo_step_{step:02d}_code.html", debug_dir)
            step += 1
            continue

        if await _has_password_input(page):
            await _fill_password(page, password, log_fn)
            await page.wait_for_timeout(leo.post_submit_wait_ms)
            await _dump_debug(page, f"leonardo_step_{step:02d}_password.html", debug_dir)
            step += 1
            continue

        if await _has_name_input(page, text):
            await _fill_name(page, full_name, log_fn)
            await page.wait_for_timeout(leo.post_submit_wait_ms)
            await _dump_debug(page, f"leonardo_step_{step:02d}_name.html", debug_dir)
            step += 1
            continue

        if await _try_continue(page, log_fn):
            await page.wait_for_timeout(t.short_delay)
        else:
            await page.wait_for_timeout(t.nav_delay)
        await _dump_debug(page, f"leonardo_step_{step:02d}_unknown.html", debug_dir)
        step += 1

    raise RuntimeError("Leonardo signup did not reach the dashboard in time")




def _random_full_name() -> str:
    return f"{random.choice(_FIRST)} {random.choice(_LAST)}"


async def _dismiss_getting_started(page: Page, log_fn: LogFn) -> None:
    """Đợi popup 'Getting Started', tick checkbox, click 'Let's Go'."""
    log_fn("  [POPUP] Checking for 'Getting Started' popup...")

    # Đợi popup xuất hiện tối đa 8s
    try:
        dialog = page.locator('[role="dialog"]').filter(has_text="Getting Started")
        await dialog.wait_for(state="visible", timeout=8_000)
    except Exception:  # noqa: BLE001 - best-effort UI action - log and continue
        log_fn("  [POPUP] 'Getting Started' popup not found — skipping")
        return

    log_fn("  [POPUP] Popup found. Ticking checkbox...")

    # Tick checkbox bên trong popup
    checkbox = dialog.locator('[role="checkbox"], input[type="checkbox"]').first
    if await checkbox.count() == 0:
        raise RuntimeError("Getting Started popup: checkbox not found")
    is_checked = await checkbox.get_attribute("aria-checked") == "true" or await checkbox.is_checked()
    if not is_checked:
        await checkbox.click()
        await page.wait_for_timeout(500)
    log_fn("  [POPUP] Checkbox ticked. Clicking 'Let's Go'...")

    # Click "Let's Go" bên trong popup
    btn = dialog.get_by_role("button").filter(has_text="Let's Go")
    if await btn.count() == 0:
        raise RuntimeError("Getting Started popup: 'Let's Go' button not found")
    await btn.first.click()
    await page.wait_for_timeout(2000)
    log_fn("  [POPUP] Dismissed 'Getting Started' popup")


def _is_dashboard(url: str, app_url_contains: str) -> bool:
    lowered = url.lower()
    return app_url_contains in lowered and "/auth/" not in lowered and "/login" not in lowered


async def _can_choose_email_method(page: Page, text: str) -> bool:
    if await _has_email_input(page):
        return False
    if "continue with email" in text.lower():
        return True
    try:
        return await page.get_by_role("button", name="Continue with Email", exact=False).count() > 0
    except Exception:  # noqa: BLE001 - best-effort UI probe - returns safe default
        return False


async def _click_email_method(page: Page, log_fn: LogFn) -> bool:
    try:
        await page.get_by_role("button", name="Continue with Email", exact=False).click(timeout=5000)
        log_fn("  Clicked 'Continue with Email'")
        return True
    except Exception:  # noqa: BLE001 - best-effort UI probe - returns safe default
        return False


async def _has_email_input(page: Page) -> bool:
    for selector in (
        "input[type='email']",
        "input[name='email']",
        "input[autocomplete='email']",
    ):
        try:
            locator = page.locator(selector)
            if await locator.count() > 0 and await locator.first.is_visible():
                return True
        except Exception:  # noqa: BLE001 - best-effort optional UI action
            pass
    return False


async def _fill_email(page: Page, email: str, log_fn: LogFn) -> None:
    for selector in (
        "input[type='email']",
        "input[name='email']",
        "input[autocomplete='email']",
    ):
        try:
            locator = page.locator(selector)
            if await locator.count() > 0 and await locator.first.is_visible():
                if (await locator.first.input_value() or "").strip().lower() != email.lower():
                    await locator.first.fill(email)
                    log_fn(f"  Filled email ({selector})")
                return
        except Exception:  # noqa: BLE001 — best-effort optional UI action
            pass
    log_fn("  No Leonardo email input found")


async def _click_turnstile(page: Page, log_fn: LogFn) -> None:
    """Camoufox bypass fingerprint — chỉ cần click checkbox CF một lần là xong."""
    cf_frames = [f for f in page.frames if "challenges.cloudflare.com" in f.url]
    if not cf_frames:
        log_fn("  [WARN] CF Turnstile frame not found")
        return
    try:
        await cf_frames[0].locator("body").click(position={"x": 20, "y": 20}, timeout=5000)
        log_fn("  Clicked Turnstile checkbox")
        await page.wait_for_timeout(1500)
    except Exception as exc:  # noqa: BLE001 - best-effort UI action - log and continue
        log_fn(f"  Turnstile click failed: {str(exc)[:80]}")


async def _is_code_page(page: Page, text: str) -> bool:
    lowered = text.lower()
    if any(phrase in lowered for phrase in ("verification code", "enter the code", "6-digit", "6 digit", "check your email")):
        return True
    try:
        if await page.locator("input[autocomplete='one-time-code']").count() > 0:
            return True
        if await page.locator("input[maxlength='1']").count() >= 6:
            return True
    except Exception:  # noqa: BLE001 - best-effort optional UI action
        pass
    return False


def _extract_verification_code(message: dict) -> str | None:
    for source in (message.get("subject", ""), message.get("intro", ""), message.get("body", "")):
        match = re.search(r"\b(\d{6,8})\b", source)
        if match:
            return match.group(1)
    return None


async def _fill_code(page: Page, code: str, log_fn: LogFn) -> None:
    for selector in (
        "input[autocomplete='one-time-code']",
        "input[name='code']",
        "input[id='code']",
        "input[data-slot='input-group-control']",
    ):
        try:
            locator = page.locator(selector)
            if await locator.count() > 0 and await locator.first.is_visible():
                await locator.first.fill(code)
                await page.keyboard.press("Enter")
                log_fn("  Filled verification code (single input)")
                return
        except Exception:  # noqa: BLE001 — best-effort optional UI action
            pass
    try:
        boxes = page.locator("input[maxlength='1']")
        if await boxes.count() >= len(code):
            for index, digit in enumerate(code):
                await boxes.nth(index).fill(digit)
                await page.wait_for_timeout(60)
            await _try_continue(page, log_fn)
            log_fn("  Filled verification code (digit boxes)")
            return
    except Exception:  # noqa: BLE001 — best-effort optional UI action
        pass
    log_fn("  Could not find Leonardo verification code inputs")


async def _has_password_input(page: Page) -> bool:
    try:
        locator = page.locator("input[type='password']")
        return await locator.count() > 0 and await locator.first.is_visible()
    except Exception:  # noqa: BLE001 - best-effort UI probe - returns safe default
        return False


async def _fill_password(page: Page, password: str, log_fn: LogFn) -> None:
    try:
        fields = page.locator("input[type='password']")
        count = await fields.count()
        for index in range(count):
            field = fields.nth(index)
            if await field.is_visible():
                await field.fill(password)
        log_fn("  Filled password fields")
    except Exception as exc:  # noqa: BLE001 - best-effort UI action - log and continue
        log_fn(f"  Password fill failed: {exc}")
    await _try_continue(page, log_fn)


async def _has_name_input(page: Page, text: str) -> bool:
    lowered = text.lower()
    if any(phrase in lowered for phrase in ("full name", "your name", "display name")):
        return True
    for selector in (
        "input[name='name']",
        "input[autocomplete='name']",
        "input[placeholder*='name' i]",
    ):
        try:
            locator = page.locator(selector)
            if await locator.count() > 0 and await locator.first.is_visible():
                return True
        except Exception:  # noqa: BLE001 - best-effort optional UI action
            pass
    return False


async def _fill_name(page: Page, full_name: str, log_fn: LogFn) -> None:
    for selector in (
        "input[name='name']",
        "input[autocomplete='name']",
        "input[placeholder*='full name' i]",
        "input[placeholder*='name' i]",
    ):
        try:
            locator = page.locator(selector)
            if await locator.count() > 0 and await locator.first.is_visible():
                await locator.first.fill(full_name)
                log_fn(f"  Filled name: {full_name}")
                await _try_continue(page, log_fn)
                return
        except Exception:  # noqa: BLE001 — best-effort optional UI action
            pass
    log_fn("  No Leonardo name input found")


async def _try_continue(page: Page, log_fn: LogFn) -> bool:
    for label in ("Continue", "Verify", "Submit", "Create account", "Finish", "Get started"):
        try:
            buttons = page.get_by_role("button", name=label, exact=False)
            for index in range(await buttons.count()):
                button = buttons.nth(index)
                if await button.is_visible() and await button.is_enabled():
                    await button.click()
                    log_fn(f"  Clicked '{label}'")
                    return True
        except Exception:  # noqa: BLE001 — best-effort optional UI action
            pass
    return False
