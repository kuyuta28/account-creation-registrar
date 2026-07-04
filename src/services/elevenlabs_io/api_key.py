"""
services/elevenlabs/api_key.py
Pure function — create an unrestricted API key and return its value.
No class state, all deps injected.
"""
from __future__ import annotations

from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError

from ...config.settings import AppConfig
from ..protocols import LogFn
from common.page_utils import safe_load, dump_debug_html as _dump_debug
from .onboarding import handle_onboarding


async def create_api_key(page: Page, log_fn: LogFn, cfg: AppConfig) -> str:
    """
    Navigate to API keys page, open the Create Key dialog,
    disable Restrict Key, confirm, and return the sk_... string.
    """
    t = cfg.timeouts
    url = cfg.elevenlabs.api_keys_url
    log_fn(f"\n[API KEY] Navigating to API keys page...  url={url}")
    await page.goto(url, timeout=t.page_load * 2)
    await _safe_load(page, t.page_load)
    await page.wait_for_timeout(t.nav_delay)

    await _dump_debug(page, "apikey_page.html", cfg.debug_dir)
    log_fn(f"  URL: {page.url}")

    if "onboarding" in page.url:
        log_fn("  Still in onboarding, handling...")
        await handle_onboarding(page, log_fn, cfg)
        await page.goto(url, timeout=t.page_load * 2)
        await _safe_load(page, t.page_load)
        await page.wait_for_timeout(t.nav_delay)
        await _dump_debug(page, "apikey_page_after_onboarding.html", cfg.debug_dir)

    await _log_buttons(page, log_fn)
    await _click_create_key(page, log_fn, cfg.screenshot_dir)

    await page.wait_for_timeout(t.step_delay)
    await _dump_debug(page, "apikey_after_click.html", cfg.debug_dir)

    await _fill_key_name(page, log_fn, cfg, t.short_delay)
    await _disable_restrict_key(page, log_fn, t.short_delay)
    await _dump_debug(page, "apikey_after_toggle.html", cfg.debug_dir)

    await _confirm_dialog(page, log_fn)
    await page.wait_for_timeout(t.step_delay)
    await _dump_debug(page, "apikey_after_confirm.html", cfg.debug_dir)

    return await _extract_api_key(page, cfg.elevenlabs.api_key_regex, log_fn)


# ── private helpers ───────────────────────────────────────────────────────────

async def _safe_load(page: Page, timeout: int) -> None:
    await safe_load(page, timeout)


async def _log_buttons(page: Page, log_fn: LogFn) -> None:
    btn_texts: list = await page.evaluate("""() =>
        Array.from(document.querySelectorAll('button'))
            .map(b => b.innerText.trim())
            .filter(t => t.length > 0)
    """)
    log_fn("  [DEBUG] Buttons on page:")
    for t in btn_texts:
        log_fn(f"    - '{t}'")


async def _click_create_key(page: Page, log_fn: LogFn, screenshot_dir) -> None:
    import re as _re
    keywords = ["create key", "create api key", "create new key", "new key", "add key"]
    for kw in keywords:
        try:
            btn = page.get_by_role("button", name=_re.compile(kw, _re.IGNORECASE))
            if await btn.count() > 0 and await btn.first.is_visible():
                await btn.first.click()
                log_fn(f"  → Clicked '{kw}'")
                return
        except PlaywrightTimeoutError:
            continue
    await page.screenshot(path=str(screenshot_dir / "apikey_error.png"))
    raise RuntimeError("Cannot find Create Key button")


async def _fill_key_name(page: Page, log_fn: LogFn, cfg: AppConfig, delay: int) -> None:
    import random as _random
    import string as _string
    label = "".join(_random.choices(_string.digits, k=10))
    try:
        inp = page.get_by_placeholder("API Key Name")
        if await inp.count() == 0:
            inp = page.locator("input[type='text']").last
        if await inp.is_visible():
            await inp.fill(label)
            log_fn(f"  → Filled key name: {label}")
            await page.wait_for_timeout(delay)
        else:
            log_fn("  ℹ️ Key name input not visible, skipping")
    except Exception as e:  # noqa: BLE001 - best-effort UI action - log and continue
        log_fn(f"  ℹ️ Key name fill skipped: {e}")


