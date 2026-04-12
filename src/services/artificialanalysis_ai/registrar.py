"""
registrar.py — Artificial Analysis account registration (FP module).

Flow:
  1. create_mailbox()
  2. Playwright → fill email on /login → click Continue
  3. Wait for magic link email → navigate
  4. Extract org slug from redirect URL
  5. Navigate to /orgs/{slug}/api-access → Create API key
  6. save_fn(record)

Public API:
  register_artificialanalysis(cfg, log_fn, save_fn) → Optional[AccountRecord]
"""
from __future__ import annotations

import asyncio
import html as _html
import logging
import re
from pathlib import Path

from playwright.async_api import Page

from ...config.settings import AppConfig
from common.browser import open_browser
from common.page_utils import dump_debug_html as _dump_debug
from src.core.storage import AccountRecord, db_path
from ...mail.client import Mailbox, create_mailbox, extract_link, wait_for_message
from ..protocols import LogFn, SaveFn
from .session import save_session

_LOG = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────

_LOGIN_URL = "https://artificialanalysis.ai/login"
_BASE_URL = "https://artificialanalysis.ai"


# ── Step helpers ──────────────────────────────────────────────────────

async def _fill_email_and_submit(page: Page, email: str, log_fn: LogFn) -> None:
    """Fill email input and click Continue."""
    await page.locator("input[name='email']").fill(email)
    await page.wait_for_timeout(500)
    await page.locator("button[type='submit']:has-text('Continue')").click()


async def _fetch_magic_link(mailbox: Mailbox, timeout: int, log_fn: LogFn) -> str:
    """Wait for magic link email and extract the verify URL."""
    msg = await wait_for_message(
        mailbox, from_contains="artificialanalysis", timeout=timeout, poll_interval=4, log_fn=log_fn,
    )
    if not msg:
        raise RuntimeError("No magic link email received from Artificial Analysis")

    log_fn(f"  Subject: {msg.get('subject', 'N/A')}")

    body_text = msg.get("body", "") or msg.get("text", "") or ""
    html_parts = msg.get("html", [""])
    html_text = html_parts[0] if html_parts else ""

    link = (
        extract_link(body_text, "artificialanalysis")
        or extract_link(html_text, "artificialanalysis")
    )
    if not link:
        raise RuntimeError("Could not extract magic link from email")
    return _html.unescape(link).rstrip(".,;)")


async def _navigate_magic_link(page: Page, link: str, timeout_ms: int, log_fn: LogFn) -> str:
    """Navigate magic link, handle JSON response, return org slug."""
    await page.goto(link, timeout=timeout_ms * 2)
    await page.wait_for_timeout(3000)

    body = await page.inner_text("body")

    # Magic link verify returns JSON → need to navigate to /orgs
    if '"token"' in body:
        log_fn("  Got auth token — navigating to dashboard...")
        await page.goto(f"{_BASE_URL}/orgs", timeout=timeout_ms * 2)
        await page.wait_for_load_state("domcontentloaded", timeout=timeout_ms)
        await page.wait_for_timeout(3000)

    final_url = page.url
    log_fn(f"  Post-login URL: {final_url}")

    # If still on login page, auth failed
    if "/login" in final_url:
        raise RuntimeError(f"Still on login after magic link. URL: {final_url}")

    # Extract org slug from URL: /orgs/{slug}/...
    org_match = re.search(r"/orgs/([^/]+)", final_url)
    if not org_match:
        raise RuntimeError(f"Cannot determine org slug. URL: {final_url}")
    return org_match.group(1)


async def _create_api_key(
    page: Page, org_slug: str, timeout_ms: int, key_label: str, log_fn: LogFn, debug_dir: Path,
) -> str:
    """Navigate to API Access page and create a new API key."""
    api_url = f"{_BASE_URL}/orgs/{org_slug}/api-access"
    log_fn(f"  Opening {api_url}")
    await page.goto(api_url, timeout=timeout_ms * 2, wait_until="domcontentloaded")
    await page.wait_for_timeout(2000)
    await _dump_debug(page, "aa_api_access.html", debug_dir)

    # Click "Create API key" button
    log_fn("  Clicking 'Create API key'...")
    create_btn = page.locator("button:has-text('Create API key')")
    await create_btn.click()
    await page.wait_for_timeout(2000)
    await _dump_debug(page, "aa_after_create_click.html", debug_dir)

    # Fill key name in dialog form
    form = page.locator("form#new-api-key-form")
    name_input = form.locator("input").first
    await name_input.fill(key_label)
    await page.wait_for_timeout(300)
    log_fn(f"  Filled key name: {key_label}")

    # Submit — click "Create key" button
    await page.locator("button[type='submit'][form='new-api-key-form']").click()

    await page.wait_for_timeout(3000)
    await _dump_debug(page, "aa_after_key_submit.html", debug_dir)

    # Extract API key — look for aa_ pattern
    api_key = await page.evaluate("""() => {
        let text = document.body.innerText || '';
        document.querySelectorAll('input, textarea, code, pre').forEach(el => {
            text += ' ' + (el.value || el.innerText || el.textContent || '');
        });
        const matches = text.match(/aa_[a-zA-Z0-9_-]{10,}/g);
        return matches ? matches[0] : null;
    }""")

    if not api_key:
        await _dump_debug(page, "aa_key_not_found.html", debug_dir)
        raise RuntimeError("API key not found after creation")

    log_fn(f"  API key: {api_key[:20]}...")
    return api_key


