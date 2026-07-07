"""services/elevenlabs_io/flow.py - ElevenLabs signup automation recipe.

Pure browser automation — nhận `page`/`context` từ gateway task, không mở browser.
`context` đã inject Google storage_state (nếu use_session). Entrypoint
`_signup_flow` chạy Google OAuth → dashboard → create API key.
"""
from __future__ import annotations

import json
import logging

from ...config.settings import AppConfig
from common.database._async import save_mailbox_google_auth_state_async
from common.database._engine import get_async_session
from src.core.google_oauth import dump_page_html, handle_oauth_popup
from src.core.account_record import AccountRecord
from ...mail.client import Mailbox
from ..protocols import LogFn
from .api_key import create_api_key
from .onboarding import handle_onboarding

_LOG = logging.getLogger(__name__)


async def _signup_flow(
    page,
    context,
    mailbox: Mailbox,
    cfg: AppConfig,
    log_fn: LogFn,
) -> AccountRecord:
    """Pure automation: ElevenLabs Google OAuth + API key. Browser/context do caller mở."""
    return await _run_google_oauth(page, context, mailbox, cfg, log_fn)


async def _run_google_oauth(page, context, mailbox: Mailbox, cfg: AppConfig, log_fn: LogFn) -> AccountRecord:
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
        log_fn=log_fn,
    )
    log_fn("  ✓ OAuth popup handled")

    # Lưu updated storage_state về DB (cookies có thể đã refresh)
    try:
        new_state = await context.storage_state()
        async with get_async_session() as session:
            await save_mailbox_google_auth_state_async(
                session,
                mailbox.email,
                json.dumps(new_state),
            )
        log_fn("  ✓ Google session refreshed in DB")
    except Exception:  # noqa: BLE001 - best-effort session refresh
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

        if i == 0 or i == max_polls - 1:
            await dump_page_html(page, f"signup_poll_{i+1}", log_fn)

    raise RuntimeError(
        f"Timed out waiting for Google OAuth to complete after {max_polls} polls — "
        f"xem debug/page_signup_poll_*.html để biết trạng thái trang"
    )


def _is_dashboard(url: str, cfg: AppConfig) -> bool:
    base = cfg.elevenlabs.app_base_url
    return base in url and "sign-up" not in url and "sign-in" not in url and "verify" not in url
