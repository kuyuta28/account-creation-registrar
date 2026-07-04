"""add_cf_to_9router.py — Browser Gateway task: auto-add Cloudflare account vào 9Router.

9Router là service RIÊNG (tao chỉ dùng, không quản lý code). Mỗi task mở fresh
context camoufox — nếu navigate rơi vào /login thì fill pass rồi làm tiếp, không
thì fill form Add như thường (1 nhánh if xử lý 2 case thực tế, không fallback).

Flow: goto dashboard → login if needed → click Add → fill Name=email/API Key/Account ID
→ Check → đợi badge valid/invalid → Save nếu valid. Trả {ok, valid}.

DOM đã verify (Playwright rendered, 2026-07-04):
  - Login page (/login): input[placeholder="Enter password"] + button "Login"
  - Add button: <button>innerText "add\nAdd" (icon + text, không aria-label)
  - Panel: scope qua <h2>"Add Cloudflare API Key"> → ancestor div chứa input
    (form không có role=dialog)
  - Name: input[type=text][placeholder="Production Key"]
  - API Key: input[type=password] (trong panel, không placeholder)
  - Account ID: input[type=text][placeholder="abc123def456..."]
  - Check: button "Check" (disabled cho đến khi đủ 3 field)
  - Badge: <span> leaf text "Valid" (class text-green) / "Invalid" (class text-red)
  - Save: button "Save" (disabled cho đến khi Check = valid)
  - Cancel: button "Cancel"
"""
from __future__ import annotations

import re
from typing import Any

from playwright.async_api import Browser, Page

from ....core.google_oauth._helpers import LogFn
from ._registry import register  # noqa: F401  — side-effect: đăng ký task


_ADD_H2 = "Add Cloudflare API Key"


async def _scope_add_panel(page: Page):
    """Panel chứa form Add — scope qua H2 + ancestor div có input (không role=dialog)."""
    h2 = page.locator(f'h2:text-is("{_ADD_H2}")')
    return h2.locator('xpath=ancestor::div[.//input][1]')


async def _handle_login_if_needed(page: Page, password: str, log) -> None:
    """2 case thực tế: đã login (bỏ qua) hoặc rơi /login (fill pass). Không fallback."""
    if "/login" not in page.url:
        return
    log("  9Router: login page → fill password")
    pwd = page.locator('input[placeholder="Enter password"]')
    await pwd.wait_for(state="visible", timeout=10_000)
    await pwd.fill(password)
    await page.get_by_role("button", name="Login", exact=True).click()
    await page.wait_for_url(lambda u: "/login" not in u, timeout=15_000)


async def _open_add_form(page: Page, log) -> None:
    log("  9Router: mở form Add")
    # Nút Add = icon span "add" + text "Add" dính nhau (textContent "addAdd", không space).
    # XPath exact normalize-space để tránh khớp "Add Model" / "Bulk Add".
    add_btn = page.locator('xpath=//button[normalize-space()="addAdd"]').first
    await add_btn.wait_for(state="visible", timeout=10_000)
    await add_btn.click()
    await page.locator(f'h2:text-is("{_ADD_H2}")').wait_for(state="visible", timeout=10_000)


async def _wait_enabled(page: Page, locator, timeout_ms: int) -> None:
    """Đợi button enabled — wait_for(state=) không có 'enabled', poll is_enabled."""
    import asyncio as _aio
    deadline = _aio.get_event_loop().time() + timeout_ms / 1000
    while _aio.get_event_loop().time() < deadline:
        if await locator.is_enabled():
            return
        await _aio.sleep(0.15)
    raise TimeoutError(f"button không enabled sau {timeout_ms}ms")


async def _check_and_wait_badge(page: Page, panel, log) -> bool:
    log("  9Router: click Check, đợi badge...")
    check = panel.get_by_role("button", name="Check", exact=True)
    await _wait_enabled(page, check, 10_000)
    await check.click()
    # Badge = span leaf với text Valid/Invalid. Đợi xuất hiện (CF API ~1-5s).
    badge = panel.locator('span').filter(has_text=re.compile(r'^(Valid|Invalid)$')).first
    await badge.wait_for(state="visible", timeout=30_000)
    text = (await badge.inner_text()).strip().lower()
    valid = text == "valid"
    log(f"  9Router: badge = {text}")
    return valid


@register("add_cf_to_9router", engine="camoufox")
async def add_cf_to_9router(
    *, browser: Browser, args: dict[str, Any], log_fn: LogFn | None = None,
) -> dict[str, Any]:
    """Add 1 Cloudflare account vào 9Router dashboard.

    args: {"email": str, "api_key": str, "account_id": str}
    Trả về {"ok": True, "valid": bool}.
    """
    from ....config.settings import load_config

    email = args["email"]
    api_key = args["api_key"]
    account_id = args["account_id"]
    cfg = load_config()
    nine = cfg.ninerouter
    t = cfg.timeouts
    log = log_fn or (lambda m: None)

    log(f"[9Router] Add CF account {email}")
    ctx = await browser.new_context()
    try:
        page = await ctx.new_page()
        await page.goto(nine.dashboard_url, wait_until="domcontentloaded", timeout=t.page_load * 2)
        await _handle_login_if_needed(page, nine.password, log)
        # Sau login, gateway redirect về /dashboard chung → goto lại cloudflare-ai.
        if "/cloudflare-ai" not in page.url:
            await page.goto(nine.dashboard_url, wait_until="domcontentloaded", timeout=t.page_load * 2)
        await page.wait_for_timeout(t.nav_delay)

        await _open_add_form(page, log)
        panel = await _scope_add_panel(page)

        # Fill 3 field theo DOM đã verify. Name = email.
        await panel.locator('input[placeholder="Production Key"]').fill(email)
        await panel.locator('input[type="password"]').fill(api_key)
        await panel.locator('input[placeholder="abc123def456..."]').fill(account_id)
        log("  9Router: đã fill Name/API Key/Account ID")

        valid = await _check_and_wait_badge(page, panel, log)
        if not valid:
            return {"ok": True, "valid": False}

        # Save — chỉ khi valid (Save enable sau Check valid).
        save = panel.get_by_role("button", name="Save", exact=True)
        await _wait_enabled(page, save, 5_000)
        await save.click()
        # Panel đóng / form biến mất sau save.
        await page.locator(f'h2:text-is("{_ADD_H2}")').wait_for(state="hidden", timeout=15_000)
        log("  9Router: ✅ saved")
        return {"ok": True, "valid": True}
    finally:
        await ctx.close()