async def _accept_image_lab_terms(page: Page, timeout_ms: int, log_fn: LogFn, debug_dir: Path) -> None:
    """Navigate to Image Lab, trigger terms dialog, and accept."""
    image_lab_url = f"{_BASE_URL}/image/image-lab"
    log_fn(f"  Opening {image_lab_url}...")
    await page.goto(image_lab_url, timeout=timeout_ms * 2, wait_until="domcontentloaded")
    await page.wait_for_timeout(3000)
    await _dump_debug(page, "aa_image_lab_loaded.html", debug_dir)

    # Fill dummy prompt to enable Start Generation button
    prompt_area = page.locator("textarea").first
    if await prompt_area.count() > 0:
        await prompt_area.fill("test")
        await page.wait_for_timeout(300)

    # Click Start Generation to trigger Terms dialog
    start_btn = page.locator("button:has-text('Start Generation')").first
    if await start_btn.count() == 0:
        raise RuntimeError("'Start Generation' button not found on Image Lab page")
    await start_btn.click()
    await page.wait_for_timeout(2500)
    await _dump_debug(page, "aa_image_lab_terms_dialog.html", debug_dir)

    # Click accept button in terms dialog
    agree_btn = page.locator("button:has-text('I agree to the Image Lab Terms of Use')").first
    if await agree_btn.count() == 0:
        log_fn("  (No terms dialog — already accepted or not triggered)")
        return
    await agree_btn.click()
    await page.wait_for_timeout(2000)
    await _dump_debug(page, "aa_image_lab_after_accept.html", debug_dir)
    log_fn("  ✅ Image Lab Terms of Use accepted")


# ── Full flow ──────────────────────────────────────────────────────────

async def _signup_flow(
    page: Page,
    mailbox: Mailbox,
    email: str,
    cfg: AppConfig,
    log_fn: LogFn,
) -> AccountRecord:
    t = cfg.timeouts
    aa_cfg = cfg.artificialanalysis
    debug_dir = cfg.base_dir / "debug"

    log_fn(f"\n[1/5] Opening {_LOGIN_URL}...")
    await page.goto(_LOGIN_URL, timeout=t.page_load * 2, wait_until="domcontentloaded")
    await page.wait_for_timeout(t.nav_delay)
    await _dump_debug(page, "aa_01_login.html", debug_dir)

    log_fn("\n[2/5] Filling email & submitting...")
    await _fill_email_and_submit(page, email, log_fn)
    await page.wait_for_timeout(aa_cfg.post_submit_wait_ms)
    await _dump_debug(page, "aa_02_after_submit.html", debug_dir)
    log_fn("  Magic link sent — check email")

    log_fn(f"\n[3/5] Waiting for magic link (up to {aa_cfg.magic_link_wait_sec}s)...")
    link = await _fetch_magic_link(mailbox, aa_cfg.magic_link_wait_sec, log_fn)
    log_fn(f"  Link: {link[:80]}...")

    log_fn("\n[4/5] Navigating magic link...")
    org_slug = await _navigate_magic_link(page, link, t.page_load, log_fn)
    log_fn(f"  Org slug: {org_slug}")
    await _dump_debug(page, "aa_03_dashboard.html", debug_dir)

    log_fn("\n[4.5/5] Accepting Image Lab Terms of Use...")
    await _accept_image_lab_terms(page, t.page_load, log_fn, debug_dir)

    log_fn("\n[5/5] Creating API key...")
    api_key = await _create_api_key(
        page, org_slug, t.page_load, cfg.register.api_key_label, log_fn, debug_dir,
    )

    return AccountRecord(
        service="ARTIFICIALANALYSIS",
        email=email,
        password="",
        api_key=api_key,
    )


# ── Public API ────────────────────────────────────────────────────────

