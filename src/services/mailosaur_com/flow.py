"""services/mailosaur_com/flow.py - Mailosaur signup automation recipe.

Pure browser automation — nhận `page` từ gateway task, không mở browser.
Entrypoint `_signup_flow` chạy full flow signup → OTP → onboard → API key.

Flow:
  1. goto signup form
  2. submit email + wait recaptcha
  3. poll testmail.app cho OTP (6 chars alphanumeric uppercase)
  4. fill OTP vào 6 input fields
  5. onboard: name, password, reject-marketing
  6. use-cases: automatingTests
  7. framework: playwright
  8. first inbox: email, "My Inbox", setup-inbox → extract SERVER_ID
  9. /app/keys → create standard key → reveal → extract API key
"""
from __future__ import annotations

import random
import re
import string

from playwright.async_api import Page

from ...config.settings import AppConfig
from common.page_utils import dump_debug_html as _dump_debug
from src.core.account_record import AccountRecord
from ...mail.client import Mailbox, wait_for_message
from ..protocols import LogFn

_NAMES = [
    ("Alex", "Morgan"), ("Jordan", "Taylor"), ("Casey", "Riley"),
    ("Morgan", "Quinn"), ("Taylor", "Avery"), ("Chris", "Bailey"),
    ("Robin", "Blake"), ("Jamie", "Cameron"), ("Drew", "Ellis"),
    ("Skyler", "Finley"),
]


# ── Pure helpers ──────────────────────────────────────────────────────

def _random_name() -> tuple[str, str]:
    return random.choice(_NAMES)


def _random_password() -> str:
    special = random.choice("!@#$%^&*()")
    nums = "".join(random.choices(string.digits, k=3))
    uppers = "".join(random.choices(string.ascii_uppercase, k=3))
    lowers = "".join(random.choices(string.ascii_lowercase, k=6))
    chars = list(special + nums + uppers + lowers)
    random.shuffle(chars)
    return "".join(chars)


def _extract_otp(body: str) -> str | None:
    """Extract 6-char alphanumeric OTP từ email body (uppercase)."""
    codes = re.findall(r'\b([A-Z0-9]{6})\b', str(body))
    skip = {"VERIFY", "RESEND", "PLEASE", "FOLLOW", "KINDLY"}
    for code in codes:
        if code not in skip:
            return code
    return None


def _extract_server_id(url: str) -> str | None:
    """Extract SERVER_ID từ URL: /app/servers/{SERVER_ID}/messages/inbox"""
    m = re.search(r"/app/servers/([a-z0-9]+)/", url)
    return m.group(1) if m else None


# ── Step helpers ──────────────────────────────────────────────────────

async def _submit_email(page: Page, email: str) -> None:
    """Fill email + wait recaptcha + JS click submit."""
    await page.locator("input[name=email]").fill(email)
    await page.wait_for_timeout(4000)  # đợi recaptcha init
    await page.evaluate("document.querySelector('button[type=submit]').click()")


async def _fill_otp(page: Page, otp: str) -> None:
    """Fill 6 OTP chars vào 6 input riêng biệt."""
    for i, char in enumerate(otp):
        await page.locator(f'[data-testid="code-input-{i}"]').fill(char)
        await page.wait_for_timeout(150)
    await page.wait_for_timeout(500)
    await page.evaluate("() => { const b = document.querySelector('button[type=submit]'); if(b) b.click(); }")


async def _fill_onboard(page: Page, first: str, last: str, password: str, msr_cfg) -> None:
    """Fill onboard form: name + password + reject marketing + submit."""
    full_name = f"{first} {last}"
    await page.locator("input[name=name]").fill(full_name)
    await page.wait_for_timeout(300)
    await page.locator('[data-testid="password-input"]').fill(password)
    await page.wait_for_timeout(300)
    await page.locator('[data-testid="reject-marketing"]').click()
    await page.wait_for_timeout(300)
    await page.locator("button[type=submit]").click(timeout=msr_cfg.click_timeout_ms)


