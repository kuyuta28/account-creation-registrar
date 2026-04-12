"""
services/elevenlabs_io/registrar.py — ElevenLabs registration via Google OAuth only.

Flow: inject Google storage_state vào browser context -> "Sign up with Google"
      -> popup thấy Google session -> auto-approve (không cần type email/pass/TOTP)
      -> dashboard -> create API key -> lưu storage_state mới về DB
"""
from __future__ import annotations

import asyncio
import json
import logging

from ...config.settings import AppConfig
from common.browser import open_browser
from common.database import get_mailbox_google_auth_state, save_mailbox_google_auth_state
from src.core.google_oauth import dump_page_html, handle_oauth_popup
from src.core.storage import AccountRecord, db_path
from ...mail.client import Mailbox, create_mailbox
from ..errors import FatalRegistrationError, NoMailboxAvailableError, NoSessionError, RetryableRegistrationError
from ..protocols import LogFn, SaveFn
from .api_key import create_api_key
from .onboarding import handle_onboarding

_LOG = logging.getLogger(__name__)


async def register_elevenlabs(
    cfg: AppConfig,
    log_fn: LogFn,
    save_fn: SaveFn,
) -> AccountRecord | None:
    max_attempts = cfg.register.max_attempts
    for attempt in range(1, max_attempts + 1):
        try:
            providers = cfg.mail.providers_for("elevenlabs")
            mailbox = await create_mailbox(providers, log_fn=log_fn)
        except RuntimeError as e:
            raise NoMailboxAvailableError(str(e)) from e

        if attempt > 1:
            log_fn(f"\n🔄 Retry attempt {attempt}/{max_attempts}")
        log_fn(f"📧 Email: {mailbox.email}")
        log_fn("-" * 50)

        use_session = cfg.elevenlabs.use_google_session

        if use_session:
            # Lấy Google storage_state từ DB — bắt buộc phải có
            state_json = await asyncio.to_thread(
                get_mailbox_google_auth_state, db_path(cfg.base_dir), mailbox.email
            )
            if not state_json:
                raise NoSessionError(
                    f"No Google session found for {mailbox.email} — "
                    "chạy 'Login Google Session' trước để lưu session vào DB"
                )
            log_fn(f"  ✓ Google session loaded ({len(state_json)} bytes)")
        else:
            state_json = None
            log_fn("  ℹ use_google_session=false → login fresh trong popup")

        try:
            async with open_browser(cfg) as browser:
                context = await browser.new_context(
                    **({"storage_state": json.loads(state_json)} if state_json else {})
                )
                page = await context.new_page()
                record = await _run_google_oauth(page, context, mailbox, cfg, log_fn)
                if record:
                    await asyncio.to_thread(save_fn, record)
                    log_fn("💾 Saved to DB")
                return record
        except FatalRegistrationError:
            raise
        except (RuntimeError, RetryableRegistrationError) as e:
            log_fn(f"\n⚠️  {e}")
            raise  # no retry — fail fast for testing
        except Exception:
            _LOG.exception("Unexpected error in elevenlabs registrar")
            raise

    log_fn(f"\n❌ Failed after {max_attempts} attempts")
    return None


async def _run_google_oauth(page, context, mailbox: Mailbox, cfg: AppConfig, log_fn: LogFn) -> AccountRecord | None:
    t = cfg.timeouts

    log_fn(f"\n[1/4] Opening ElevenLabs signup ({cfg.elevenlabs.signup_url})...")
    await page.goto(cfg.elevenlabs.signup_url, timeout=t.page_load * 4)
    await page.wait_for_load_state("domcontentloaded")
    await page.wait_for_timeout(t.short_delay)

    log_fn("\n[2/4] Clicking Sign up with Google...")
    google_btn = page.get_by_role("button", name="Sign up with Google")
    await google_btn.wait_for(state="visible", timeout=t.page_load * 2)

    async with page.expect_popup() as popup_info:
        await google_btn.click()

    popup = await popup_info.value
    log_fn(f"  → Popup opened: {popup.url}")

    log_fn("\n[3/4] Waiting for Google OAuth...")
    await handle_oauth_popup(
        popup,
        email=mailbox.email,
        password=mailbox.password,
        totp_secret=mailbox.totp_secret,
        db_path=db_path(cfg.base_dir),
        log_fn=log_fn,
    )
    log_fn("  ✓ OAuth popup handled")

    # Lưu updated storage_state về DB (cookies có thể đã refresh)
    try:
        new_state = await context.storage_state()
        await asyncio.to_thread(
            save_mailbox_google_auth_state,
            db_path(cfg.base_dir),
            mailbox.email,
            json.dumps(new_state),
        )
        log_fn("  ✓ Google session refreshed in DB")
    except Exception:  # noqa: BLE001 - best-effort session refresh - log and continue
        _LOG.warning("Failed to save updated Google storage_state", exc_info=True)

    log_fn("  ⏳ Waiting for ElevenLabs to process OAuth...")
    await _wait_for_dashboard_oauth(page, cfg, log_fn)

    log_fn("\n[4/4] Creating API key...")
    api_key = await create_api_key(page, log_fn, cfg)

    return AccountRecord(service="ELEVENLABS", email=mailbox.email, password=mailbox.password, api_key=api_key)


async def _wait_for_dashboard_oauth(page, cfg: AppConfig, log_fn: LogFn) -> None:
    t = cfg.timeouts
    max_polls = (t.email_wait * 1000) // t.nav_delay
    log_fn(f"  [dashboard] polling up to {max_polls} times (interval={t.nav_delay}ms)...")

    # Gắn console listener để catch JS errors trên main page
    for i in range(max_polls):
        await page.wait_for_timeout(t.nav_delay)
        url = page.url
        log_fn(f"  [dashboard] poll {i+1}/{max_polls}: {url}")

        if "onboarding" in url:
            log_fn("  → Onboarding detected...")
            await handle_onboarding(page, log_fn, cfg)
            continue

        if _is_dashboard(url, cfg):
            log_fn("  ✓ Reached dashboard!")
            return

        # Dump HTML ở poll đầu tiên và poll cuối để debug
        if i == 0 or i == max_polls - 1:
            await dump_page_html(page, f"signup_poll_{i+1}", log_fn)

    raise RuntimeError(
        f"Timed out waiting for Google OAuth to complete after {max_polls} polls — "
        f"xem debug/page_signup_poll_*.html để biết trạng thái trang"
    )


def _is_dashboard(url: str, cfg: AppConfig) -> bool:
    base = cfg.elevenlabs.app_base_url
    return base in url and "sign-up" not in url and "sign-in" not in url and "verify" not in url