async def relogin_artificialanalysis(
    email: str,
    cfg: AppConfig,
    log_fn: LogFn,
) -> None:
    """Re-login tài khoản AA đã có qua magic link. Cập nhật session_state trong DB.

    Dùng khi session_token hết hạn — flow giống registration nhưng không tạo API key.
    Email phải là testmail.app format: {namespace}.{tag}@inbox.testmail.app
    """
    t = cfg.timeouts
    aa_cfg = cfg.artificialanalysis
    debug_dir = cfg.base_dir / "debug"

    # ── Reconstruct Mailbox từ email testmail hiện có ─────────────────────
    local, _, domain = email.partition("@")
    if domain != "inbox.testmail.app":
        raise RuntimeError(f"relogin chỉ hỗ trợ testmail.app — email không hợp lệ: {email}")

    namespace, _, tag = local.partition(".")
    if not namespace or not tag:
        raise RuntimeError(f"Email testmail sai format (phải là ns.tag@inbox.testmail.app): {email}")

    providers = cfg.mail.providers_for("artificialanalysis")
    api_key = ""
    for p in providers:
        if p.startswith(f"testmail.app:{namespace}:"):
            api_key = p.split(":", 2)[2]
            break
    if not api_key:
        raise RuntimeError(
            f"Không tìm thấy testmail provider với namespace '{namespace}' trong DB. "
            "Kiểm tra bảng mail_providers."
        )

    from ...mail._base import TESTMAIL_BASE, Mailbox as _Mailbox  # noqa: PLC0415
    mailbox = _Mailbox(
        email=email,
        token=namespace,
        account_id=tag,
        base_url=TESTMAIL_BASE,
        provider="testmail.app",
        api_key=api_key,
    )

    log_fn(f"🔑 Re-login: {email}")
    log_fn("-" * 50)

    # ── Magic link flow (không tạo API key) ──────────────────────────────
    async with open_browser(cfg) as browser:
        context = await browser.new_context()
        page = await context.new_page()

        log_fn(f"\n[1/4] Opening {_LOGIN_URL}...")
        await page.goto(_LOGIN_URL, timeout=t.page_load * 2, wait_until="domcontentloaded")
        await page.wait_for_timeout(t.nav_delay)
        await _dump_debug(page, "aa_relogin_01_login.html", debug_dir)

        log_fn("\n[2/4] Filling email & submitting...")
        await _fill_email_and_submit(page, email, log_fn)
        await page.wait_for_timeout(aa_cfg.post_submit_wait_ms)
        await _dump_debug(page, "aa_relogin_02_after_submit.html", debug_dir)
        log_fn("  Magic link sent — waiting for email")

        log_fn(f"\n[3/4] Waiting for magic link (up to {aa_cfg.magic_link_wait_sec}s)...")
        link = await _fetch_magic_link(mailbox, aa_cfg.magic_link_wait_sec, log_fn)
        log_fn(f"  Link: {link[:80]}...")

        log_fn("\n[4/4] Navigating magic link...")
        await _navigate_magic_link(page, link, t.page_load, log_fn)
        await _dump_debug(page, "aa_relogin_03_dashboard.html", debug_dir)

        log_fn("\n[4.5/4] Accepting Image Lab Terms of Use...")
        await _accept_image_lab_terms(page, t.page_load, log_fn, debug_dir)

        await save_session(db_path(cfg.base_dir), email, context)

        from common.database import update_account  # noqa: PLC0415
        update_account(db_path(cfg.base_dir), "ARTIFICIALANALYSIS", email, check_status="valid")

        log_fn("✅ Session refreshed + check_status = valid")


async def register_artificialanalysis(
    cfg: AppConfig,
    log_fn: LogFn,
    save_fn: SaveFn,
) -> AccountRecord | None:
    max_attempts = cfg.register.max_attempts
    for attempt in range(1, max_attempts + 1):
        mailbox = await create_mailbox(
            cfg.mail.providers_for("artificialanalysis"), log_fn=log_fn)
        email = mailbox.email

        if attempt > 1:
            log_fn(f"\n🔄 Retry {attempt}/{max_attempts}")
        log_fn(f"📧 Email: {email}")
        log_fn("-" * 50)

        try:
            async with open_browser(cfg) as browser:
                context = await browser.new_context()
                page = await context.new_page()
                record = await _signup_flow(page, mailbox, email, cfg, log_fn)
                await asyncio.to_thread(save_fn, record)
                log_fn("✅ Saved to DB")
                await save_session(db_path(cfg.base_dir), email, context)
                log_fn("✅ Session saved")
                return record
        except RuntimeError as exc:
            log_fn(f"\n⚠️  {exc}")
            if attempt < max_attempts:
                log_fn("  → Retrying with a fresh email...")
        except Exception:
            _LOG.exception("Unexpected error in artificialanalysis registrar")
            raise

    log_fn(f"\n❌ Failed after {max_attempts} attempts")
    return None