async def _pick_use_case(page: Page, msr_cfg) -> None:
    """Chọn automatingTests + submit."""
    await page.locator('[data-testid="option-automatingTests"]').click()
    await page.wait_for_timeout(300)
    await page.locator("button[type=submit]").click(timeout=msr_cfg.click_timeout_ms)


async def _pick_framework(page: Page, msr_cfg) -> None:
    """Chọn playwright label + submit."""
    lbl = page.locator('label[for="playwright"]')
    if await lbl.count() > 0:
        await lbl.click()
    else:
        await page.evaluate("document.getElementById('playwright').click()")
    await page.wait_for_timeout(300)
    await page.locator("button[type=submit]").click(timeout=msr_cfg.click_timeout_ms)


async def _setup_first_inbox(page: Page, msr_cfg) -> None:
    """Chọn email type, đặt tên inbox, click setup."""
    await page.locator('[data-testid="option-email"]').click()
    await page.wait_for_timeout(500)
    await page.locator('[data-testid="inbox-name-input"]').fill("My Inbox")
    await page.wait_for_timeout(500)
    await page.locator('[data-testid="setup-inbox"]').click(timeout=msr_cfg.click_timeout_ms)
    await page.wait_for_url(lambda url: "first-inbox" not in url, timeout=msr_cfg.wait_url_timeout_ms, wait_until="commit")


async def _extract_api_key(page: Page, msr_cfg, debug_dir, log_fn: LogFn) -> str:
    """Navigate tới /app/keys → tạo standard key → lấy API key từ dialog."""
    log_fn("  Navigating to API keys page...")
    await page.goto(msr_cfg.keys_url, wait_until="domcontentloaded", timeout=msr_cfg.keys_page_timeout_ms)
    await page.wait_for_timeout(3000)
    await _dump_debug(page, "msr_09_api_keys_page.html", debug_dir)

    log_fn("  Clicking 'Create standard key'...")
    await page.locator("button:has-text('Create standard key')").click(timeout=msr_cfg.click_timeout_ms)
    await page.wait_for_timeout(2000)
    await _dump_debug(page, "msr_10_create_key_dialog.html", debug_dir)

    name_input = page.locator("input[placeholder*='name'], input[placeholder*='Name'], input[name='name'], input[type='text']").first
    if await name_input.count() > 0:
        log_fn("  Filling key name...")
        await name_input.fill("default")
        await page.wait_for_timeout(500)

    btns = await page.locator("button").all()
    btn_texts = [(await b.inner_text()).strip() for b in btns]
    log_fn(f"  Buttons: {[t for t in btn_texts if t]}")

    for confirm_text in ["Create", "Create key", "Generate", "Confirm", "Save"]:
        confirm_btn = page.locator(f"button:has-text('{confirm_text}')").last
        if await confirm_btn.count() > 0:
            log_fn(f"  Confirming with '{confirm_text}'...")
            await confirm_btn.click(timeout=msr_cfg.click_timeout_ms)
            await page.wait_for_timeout(3000)
            break

    await _dump_debug(page, "msr_11_after_key_created.html", debug_dir)

    reveal_btn = page.locator('[data-testid="reveal-key-btn"]')
    if await reveal_btn.count() > 0:
        log_fn("  Clicking 'Reveal Key'...")
        await reveal_btn.first.click()
        await page.wait_for_timeout(2000)
        await _dump_debug(page, "msr_12_after_reveal.html", debug_dir)

    for selector in [
        '[data-testid*="col-1"] span',
        '[data-testid="text"]',
        '[data-testid="copyable-text"]',
        "code",
        "pre",
        "input[readonly]",
        'input[type="text"]',
    ]:
        els = page.locator(selector)
        count = await els.count()
        for i in range(count):
            if selector.startswith("input"):
                txt = (await els.nth(i).input_value()).strip()
            else:
                txt = (await els.nth(i).inner_text()).strip()
            if len(txt) > 20 and "@" not in txt and " " not in txt and "http" not in txt and "\n" not in txt:
                log_fn(f"  Found API key ({selector} #{i}): {txt[:8]}...")
                return txt

    body_txt = await page.inner_text("body")
    log_fn(f"  ⚠️  Không lấy được API key. Body:\n{body_txt[:800]}")
    raise RuntimeError("Không lấy được API key từ /app/keys")


