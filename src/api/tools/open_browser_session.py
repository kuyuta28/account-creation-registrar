"""
open_browser_session.py - Mo browser Playwright voi session_state da luu trong DB.

Chay nhu subprocess doc lap, doi nguoi dung dong browser roi exit.

Usage:
  python -m src.api.tools.open_browser_session <service> <email> [url]

  service = ten service (OPENROUTER, ELEVENLABS, ...) hoac "GMAIL" cho Gmail mailboxes.
  email   = email cua account/mailbox.
  url     = (optional) URL mo khi khoi dong. Default tuy theo service.
"""
from __future__ import annotations

import asyncio
import json
import logging
import sys
import traceback
import warnings
from pathlib import Path

from common.database._async import (
    get_account_by_email_async,
    get_mailbox_record_async,
)
from common.database._engine import get_async_session, init_async_db

# Playwright trên Windows emit "coroutine 'Waiter.reject_on_timeout...' was never awaited"
# khi event loop cleanup — đây là Playwright internal bug, không phải lỗi code ta.
# Suppress để tránh pollute all.log.
warnings.filterwarnings(
    "ignore",
    message=r"coroutine.*was never awaited",
    category=RuntimeWarning,
)

BASE_DIR = Path(__file__).parent.parent.parent.parent


def _load_cfg():
    """Load AppConfig — single source of truth cho base_dir, log_dir, db_path."""
    sys.path.insert(0, str(BASE_DIR))
    from src.config.settings import load_config
    return load_config()


def _get_log_dir() -> Path:
    return _load_cfg().log_dir

_DEFAULT_URLS: dict[str, str] = {
    "GMAIL": "https://mail.google.com",
    "_DEFAULT": "https://artificialanalysis.ai/image/image-lab",
}

_PREFS = {
    "dom.min_background_timeout_value": 0,
    "dom.suspend_inactive_tabs": False,
    "dom.browser_suspend_background_tabs": False,
}


