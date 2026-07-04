"""
services/proton/registrar.py — Proton Mail registration flow.
Implements Registrar protocol (FP callable).
Dependencies injected via constructor (Dependency Inversion).
"""
from __future__ import annotations

import asyncio
import logging

from ...config.settings import AppConfig
from common.browser import open_browser
from common.password import generate_password, generate_username
from src.core.account_record import AccountRecord
from ..protocols import LogFn, SaveFn

_LOG = logging.getLogger(__name__)


async def register_proton(
    cfg: AppConfig,
    log_fn: LogFn,
    save_fn: SaveFn,
) -> AccountRecord | None:
    max_attempts = cfg.register.max_attempts
    for attempt in range(1, max_attempts + 1):
        username = generate_username(17)
        password = generate_password(cfg.register.password_length)

        if attempt > 1:
            log_fn(f"\n🔄 Retry {attempt}/{max_attempts}")
        log_fn(f"Username: {username}")
        log_fn("Password: ****")
        log_fn("-" * 50)

        try:
            async with open_browser(cfg) as browser:
                page = await browser.new_page()
                return await _run(page, username, password, cfg, log_fn, save_fn)
        except RuntimeError as e:
            log_fn(f"\n⚠️  {e}")
            if attempt < max_attempts:
                log_fn("  → Starting over...")
        except Exception:
            _LOG.exception("Unexpected error in proton registrar")
            raise

    log_fn(f"\n❌ Failed after {max_attempts} attempts")
    return None


async def _run(page, username: str, password: str, cfg: AppConfig, log_fn: LogFn, save_fn: SaveFn) -> AccountRecord | None:
    p = cfg.proton
    log_fn("\n[1/6] Opening Proton signup...")
    await page.goto(p.signup_url, timeout=cfg.timeouts.page_load * p.signup_page_load_multiplier)
    await page.wait_for_load_state("domcontentloaded", timeout=cfg.timeouts.page_load)

    log_fn("\n[2/6] Filling username...")
    frame = await _find_signup_iframe(page, cfg.timeouts.page_load * p.signup_page_load_multiplier, p)
    if not frame:
        raise RuntimeError("Cannot find signup iframe")

    for attempt in range(p.username_max_attempts):
        if attempt > 0:
            username = generate_username(17)
            log_fn(f"  Retry {attempt}: {username}")
        if await _fill_username(frame, username, p):
            log_fn(f"  ✓ Username '{username}' available")
            break
    else:
        raise RuntimeError(f"Could not find available username after {p.username_max_attempts} attempts")

    log_fn("\n[3/6] Filling password...")
    await page.locator(p.password_selector).fill(password)
    confirm = page.locator(p.password_confirm_selector)
    await confirm.wait_for(state="visible", timeout=cfg.timeouts.page_load)
    await confirm.fill(password)

    log_fn("\n[4/6] Submitting...")
    submit = page.locator(p.submit_selector)
    if await submit.is_visible():
        await submit.click()
    else:
        await page.get_by_text(p.create_account_button_text).click()

    record = AccountRecord(service="PROTON", email=f"{username}@protonmail.com", password=password)
    await asyncio.to_thread(save_fn, record)
    log_fn("💾 Saved to DB")

    log_fn("\n[5/6] 🧩 Solve CAPTCHA in browser!")
    log_fn("=" * 50)

    log_fn("\n[6/6] Waiting for dashboard...")
    await _wait_for_inbox(page, cfg, log_fn)

    final_url = page.url.lower()
    if "mail" not in final_url:
        log_fn(f"✗ Did not reach dashboard. URL: {final_url}")
        return None

    return record


async def _wait_for_inbox(page, cfg: AppConfig, log_fn: LogFn) -> None:
    max_polls = (cfg.timeouts.email_wait * 1000) // cfg.timeouts.nav_delay
    for _ in range(max_polls):
        await page.wait_for_timeout(cfg.timeouts.nav_delay)
        await _dismiss_popups(page, cfg.proton)
        url = page.url.lower()
        if "mail" in url and ("inbox" in url or "all-mail" in url):
            log_fn("  ✓ Reached mail dashboard!")
            return


# ── pure helpers ──────────────────────────────────────────────────────────────

async def _find_signup_iframe(page, timeout: int, p) :
    """Return the signup iframe frame or None."""
    await page.wait_for_selector(p.signup_iframe_selector, state="attached", timeout=timeout)
    for frame in page.frames:
        if p.signup_iframe_url_contains in frame.url or await frame.locator(p.username_selector).count() > 0:
            return frame
    return None


async def _fill_username(frame, username: str, p) -> bool:
    """Inject username via React-compatible approach. Returns True if no 'already used' error."""
    await frame.evaluate(f"""() => {{
        const input = document.querySelector('{p.username_selector}');
        if (input) {{
            const setter = Object.getOwnPropertyDescriptor(
                window.HTMLInputElement.prototype, 'value'
            ).set;
            setter.call(input, '{username}');
            input.dispatchEvent(new Event('input', {{ bubbles: true }}));
        }}
    }}""")
    try:
        if await frame.locator(f'span:has-text("{p.username_taken_text}")').count() > 0:
            return False
    except Exception as e:  # noqa: BLE001 - best-effort optional UI action
        import logging
        logging.getLogger(__name__).warning("username check error: %s", e)
    return True


async def _dismiss_popups(page, p) -> None:
    for text in p.dismiss_popup_texts:
        try:
            btn = page.get_by_text(text, exact=False)
            if await btn.count() > 0 and await btn.first.is_visible():
                await btn.first.click()
        except Exception:  # noqa: BLE001 — best-effort optional UI action
            pass
