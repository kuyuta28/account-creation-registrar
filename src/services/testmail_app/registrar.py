"""
registrar.py — testmail.app account registration (FP module).

Flow:
  1. create_mailbox() từ mail.tm để nhận verification code
  2. Playwright → signup form tại https://testmail.app/signup/
  3. Wait verification code email → fill #code → click Confirm
  4. Navigate /console/ → extract namespace + API key
  5. save_fn(record) — api_key = "testmail.app:NS:KEY" (lưu vào DB)
     Settings.py tự load TESTMAIL keys từ DB khi khởi động.

Public API:
  register_testmail(cfg, log_fn, save_fn) → Optional[AccountRecord]
"""
from __future__ import annotations

import asyncio
import html as _html_module
import logging
import random
import re
import string
from pathlib import Path
from playwright.async_api import Page

from ...config.settings import AppConfig
from common.browser import open_browser
from common.database import upsert_mail_provider
from common.page_utils import dump_debug_html as _dump_debug
from src.core.storage import AccountRecord
from ...mail.client import Mailbox, create_mailbox, wait_for_message
from ..protocols import LogFn, SaveFn

_LOG = logging.getLogger(__name__)

# ── Config-driven URLs ──────────────────────────────────────────────────

def _signup_url(cfg: AppConfig) -> str:
    return cfg.testmail.signup_url

def _console_url() -> str:
    from ...config.settings import load_config
    return load_config().testmail.console_url


# ── Pure helpers ──────────────────────────────────────────────────────

def _random_name() -> tuple[str, str]:
    FIRST_NAMES = ["Alex", "Jordan", "Casey", "Riley", "Morgan", "Taylor", "Quinn", "Avery"]
    first = random.choice(FIRST_NAMES)
    last = "".join(random.choices(string.ascii_lowercase, k=6)).capitalize()
    return first, last


def _strip_html(text: str) -> str:
    """Strip HTML tags và decode entities để lấy plain text."""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return _html_module.unescape(text).strip()


def _extract_verification_code(body: str) -> str | None:
    """Extract verification code từ email body.
    Format: '----------\\nCODE\\n----------' (alphanumeric, 4–12 chars)
    Tự động strip HTML nếu body là HTML.
    """
    # Strip HTML nếu cần — tránh match 'DOCTYPE', 'SCRIPT', v.v.
    if "<" in body and ">" in body:
        body = _strip_html(body)

    m = re.search(r"-{5,}\s*\n([A-Z0-9]{4,12})\n\s*-{5,}", body)
    if m:
        return m.group(1).strip()
    # fallback: standalone 6–8 char alphanumeric (không phải từ HTML)
    m = re.search(r"\b([A-Z0-9]{6,8})\b", body)
    return m.group(1) if m else None


def _extract_credentials_from_quickstart(text: str) -> tuple[str | None, str | None]:
    """Extract namespace + API key from Quickstart API URL.
    Pattern: apikey=UUID&(amp;)namespace=NS
    Returns (namespace, api_key).
    """
    m = re.search(
        r"apikey=([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"
        r"(?:&amp;|&)namespace=([a-z0-9]+)",
        text,
    )
    if m:
        return m.group(2), m.group(1)  # namespace, api_key
    return None, None


def _extract_namespace(text: str) -> str | None:
    """Extract namespace from console page — multiple fallback patterns."""
    # From inline example inbox email: NS.tag@inbox.testmail.app
    m = re.search(r"\b([a-z0-9]+)\.[a-z0-9]+@inbox\.testmail\.app", text)
    if m:
        return m.group(1)
    # From JSON/JS: "namespace": "NS"
    m = re.search(r'"namespace"\s*:\s*"?([a-z0-9]+)"?', text)
    return m.group(1) if m else None


def _extract_uuid_api_key(text: str) -> str | None:
    """Extract testmail API key from apikey= query param (avoids Stripe/Beacon UUIDs)."""
    m = re.search(r"apikey=([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", text)
    return m.group(1) if m else None


# ── Step helpers ──────────────────────────────────────────────────────

async def _fill_signup_form(page: Page, email: str, first: str, last: str) -> None:
    await page.fill("#email", email)
    await asyncio.sleep(0.4)
    await page.fill("#firstName", first)
    await asyncio.sleep(0.4)
    await page.fill("#lastName", last)
    await asyncio.sleep(0.4)
    await page.locator("button#signupbutton").click()


async def _get_verification_code(mailbox: Mailbox, timeout: int, log_fn: LogFn) -> str | None:
    log_fn("  Đợi email verification từ testmail.app...")
    msg = await wait_for_message(
        mailbox,
        from_contains="testmail",
        timeout=timeout,
        poll_interval=5,
        log_fn=log_fn,
    )
    if not msg:
        return None
    log_fn(f"  Subject: {msg.get('subject', 'N/A')!r}")
    body = msg.get("body", "") or msg.get("subject", "")
    code = _extract_verification_code(body)
    log_fn(f"  Code extracted: {code!r}")
    return code