def _setup_logger() -> logging.Logger:
    """Setup logger cho subprocess độc lập — mọi log đều vào all.log từ config (append)."""
    log_dir = _get_log_dir()
    log_dir.mkdir(parents=True, exist_ok=True)
    log = logging.getLogger("open_browser_session")
    log.setLevel(logging.DEBUG)
    fmt = logging.Formatter("[%(asctime)s] [%(levelname)-5s] [open_browser_session] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

    # Console (stdout) — để user thấy realtime nếu chạy tay
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.DEBUG)
    ch.setFormatter(fmt)
    log.addHandler(ch)

    # all.log — append, cùng file với main process để trace tập trung
    fh = logging.FileHandler(log_dir / "all.log", mode="a", encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    log.addHandler(fh)

    return log


async def _load_service_session(service: str, email: str, log: logging.Logger) -> dict:
    """Load session_state từ bảng accounts (async Postgres)."""
    log.debug("DB lookup: accounts WHERE service=%r AND email=%r", service, email)
    async with get_async_session() as session:
        record = await get_account_by_email_async(session, service, email)
    if not record:
        raise RuntimeError(f"Không tìm thấy account {service}/{email} trong DB")
    if not record.get("session_state"):
        raise RuntimeError(f"Account {service}/{email} tồn tại nhưng session_state = NULL/empty")
    data = json.loads(record["session_state"])
    cookies = data.get("cookies", [])
    log.info("Session loaded: %d cookies cho %s/%s", len(cookies), service, email)
    return data


async def _load_gmail_session(email: str, log: logging.Logger) -> dict:
    """Load google_auth_state từ mailboxes table (async Postgres)."""
    log.debug("DB lookup: mailboxes WHERE email=%r", email)
    async with get_async_session() as session:
        record = await get_mailbox_record_async(session, email)
    if not record:
        raise RuntimeError(f"Mailbox {email!r} không tìm thấy trong DB (mailboxes table)")
    state = record.get("google_auth_state")
    if not state:
        raise RuntimeError(f"Mailbox {email!r} chưa có Google session — chạy refresh-session trước")
    if isinstance(state, (bytes, bytearray)):
        state = state.decode("utf-8")
    data = json.loads(state)
    cookies = data.get("cookies", [])
    log.info("Gmail session loaded: %d cookies cho %s", len(cookies), email)
    return data


def load_session_sync(service: str, email: str, log: logging.Logger) -> dict:
    """Sync entry point — drives the async loader from a non-async caller
    without re-creating the event loop on every call."""
    if service.upper() == "GMAIL":
        return asyncio.run(_load_gmail_session(email, log))
    return asyncio.run(_load_service_session(service.upper(), email, log))


async def load_session(service: str, email: str, log: logging.Logger) -> dict:
    """Async entry point. Equivalent to load_session_sync but for async callers."""
    log.info("Loading session: service=%s email=%s", service, email)
    if service.upper() == "GMAIL":
        return await _load_gmail_session(email, log)
    return await _load_service_session(service.upper(), email, log)


async def main() -> None:
    log = _setup_logger()
    log.info("=" * 60)
    log.info("open_browser_session START — args: %s", sys.argv[1:])

    if len(sys.argv) < 3:
        log.error("Thiếu arguments. Usage: open_browser_session <service> <email> [url]")
        sys.exit(1)

    cfg = _load_cfg()
    if cfg.database.database_url:
        init_async_db(cfg.database.database_url)

    service = sys.argv[1]
    email = sys.argv[2]
    default_url = _DEFAULT_URLS.get(service.upper(), _DEFAULT_URLS["_DEFAULT"])
    url = sys.argv[3] if len(sys.argv) > 3 else default_url
    log.info("Target: service=%s email=%s url=%s", service, email, url)

    try:
        state = await load_session(service, email, log)
    except Exception:  # noqa: BLE001 - subprocess top-level: log then abort
        log.error("Không load được session:\n%s", traceback.format_exc())
        sys.exit(1)

    log.info("Khởi động Camoufox (headless=False, os=windows)...")
    try:
        from camoufox.async_api import AsyncCamoufox
        from screeninfo import get_monitors
    except ImportError as e:
        log.error("Thiếu dependency: %s — chạy: pip install camoufox screeninfo", e)
        sys.exit(1)

    # Lấy kích thước màn hình thực tế để fingerprint khớp với window thật
    monitor = max(get_monitors(), key=lambda m: m.width * m.height)
    win_w, win_h = monitor.width, monitor.height
    log.info("Monitor detected: %dx%d — set window=%s", win_w, win_h, (win_w, win_h))

    try:
        async with AsyncCamoufox(
            headless=False,
            os="windows",
            firefox_user_prefs=_PREFS,
            # window=(w,h) → fingerprint innerWidth/innerHeight khớp với actual window size
            # → page responsive khi resize vì không có fixed logical size mismatch
            window=(win_w, win_h),
        ) as browser:
            log.info("Browser launched, tạo context với storage_state...")
            # no_viewport=True → Playwright không inject fixed viewport lên context
            ctx = await browser.new_context(storage_state=state, no_viewport=True)
            page = await ctx.new_page()
            log.debug("new_page() OK")
            log.info("Navigating to %s ...", url)
            await page.goto(url, wait_until="domcontentloaded")
            log.info("page.goto() OK — trang đã load")
            log.info("Browser sẵn sàng cho %s/%s tại: %s", service, email, url)
            log.info("Đang chờ user đóng browser...")
            try:
                await asyncio.Event().wait()
            except (KeyboardInterrupt, asyncio.CancelledError):
                log.info("Nhận tín hiệu dừng — đóng browser")
    except Exception:  # noqa: BLE001 - subprocess top-level: log then abort
        log.error("Lỗi khi chạy browser:\n%s", traceback.format_exc())
        sys.exit(1)

    log.info("open_browser_session EXIT — %s/%s", service, email)


if __name__ == "__main__":
    asyncio.run(main())