# ── Full flow ──────────────────────────────────────────────────────────

async def _signup_flow(
    page: Page,
    mailbox: Mailbox,
    cfg: AppConfig,
    log_fn: LogFn,
) -> AccountRecord:
    msr_cfg = cfg.mailosaur
    first, last = _random_name()
    password = _random_password()
    email = mailbox.email
    debug_dir = cfg.base_dir / "debug"
    otp_timeout = cfg.testmail.otp_wait_sec  # reuse testmail config (same timeout)

    log_fn(f"\n[1/9] Mở {msr_cfg.signup_url}...")
    await page.goto(msr_cfg.signup_url, wait_until="domcontentloaded", timeout=msr_cfg.keys_page_timeout_ms)
    await page.wait_for_timeout(3000)
    await _dump_debug(page, "msr_01_signup.html", debug_dir)

    log_fn(f"\n[2/9] Submit email: {email}")
    await _submit_email(page, email)
    await page.wait_for_timeout(6000)
    await _dump_debug(page, "msr_02_after_submit.html", debug_dir)
    log_fn(f"  URL: {page.url}")

    log_fn(f"\n[3/9] Đợi OTP email (timeout={otp_timeout}s)...")
    msg = await wait_for_message(
        mailbox,
        from_contains="mailosaur",
        timeout=otp_timeout,
        log_fn=log_fn,
    )
    if not msg:
        raise RuntimeError("Không nhận được email OTP từ Mailosaur")

    body = msg.get("body", "") or msg.get("text", "") or msg.get("subject", "")
    log_fn(f"  Subject: {msg.get('subject', 'N/A')!r}")
    otp = _extract_otp(body)
    if not otp:
        log_fn(f"  Body snippet: {str(body)[:300]}")
        raise RuntimeError("Không extract được OTP từ email Mailosaur")
    log_fn(f"  OTP: {otp}")

    log_fn(f"\n[4/9] Fill OTP: {otp}")
    await _fill_otp(page, otp)
    await page.wait_for_timeout(6000)
    await _dump_debug(page, "msr_03_after_otp.html", debug_dir)
    log_fn(f"  URL: {page.url}")

    log_fn(f"\n[5/9] Onboard: name={first} {last}")
    await _fill_onboard(page, first, last, password, msr_cfg)
    await page.wait_for_timeout(6000)
    await _dump_debug(page, "msr_04_after_onboard.html", debug_dir)
    log_fn(f"  URL: {page.url}")

    log_fn("\n[6/9] Use-case: automatingTests")
    await _pick_use_case(page, msr_cfg)
    await page.wait_for_timeout(6000)
    await _dump_debug(page, "msr_05_after_usecase.html", debug_dir)
    log_fn(f"  URL: {page.url}")

    log_fn("\n[7/9] Framework: playwright")
    await _pick_framework(page, msr_cfg)
    await page.wait_for_timeout(6000)
    await _dump_debug(page, "msr_06_after_framework.html", debug_dir)
    log_fn(f"  URL: {page.url}")

    log_fn("\n[8/9] Setup first inbox...")
    await _setup_first_inbox(page, msr_cfg)
    await page.wait_for_timeout(3000)
    await _dump_debug(page, "msr_07_after_inbox_setup.html", debug_dir)
    log_fn(f"  URL: {page.url}")

    server_id = _extract_server_id(page.url)
    if not server_id:
        raise RuntimeError(f"Không extract được server_id từ URL: {page.url}")
    log_fn(f"  SERVER_ID: {server_id}")

    log_fn("\n[9/9] Lấy API key từ dashboard...")
    api_key = await _extract_api_key(page, msr_cfg, debug_dir, log_fn)
    log_fn(f"  API key: {api_key[:8]}...")

    return AccountRecord(
        service="MAILOSAUR",
        email=email,
        password=password,
        api_key=api_key,
        account_id=server_id,
    )
