"""cloudflare_dom_dump.py - Dump real Cloudflare DOM for upcoming registrar.
Run from repo root with python -m registrar.scripts.cloudflare_dom_dump
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTRAR = ROOT / "registrar"
COMMON = ROOT / "common" / "src"
sys.path.insert(0, str(REGISTRAR / "src"))
sys.path.insert(0, str(COMMON))

from common.browser import open_browser
from common.page_utils import dump_debug_html
from config.settings import load_config
from mail.client import create_mailbox, extract_link, wait_for_message, get_message_body
from common.password import generate_password

DEBUG_DIR = REGISTRAR / "debug" / "cf_dump"


def _log(msg: str) -> None:
    print(msg)


async def _describe_page(page, label: str) -> None:
    await dump_debug_html(page, f"{label}.html", DEBUG_DIR)
    info = await page.evaluate("""() => {
        const inputs = [...document.querySelectorAll('input, select, textarea')].map(el => ({
            tag: el.tagName,
            type: el.type || '',
            name: el.name || '',
            id: el.id || '',
            placeholder: el.placeholder || '',
            ariaLabel: el.getAttribute('aria-label') || '',
            dataTestId: el.getAttribute('data-testid') || '',
        }));
        const buttons = [...document.querySelectorAll('button')].map(el => ({
            text: el.textContent.trim().replace(/\\s+/g, ' '),
            disabled: el.disabled,
            type: el.type || '',
            id: el.id || '',
            ariaLabel: el.getAttribute('aria-label') || '',
            dataTestId: el.getAttribute('data-testid') || '',
        }));
        const links = [...document.querySelectorAll('a')].map(el => el.href).filter(Boolean).slice(0, 20);
        return { url: location.href, title: document.title, inputs, buttons, links };
    }""")
    path = DEBUG_DIR / f"{label}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(info, indent=2, ensure_ascii=False), encoding="utf-8")
    _log(f"  dumped {label}.html + {label}.json")


async def main() -> None:
    cfg = load_config()
    _log(f"base_dir={cfg.base_dir}")
    _log("Creating testmail mailbox for cloudflare tag...")
    mailbox = await create_mailbox(cfg.mail.providers_for("cloudflare"), log_fn=_log)
    _log(f"email={mailbox.email} provider={mailbox.provider}")
    password = generate_password(cfg.register.password_length)
    _log(f"password generated ({len(password)} chars)")

    async with open_browser(cfg) as browser:
        page = await browser.new_page()
        cf = cfg.cloudflare

        _log(f"\n[1] Opening {cf.signup_url}...")
        await page.goto(cf.signup_url, timeout=cfg.timeouts.page_load * 3, wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)
        await _describe_page(page, "01_signup_loaded")

        _log("\n[2] Filling signup form...")
        await page.locator(cf.email_selector).first.fill(mailbox.email)
        await page.wait_for_timeout(500)
        pws = await page.locator(cf.password_selector).all()
        if not pws:
            _log("ERROR: no password input")
            return
        await pws[0].fill(password)
        await page.wait_for_timeout(500)
        if len(pws) > 1:
            await pws[1].fill(password)
            await page.wait_for_timeout(500)
        await _describe_page(page, "02_form_filled")

        _log("\n[3] Clicking Turnstile checkbox...")
        for sec in range(20):
            frames = [f for f in page.frames if "challenges.cloudflare.com" in f.url]
            if frames:
                _log(f"  CF frame found after {sec+1}s")
                await page.wait_for_timeout(2000)
                try:
                    await frames[0].locator("body").click(timeout=10000)
                    _log("  clicked CF body")
                except Exception as exc:
                    _log(f"  click CF error: {exc}")
                break
            await page.wait_for_timeout(1000)
        else:
            _log("  no CF frame found")
        await _describe_page(page, "03_after_turnstile_click")

        _log("\n[4] Submitting signup...")
        try:
            btn = page.locator(f"button:has-text('{cf.signup_button_text}')").first
            await btn.wait_for(state="visible", timeout=10000)
            await btn.click(timeout=10000)
        except Exception as exc:
            _log(f"  direct signup button error: {exc}, trying JS fallback dump")
            clicked = await page.evaluate("""() => {
                const b = [...document.querySelectorAll('button')].find(x => x.textContent.toLowerCase().includes('sign up') && !x.disabled);
                if (b) { b.click(); return true; }
                return false;
            }""")
            _log(f"  JS click result: {clicked}")
        await page.wait_for_timeout(cf.post_submit_wait_ms)
        await page.wait_for_timeout(3000)
        await _describe_page(page, "04_after_submit")

        _log("\n[5] Waiting for verification email...")
        msg = await wait_for_message(mailbox, from_contains="cloudflare", subject_contains="verify", timeout=180, log_fn=_log)
        if not msg:
            _log("ERROR: no verify email")
            return
        body = await get_message_body(mailbox, msg["id"])
        link = extract_link(body, "dash.cloudflare.com")
        _log(f"  verify link: {link}")
        if not link:
            _log("ERROR: no verify link in email")
            return

        _log("\n[6] Opening verify link...")
        await page.goto(link, timeout=cfg.timeouts.page_load * 2, wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)
        await _describe_page(page, "05_after_verify")

        _log("\n[7] Skipping onboarding...")
        for text in cf.skip_button_texts:
            try:
                btn = page.get_by_role("button", name=text).first
                if await btn.is_visible(timeout=2000):
                    await btn.click(timeout=5000)
                    _log(f"  clicked skip button: {text}")
                    await page.wait_for_timeout(3000)
            except Exception:
                pass
            try:
                js = await page.evaluate("""(text) => {
                    const b = [...document.querySelectorAll('button')].find(x => x.textContent.trim().toLowerCase() === text.toLowerCase() && !x.disabled);
                    if (b) { b.click(); return true; } return false;
                }""", text)
                if js:
                    _log(f"  JS clicked skip: {text}")
                    await page.wait_for_timeout(3000)
            except Exception as exc:
                _log(f"  skip error: {exc}")
        await _describe_page(page, "06_after_onboarding")

        import re
        m = re.search(cf.account_id_regex, page.url)
        account_id = m.group(1) if m else None
        _log(f"  url={page.url} account_id={account_id}")

        if account_id:
            token_url = cf.token_create_url_template.format(account_id=account_id)
            _log(f"\n[8] Opening token create page {token_url}...")
            await page.goto(token_url, timeout=cfg.timeouts.page_load * 2, wait_until="domcontentloaded")
            await page.wait_for_timeout(3000)
            await _describe_page(page, "07_token_page")

    _log("\nDump complete.")


if __name__ == "__main__":
    asyncio.run(main())
