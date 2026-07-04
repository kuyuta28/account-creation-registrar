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

from ....config.settings import NineRouterConfig
from ....core.google_oauth._helpers import LogFn
from ._registry import register  # noqa: F401  — side-effect: đăng ký task


async def _scope_add_panel(page: Page, nine: NineRouterConfig):
    """Panel chứa form Add — scope qua H2 + ancestor div có input (không role=dialog)."""
    h2 = page.locator(f'h2:text-is("{nine.add_panel_h2}")')
    return h2.locator('xpath=ancestor::div[.//input][1]')


async def _handle_login_if_needed(page: Page, nine: NineRouterConfig, log) -> None:
    """2 case thực tế: đã login (bỏ qua) hoặc rơi /login (fill pass). Không fallback."""
    if nine.login_path not in page.url:
        return
    log("  9Router: login page → fill password")
    pwd = page.locator(nine.login_password_selector)
    await pwd.wait_for(state="visible", timeout=nine.login_password_visible_timeout_ms)
    await pwd.fill(nine.password)
    await page.get_by_role("button", name=nine.login_button_text, exact=True).click()
    await page.wait_for_url(lambda u: nine.login_path not in u, timeout=nine.login_redirect_timeout_ms)


async def _open_add_form(page: Page, nine: NineRouterConfig, log) -> None:
    log("  9Router: mở form Add")
    # Nút Add = icon span "add" + text "Add" dính nhau (textContent "addAdd", không space).
    # XPath exact normalize-space để tránh khớp "Add Model" / "Bulk Add".
    add_btn = page.locator(nine.add_button_xpath).first
    await add_btn.wait_for(state="visible", timeout=nine.add_button_visible_timeout_ms)
    await add_btn.click()
    await page.locator(f'h2:text-is("{nine.add_panel_h2}")').wait_for(
        state="visible", timeout=nine.add_panel_visible_timeout_ms,
    )


async def _wait_enabled(page: Page, locator, timeout_ms: int, poll_interval_ms: int) -> None:
    """Đợi button enabled — wait_for(state=) không có 'enabled', poll is_enabled."""
    import asyncio as _aio
    deadline = _aio.get_event_loop().time() + timeout_ms / 1000
    while _aio.get_event_loop().time() < deadline:
        if await locator.is_enabled():
            return
        await _aio.sleep(poll_interval_ms / 1000)
    raise TimeoutError(f"button không enabled sau {timeout_ms}ms")


async def _check_and_wait_badge(page: Page, panel: Page, nine: NineRouterConfig, log) -> bool:
    log("  9Router: click Check, đợi badge...")
    check = panel.get_by_role("button", name=nine.check_button_text, exact=True)
    await _wait_enabled(page, check, nine.check_enable_timeout_ms, nine.button_enable_poll_interval_ms)
    await check.click()
    # Badge = span leaf với text Valid/Invalid. Đợi xuất hiện (CF API ~1-5s).
    badge_re = re.compile(rf'^({nine.badge_valid_text}|{nine.badge_invalid_text})$')
    badge = panel.locator('span').filter(has_text=badge_re).first
    await badge.wait_for(state="visible", timeout=nine.badge_visible_timeout_ms)
    text = (await badge.inner_text()).strip().lower()
    valid = text == nine.badge_valid_text.lower()
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
        await _handle_login_if_needed(page, nine, log)
        # Sau login, gateway redirect về /dashboard chung → goto lại target.
        if nine.target_path not in page.url:
            await page.goto(nine.dashboard_url, wait_until="domcontentloaded", timeout=t.page_load * 2)
        await page.wait_for_timeout(t.nav_delay)

        await _open_add_form(page, nine, log)
        panel = await _scope_add_panel(page, nine)

        # Fill 3 field theo DOM đã verify. Name = email.
        await panel.locator(nine.name_input_selector).fill(email)
        await panel.locator(nine.api_key_input_selector).fill(api_key)
        await panel.locator(nine.account_id_input_selector).fill(account_id)
        log("  9Router: đã fill Name/API Key/Account ID")

        valid = await _check_and_wait_badge(page, panel, nine, log)
        if not valid:
            return {"ok": True, "valid": False}

        # Save — chỉ khi valid (Save enable sau Check valid).
        save = panel.get_by_role("button", name=nine.save_button_text, exact=True)
        await _wait_enabled(page, save, nine.save_enable_timeout_ms, nine.button_enable_poll_interval_ms)
        await save.click()
        # Panel đóng / form biến mất sau save.
        await page.locator(f'h2:text-is("{nine.add_panel_h2}")').wait_for(
            state="hidden", timeout=nine.save_panel_hidden_timeout_ms,
        )
        log("  9Router: ✅ saved")
        return {"ok": True, "valid": True}
    finally:
        await ctx.close()