async def _disable_restrict_key(page: Page, log_fn: LogFn, delay: int) -> None:
    """Turn OFF the Restrict Key toggle — scoped bằng ID prefix để tránh click nhầm."""
    toggled: bool = await page.evaluate("""() => {
        // ID pattern: restrict-key-toggle-* — chỉ có trong Create API Key sheet
        const sw = document.querySelector("button[id^='restrict-key-toggle']");
        if (sw && sw.getAttribute('aria-checked') === 'true') {
            sw.click();
            return true;
        }
        // Fallback: tìm switch nằm trong container chứa label 'Restrict Key'
        const labels = Array.from(document.querySelectorAll('label, p, span'));
        for (const lbl of labels) {
            if (lbl.innerText && lbl.innerText.trim() === 'Restrict Key') {
                const parent = lbl.closest('div');
                if (parent) {
                    const sw2 = parent.querySelector("button[role='switch'][aria-checked='true']");
                    if (sw2) { sw2.click(); return true; }
                }
            }
        }
        return false;
    }""")
    if toggled:
        log_fn("  → Turned OFF 'Restrict Key' → Unrestricted")
        await page.wait_for_timeout(delay)
    else:
        log_fn("  ℹ️ Restrict Key toggle not found or already OFF")


async def _confirm_dialog(page: Page, log_fn: LogFn) -> None:
    confirmed = await page.evaluate("""() => {
        const btns = Array.from(document.querySelectorAll('button'));
        // Tìm "Create Key" button NGOẠI TRỪ các button trong header/nav (Create Key ở top bar)
        // Ưu tiên button nằm SAU Cancel button (trong footer của sheet/dialog)
        const cancel = btns.find(b => b.innerText.trim() === 'Cancel');
        if (cancel) {
            let next = cancel.nextElementSibling;
            while (next) {
                if (next.tagName === 'BUTTON') { next.click(); return next.innerText.trim(); }
                next = next.nextElementSibling;
            }
            // Nếu không có sibling, tìm trong cùng parent
            const parent = cancel.parentElement;
            if (parent) {
                const sibBtns = Array.from(parent.querySelectorAll('button'));
                const idx = sibBtns.indexOf(cancel);
                if (idx >= 0 && idx + 1 < sibBtns.length) {
                    sibBtns[idx + 1].click();
                    return sibBtns[idx + 1].innerText.trim();
                }
            }
        }
        // Last resort: tìm "Create Key" button - lấy cái CUỐI CÙNG (sheet footer, không phải nav)
        const createBtns = btns.filter(b => b.innerText.trim().toLowerCase() === 'create key');
        if (createBtns.length > 0) {
            const btn = createBtns[createBtns.length - 1];
            btn.click();
            return btn.innerText.trim();
        }
        return null;
    }""")
    if confirmed:
        log_fn(f"  → Confirmed: '{confirmed}'")
    else:
        log_fn("  ⚠️ Confirm button not found in dialog")


async def _extract_api_key(page: Page, api_key_regex: str, log_fn: LogFn) -> str:
    key: str = await page.evaluate(f"""() => {{
        for (const el of document.querySelectorAll('input')) {{
            if (el.value && el.value.startsWith('sk_')) return el.value;
        }}
        const m = document.body.innerText.match(/{api_key_regex}/);
        return m ? m[0] : '';
    }}""") or ""

    if key:
        log_fn(f"  ✅ API key: {key[:12]}...")
        return key
    raise RuntimeError("ElevenLabs API key not found on page — check debug/apikey_after_confirm.html")
