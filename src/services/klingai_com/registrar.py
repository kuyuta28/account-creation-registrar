"""
klingai/registrar.py — Lưu Playwright session sau khi user login Google thủ công.

Flow:
  1. Mở browser (non-headless)
  2. Vào klingai.com → click "Sign in"
  3. User tự login Google
  4. Detect dashboard → extract email từ page
  5. Lưu storage_state (cookies) vào DB (session_state column)
  6. Upsert record vào DB
"""
from __future__ import annotations

import time

from playwright.async_api import Page

from ...config.settings import AppConfig
from ...core.browser import open_browser
from ...core.database import init_db
from ...core.storage import AccountRecord, Repo, db_path, repo_save
from ..protocols import LogFn


async def _is_logged_in(page: Page, app_url_contains: str) -> bool:
    """Detect khi user đã login xong — userId != 0 trong localStorage."""
    if app_url_contains not in page.url:
        return False
    if "login" in page.url or "sign-in" in page.url or "signin" in page.url:
        return False
    try:
        user_str = await page.evaluate("() => localStorage.getItem('user')")
        if user_str:
            import json
            user = json.loads(user_str)
            if int(user.get("userId", 0)) != 0:
                return True
    except Exception:  # noqa: BLE001 - best-effort optional UI action
        pass
    return False


async def _extract_email(page: Page) -> str:
    """Thử lấy email từ page. Trả về empty string nếu không tìm được."""
    try:
        for key in ("email", "userEmail", "user_email"):
            val = await page.evaluate(f"() => localStorage.getItem('{key}')")
            if val and "@" in str(val):
                return str(val).strip()

        cookies = await page.context.cookies()
        for c in cookies:
            if c.get("name", "").lower() in ("email", "user_email") and "@" in c.get("value", ""):
                return c["value"].strip()

        for sel in (
            "[data-testid='user-email']",
            "[class*='email']",
            "[class*='profile'] span",
            "[class*='user'] span",
        ):
            try:
                el = page.locator(sel).first
                if await el.is_visible(timeout=500):
                    txt = await el.inner_text()
                    if "@" in txt:
                        return txt.strip()
            except Exception:  # noqa: BLE001 - best-effort optional UI action
                pass
    except Exception:  # noqa: BLE001 - best-effort optional UI action
        pass
    return ""


async def save_session(
    cfg: AppConfig,
    log_fn: LogFn,
    repo: Repo,
    gmail_hint: str = "",
) -> AccountRecord | None:
    """
    Mở browser, đợi user login Google vào Kling AI, lưu session vào DB.
    gmail_hint: nếu biết trước email, truyền vào để định danh account.
    """
    kling = cfg.klingai

    captured_email: list[str] = []

    async with open_browser(cfg, headless=False) as browser:
        ctx = await browser.new_context()

        async def _on_response(response):
            if captured_email:
                return
            url = response.url
            if not any(k in url for k in ("/user/info", "/user/me", "/api/user", "/account/info", "/profile")):
                return
            try:
                body = await response.json()
                def _find_email(obj):
                    if isinstance(obj, dict):
                        for k, v in obj.items():
                            if k.lower() in ("email", "mail") and isinstance(v, str) and "@" in v:
                                return v
                            result = _find_email(v)
                            if result:
                                return result
                    elif isinstance(obj, list):
                        for item in obj:
                            result = _find_email(item)
                            if result:
                                return result
                    return None
                found = _find_email(body)
                if found:
                    captured_email.append(found)
                    log_fn(f"  [auto] Email detected: {found}")
            except Exception as e:  # noqa: BLE001 - best-effort UI action - log and continue
                log_fn(f"  [auto] Response parse error: {e}")

        ctx.on("response", _on_response)
        page = await ctx.new_page()

        log_fn(f"\n[Kling AI] Mở trang đăng nhập: {kling.login_url}")
        await page.goto(kling.login_url, timeout=cfg.timeouts.page_load * 3)
        await page.wait_for_load_state("domcontentloaded", timeout=cfg.timeouts.page_load)

        log_fn("\n" + "=" * 50)
        log_fn("  Hãy đăng nhập Kling AI bằng Google trên browser.")
        log_fn(f"  Bạn có {kling.login_timeout_sec}s để hoàn thành.")
        log_fn("=" * 50)

        deadline = time.monotonic() + kling.login_timeout_sec
        logged_in = False
        while time.monotonic() < deadline:
            await page.wait_for_timeout(1500)
            if await _is_logged_in(page, kling.app_url_contains):
                logged_in = True
                break

        if not logged_in:
            log_fn("[ERROR] Hết thời gian chờ login.")
            return None

        await page.wait_for_timeout(kling.post_login_wait_ms)
        log_fn(f"[OK] Login thành công! URL: {page.url}")

        email = (
            gmail_hint.strip()
            or (captured_email[0] if captured_email else "")
            or await _extract_email(page)
            or f"kling_user_{int(time.time())}"
        )

        # Lưu session vào DB
        _db = db_path(cfg.base_dir)
        init_db(_db)
        record = AccountRecord(
            service="KLINGAI",
            email=email,
            password="",
            api_key="",
        )
        repo_save(repo, record)
        await save_session(_db, "KLINGAI", email, ctx)
        log_fn(f"[OK] Session đã lưu vào DB cho: {email}")

        try:
            await ctx.close()
        except Exception:  # noqa: BLE001 — best-effort optional UI action
            pass

        return record
