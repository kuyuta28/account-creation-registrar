"""
services/twoslides/api_key.py
Pure function — navigate to /api, create a new API key, return the sk-2slides-... string.
"""
from __future__ import annotations

import re

from playwright.async_api import Page

from ...config.settings import AppConfig
from ..protocols import LogFn
from ...core.page_utils import safe_load, dump_debug_html as _dump_debug


async def get_credits_via_page(page: Page, log_fn: LogFn) -> int:
    """
    Lấy số credits còn lại bằng cách fetch /api/subscription từ browser context.
    Page phải đang ở trạng thái logged-in (có session cookie).
    Trả về 0 nếu không lấy được.
    """
    try:
        result = await page.evaluate("""
            async () => {
                const resp = await fetch('/api/subscription', {credentials: 'include'});
                if (!resp.ok) return null;
                return await resp.json();
            }
        """)
        if result and isinstance(result, dict):
            # API trả về: {"subscriptionCredits": N, "packageCredits": N, ...}
            total = (result.get("subscriptionCredits") or 0) + (result.get("packageCredits") or 0)
            if total > 0:
                log_fn(f"  [CREDITS] {total} credits remaining")
                return total
            # Fallback: tìm key nào chứa "credit"
            for key, val in result.items():
                if "credit" in key.lower() and isinstance(val, int | float) and val > 0:
                    log_fn(f"  [CREDITS] {val} credits remaining ({key})")
                    return int(val)
                if isinstance(val, dict):
                    for subkey, subval in val.items():
                        if "credit" in subkey.lower() and isinstance(subval, int | float) and subval > 0:
                            log_fn(f"  [CREDITS] {subval} credits remaining ({key}.{subkey})")
                            return int(subval)
        log_fn(f"  [CREDITS] subscription response: {result}")
    except Exception as exc:  # noqa: BLE001 - best-effort UI action - log and continue
        log_fn(f"  [CREDITS] Could not fetch: {exc}")
    return 0


async def create_api_key(page: Page, log_fn: LogFn, cfg: AppConfig) -> str:
    """
    Navigate to 2slides /api page → click API Keys tab → fill name → confirm → return sk-2slides-... string.

    Flow thực tế: sau khi vào tab "API Keys", form điền tên key đã hiện sẵn —
    không cần click nút "Create Key" trước. Điền tên xong rồi mới click Create.
    """
    t = cfg.timeouts
    url = cfg.twoslides.api_url
    log_fn(f"\n[API KEY] Navigating to {url}...")
    await page.goto(url, timeout=t.page_load * 2)
    await _safe_load(page, t.page_load)
    await page.wait_for_timeout(t.nav_delay)
    await _dump_debug(page, "2slides_api_page.html", cfg.debug_dir)

    # 1. Click "API Keys" tab
    await _click_api_keys_tab(page, log_fn)
    await page.wait_for_timeout(t.step_delay)
    await _dump_debug(page, "2slides_api_keys_tab.html", cfg.debug_dir)

    # 2. Điền tên key (form hiện sẵn luôn sau khi vào tab)
    import random as _random
    import string as _string
    label = "".join(_random.choices(_string.digits, k=10))
    await _fill_key_name(page, log_fn, label, t.short_delay)
    await page.wait_for_timeout(t.short_delay)

    # 3. Click Create
    await _confirm_create(page, log_fn)
    await page.wait_for_timeout(t.step_delay * 2)
    await _dump_debug(page, "2slides_api_after_confirm.html", cfg.debug_dir)

    # 5. Extract key
    key = await _extract_api_key(page, log_fn)
    log_fn(f"  [API KEY] Got key: {key[:30]}...")
    return key


# ── private helpers ───────────────────────────────────────────────────────────

async def _safe_load(page: Page, timeout: int) -> None:
    await safe_load(page, timeout)


async def _click_api_keys_tab(page: Page, log_fn: LogFn) -> None:
    """Click tab 'API Keys' (radix tabs UI) bằng Playwright locator."""
    try:
        tab = page.locator('[role="tab"]').filter(has_text="API Keys")
        if await tab.count() > 0:
            await tab.first.click()
            log_fn("  [API KEY] Switched to tab: 'API Keys'")
            return
    except Exception:  # noqa: BLE001 — best-effort optional UI action
        pass
    # Fallback: text-based
    try:
        await page.get_by_text("API Keys", exact=True).first.click()
        log_fn("  [API KEY] Switched to tab via text: 'API Keys'")
    except Exception:  # noqa: BLE001 - best-effort UI action - log and continue
        log_fn("  [API KEY] ⚠️ 'API Keys' tab not found")


