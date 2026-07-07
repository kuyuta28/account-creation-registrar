"""services/artificialanalysis_ai/flow.py - AA signup automation recipe.

Pure browser automation — nhận `page` từ gateway task, không mở browser.
Entrypoint `_signup_flow` chạy full flow login → magic link → API key.

`_reconstruct_testmail_mailbox` là helper dùng chung cho relogin (reconstruct
Mailbox từ email testmail hiện có để poll magic link).
"""
from __future__ import annotations

import html as _html
import re
from pathlib import Path

from playwright.async_api import Page

from ...config.settings import AppConfig
from common.page_utils import dump_debug_html as _dump_debug
from src.core.account_record import AccountRecord
from ...mail.client import Mailbox, extract_link, wait_for_message
from ..protocols import LogFn


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


async def _navigate_magic_link(page: Page, link: str, base_url: str, timeout_ms: int, log_fn: LogFn) -> str:
    """Navigate magic link, handle JSON response, return org slug."""
    await page.goto(link, timeout=timeout_ms * 2)
    await page.wait_for_timeout(3000)

    body = await page.inner_text("body")

    # Magic link verify returns JSON → need to navigate to /orgs
    if '"token"' in body:
        log_fn("  Got auth token — navigating to dashboard...")
        await page.goto(f"{base_url}/orgs", timeout=timeout_ms * 2)
        await page.wait_for_load_state("domcontentloaded", timeout=timeout_ms)
        await page.wait_for_timeout(3000)

    final_url = page.url
    log_fn(f"  Post-login URL: {final_url}")

    if "/login" in final_url:
        raise RuntimeError(f"Still on login after magic link. URL: {final_url}")

    org_match = re.search(r"/orgs/([^/]+)", final_url)
    if not org_match:
        raise RuntimeError(f"Cannot determine org slug. URL: {final_url}")
    return org_match.group(1)


async def _create_api_key(
    page: Page, org_slug: str, base_url: str, api_key_regex: str, timeout_ms: int, key_label: str, log_fn: LogFn, debug_dir: Path,
) -> str:
    """Navigate to API Access page and create a new API key."""
    api_url = f"{base_url}/orgs/{org_slug}/api-access"
    log_fn(f"  Opening {api_url}")
    await page.goto(api_url, timeout=timeout_ms * 2, wait_until="domcontentloaded")
    await page.wait_for_timeout(2000)
    await _dump_debug(page, "aa_api_access.html", debug_dir)

    log_fn("  Clicking 'Create API key'...")
    create_btn = page.locator("button:has-text('Create API key')")
    await create_btn.click()
    await page.wait_for_timeout(2000)
    await _dump_debug(page, "aa_after_create_click.html", debug_dir)

    form = page.locator("form#new-api-key-form")
    name_input = form.locator("input").first
    await name_input.fill(key_label)
    await page.wait_for_timeout(300)
    log_fn(f"  Filled key name: {key_label}")

    await page.locator("button[type='submit'][form='new-api-key-form']").click()

    await page.wait_for_timeout(3000)
    await _dump_debug(page, "aa_after_key_submit.html", debug_dir)

    api_key = await page.evaluate(f"""() => {{
        let text = document.body.innerText || '';
        document.querySelectorAll('input, textarea, code, pre').forEach(el => {{
            text += ' ' + (el.value || el.innerText || el.textContent || '');
        }});
        const matches = text.match(/{api_key_regex}/g);
        return matches ? matches[0] : null;
    }}""")

    if not api_key:
        await _dump_debug(page, "aa_key_not_found.html", debug_dir)
        raise RuntimeError("API key not found after creation")

    log_fn(f"  API key: {api_key[:20]}...")
    return api_key


async def _accept_image_lab_terms(page: Page, base_url: str, timeout_ms: int, log_fn: LogFn, debug_dir: Path) -> None:
    """Navigate to Image Lab, trigger terms dialog, and accept."""
    image_lab_url = f"{base_url}/image/image-lab"
    log_fn(f"  Opening {image_lab_url}...")
    await page.goto(image_lab_url, timeout=timeout_ms * 2, wait_until="domcontentloaded")
    await page.wait_for_timeout(3000)
    await _dump_debug(page, "aa_image_lab_loaded.html", debug_dir)

    prompt_area = page.locator("textarea").first
    if await prompt_area.count() > 0:
        await prompt_area.fill("test")
        await page.wait_for_timeout(300)

    start_btn = page.locator("button:has-text('Start Generation')").first
    if await start_btn.count() == 0:
        raise RuntimeError("'Start Generation' button not found on Image Lab page")
    await start_btn.click()
    await page.wait_for_timeout(2500)
    await _dump_debug(page, "aa_image_lab_terms_dialog.html", debug_dir)

    agree_btn = page.locator("button:has-text('I agree to the Image Lab Terms of Use')").first
    if await agree_btn.count() == 0:
        log_fn("  (No terms dialog — already accepted or not triggered)")
        return
    await agree_btn.click()
    await page.wait_for_timeout(2000)
    await _dump_debug(page, "aa_image_lab_after_accept.html", debug_dir)
    log_fn("  ✅ Image Lab Terms of Use accepted")


# ── Mailbox reconstruction (dùng chung cho relogin) ───────────────────

def _reconstruct_testmail_mailbox(email: str, cfg: AppConfig, log_fn: LogFn) -> Mailbox:
    """Reconstruct Mailbox từ email testmail hiện có. Raise nếu sai format/provider.

    Email phải là testmail.app format: {namespace}.{tag}@inbox.testmail.app
    """
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

    from ...mail._base import get_testmail_base, Mailbox as _Mailbox
    return _Mailbox(
        email=email,
        token=namespace,
        account_id=tag,
        base_url=get_testmail_base(),
        provider="testmail.app",
        api_key=api_key,
    )


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

    log_fn(f"\n[1/5] Opening {aa_cfg.login_url}...")
    await page.goto(aa_cfg.login_url, timeout=t.page_load * 2, wait_until="domcontentloaded")
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
    org_slug = await _navigate_magic_link(page, link, aa_cfg.base_url, t.page_load, log_fn)
    log_fn(f"  Org slug: {org_slug}")
    await _dump_debug(page, "aa_03_dashboard.html", debug_dir)

    log_fn("\n[4.5/5] Accepting Image Lab Terms of Use...")
    await _accept_image_lab_terms(page, aa_cfg.base_url, t.page_load, log_fn, debug_dir)

    log_fn("\n[5/5] Creating API key...")
    api_key = await _create_api_key(
        page, org_slug, aa_cfg.base_url, aa_cfg.api_key_regex, t.page_load, cfg.register.api_key_label, log_fn, debug_dir,
    )

    return AccountRecord(
        service="ARTIFICIALANALYSIS",
        email=email,
        password="",
        api_key=api_key,
    )