async def _fill_verification_and_confirm(page: Page, code: str) -> None:
    """Điền verification code và click Confirm."""
    try:
        await page.wait_for_selector("#code", state="visible", timeout=10000)
        code_sel = "#code"
    except Exception:  # noqa: BLE001 - best-effort optional UI action
        await page.wait_for_selector("[data-cy='code']", state="visible", timeout=5000)
        code_sel = "[data-cy='code']"

    await page.fill(code_sel, code)
    await page.press(code_sel, "Tab")  # trigger React onChange
    await asyncio.sleep(0.8)

    confirm_btn = page.locator("[data-cy='confirm']")
    await confirm_btn.wait_for(state="visible", timeout=10000)
    await asyncio.sleep(0.5)
    await confirm_btn.click()


async def _extract_console_credentials(page: Page, debug_dir: Path, log_fn: LogFn) -> tuple[str, str]:
    """Navigate /console/ → extract namespace + API key."""
    await page.goto(_console_url(), wait_until="networkidle", timeout=30000)
    await asyncio.sleep(2)
    await _dump_debug(page, "testmail_console.html", debug_dir)

    html = await page.content()

    # Primary: parse both from the Quickstart API URL (most reliable)
    namespace, api_key = _extract_credentials_from_quickstart(html)

    # Fallback: parse separately
    if not namespace:
        log_fn("  ⚠️  Quickstart URL pattern not found, trying fallbacks...")
        body_text = await page.inner_text("body")
        namespace = _extract_namespace(html + "\n" + body_text)
    if not api_key:
        api_key = _extract_uuid_api_key(html)

    if not namespace or not api_key:
        body_text = await page.inner_text("body")
        log_fn("  ⚠️  Không tìm thấy credentials. HTML đầu tiên 500 ký tự:")
        log_fn(f"  {body_text[:500]}")
        raise RuntimeError("Could not extract namespace or API key from console page")

    log_fn(f"  ✅ Namespace: {namespace}")
    log_fn(f"  ✅ API Key: {api_key[:8]}...")
    return namespace, api_key


# ── Full flow ──────────────────────────────────────────────────────────

async def _signup_flow(
    page: Page,
    mailbox: Mailbox,
    cfg: AppConfig,
    log_fn: LogFn,
) -> AccountRecord:
    first, last = _random_name()
    email = mailbox.email
    debug_dir = cfg.base_dir / "debug"
    otp_timeout = cfg.testmail.otp_wait_sec

    log_fn(f"\n[1/5] Opening {_signup_url(cfg)}...")
    await page.goto(_signup_url(cfg), wait_until="networkidle", timeout=30000)
    await asyncio.sleep(1)
    await _dump_debug(page, "testmail_01_signup.html", debug_dir)

    log_fn(f"\n[2/5] Filling form (email={email}, name={first} {last})...")
    await _fill_signup_form(page, email, first, last)
    await asyncio.sleep(4)
    await _dump_debug(page, "testmail_02_after_signup.html", debug_dir)
    log_fn(f"  URL sau signup: {page.url}")

    log_fn(f"\n[3/5] Waiting for verification code (timeout={otp_timeout}s)...")
    code = await _get_verification_code(mailbox, otp_timeout, log_fn)
    if not code:
        raise RuntimeError("Không nhận được verification code từ testmail.app")

    log_fn(f"\n[4/5] Filling verification code: {code}")
    await _fill_verification_and_confirm(page, code)
    await asyncio.sleep(3)
    await _dump_debug(page, "testmail_03_after_confirm.html", debug_dir)
    log_fn(f"  URL sau confirm: {page.url}")

    log_fn("\n[5/5] Extracting namespace + API key from /console/...")
    namespace, api_key = await _extract_console_credentials(page, debug_dir, log_fn)

    provider_str = f"testmail.app:{namespace}:{api_key}"
    return AccountRecord(
        service="TESTMAIL",
        email=email,
        password="",
        api_key=provider_str,
    )


# ── Public API ────────────────────────────────────────────────────────

async def register_testmail(
    cfg: AppConfig,
    log_fn: LogFn,
    save_fn: SaveFn,
) -> AccountRecord | None:
    max_attempts = cfg.register.max_attempts
    for attempt in range(1, max_attempts + 1):
        if attempt > 1:
            log_fn(f"\n🔄 Retry {attempt}/{max_attempts}")

        # Dùng mail.tm để nhận verification (không dùng testmail.app nhận chính nó)
        mailbox = await create_mailbox(cfg.mail.providers_for("testmail"), log_fn=log_fn)
        log_fn(f"📧 Temp email (mail.tm): {mailbox.email}")
        log_fn("-" * 50)

        try:
            async with open_browser(cfg) as browser:
                page = await browser.new_page()
                record = await _signup_flow(page, mailbox, cfg, log_fn)
                await asyncio.to_thread(save_fn, record)
                # Register testmail account as a mail provider (dual-role)
                # record.api_key = compound "testmail.app:NAMESPACE:RAW_KEY"
                _parts = record.api_key.split(":")
                _ns  = _parts[1] if len(_parts) >= 3 else ""
                _key = _parts[2] if len(_parts) >= 3 else record.api_key
                await asyncio.to_thread(
                    upsert_mail_provider,
                    cfg.base_dir / "data" / "accounts.db",
                    "testmail.app",
                    _key,
                    _ns,
                )
                log_fn("✅ Saved to DB")
                return record
        except RuntimeError as exc:
            log_fn(f"\n⚠️  {exc}")
            if attempt < max_attempts:
                log_fn("  → Retrying with a fresh email...")
        except Exception:
            _LOG.exception("Unexpected error in testmail registrar")
            raise

    log_fn(f"\n❌ Failed after {max_attempts} attempts")
    return None