async def _click_create_key(page: Page, log_fn: LogFn) -> None:
    """Click button tạo API key — dùng Playwright locator để trigger React state."""
    import re as _re
    # Ưu tiên tabpanel active, fallback toàn trang
    scope = page.locator('[role="tabpanel"][data-state="active"]')
    if await scope.count() == 0:
        scope = page

    keywords = ["create api key", "create key", "new api key", "new key", "add key", "generate key", "create new"]
    for kw in keywords:
        try:
            btn = scope.get_by_role("button", name=_re.compile(kw, _re.IGNORECASE))
            if await btn.count() > 0 and await btn.first.is_visible():
                await btn.first.click()
                log_fn(f"  [API KEY] Clicked create button: '{kw}'")
                return
        except Exception:  # noqa: BLE001 — best-effort optional UI action
            pass

    # Fallback: bất kỳ button nào có text '+'
    try:
        btn = scope.locator("button").filter(has_text="+")
        if await btn.count() > 0:
            await btn.first.click()
            log_fn("  [API KEY] Clicked create button: '+'")
            return
    except Exception:  # noqa: BLE001 — best-effort optional UI action
        pass

    log_fn("  [API KEY] ⚠️ No create key button found")


async def _is_name_input_visible(page: Page) -> bool:
    """Kiểm tra input điền tên key đã hiện sẵn chưa (không cần click create trước)."""
    try:
        inp = page.locator("input[placeholder*='name' i], input[placeholder*='key' i]").first
        return await inp.is_visible()
    except Exception:  # noqa: BLE001 - best-effort UI probe - returns safe default
        return False


async def _fill_key_name(page: Page, log_fn: LogFn, label: str, delay: int) -> None:
    try:
        inp = page.locator("input[placeholder*='name' i], input[placeholder*='key' i], input[type='text']").first
        if await inp.is_visible():
            await inp.fill(label)
            log_fn(f"  [API KEY] Filled key name: '{label}'")
            await page.wait_for_timeout(delay)
        else:
            log_fn("  [API KEY] Key name input not visible, skipping")
    except Exception as e:  # noqa: BLE001 - best-effort UI action - log and continue
        log_fn(f"  [API KEY] Key name fill skipped: {e}")


async def _confirm_create(page: Page, log_fn: LogFn) -> None:
    for label in ("Create", "Generate", "Confirm", "Save", "Submit", "OK"):
        try:
            btns = page.get_by_role("button", name=label)
            for i in range(await btns.count()):
                b = btns.nth(i)
                if await b.is_visible() and await b.is_enabled():
                    await b.click()
                    log_fn(f"  [API KEY] Confirmed with '{label}'")
                    return
        except Exception:  # noqa: BLE001 — best-effort optional UI action
            pass
    # JS fallback
    await page.evaluate("""() => {
        const labels = ['create', 'generate', 'confirm', 'save', 'submit', 'ok'];
        for (const btn of document.querySelectorAll('button')) {
            const t = btn.innerText.trim().toLowerCase();
            if (labels.some(l => t.includes(l))) { btn.click(); return; }
        }
    }""")


async def _extract_api_key(page: Page, log_fn: LogFn) -> str:
    """Extract sk-2slides-... key from page content."""
    content = await page.content()
    match = re.search(r"sk-2slides-[a-f0-9]{60,}", content)
    if match:
        return match.group(0)

    # Try visible text
    try:
        text = await page.inner_text("body")
        match = re.search(r"sk-2slides-[a-f0-9]{60,}", text)
        if match:
            return match.group(0)
    except Exception:  # noqa: BLE001 - best-effort optional UI action
        pass

    # Try input values
    key_val = await page.evaluate("""() => {
        for (const el of document.querySelectorAll('input, textarea')) {
            const v = (el.value || '').trim();
            if (v.startsWith('sk-2slides-')) return v;
        }
        return null;
    }""")
    if key_val:
        return key_val

    log_fn("  [API KEY] ⚠️ Could not extract API key from page")
    raise RuntimeError("2slides API key not found on page after creation")
