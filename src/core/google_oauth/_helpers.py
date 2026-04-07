"""
google_oauth/_helpers.py — Low-level pure helper functions.
Không chứa business logic, chỉ utilities.
"""
from __future__ import annotations

import logging
import pathlib
import time as _time
from collections.abc import Callable
from urllib.parse import urlparse

from playwright.async_api import (
    Page,
    TimeoutError as PlaywrightTimeoutError,
)

LogFn = Callable[[str], None]

_log = logging.getLogger(__name__)


def short_url(url: str) -> str:
    """Truncate URL: chỉ giữ path, bỏ query string dài."""
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc}{p.path}"


def emit_log(msg: str, log_fn: LogFn | None = None, prefix: str = "google") -> None:
    """Log helper dùng chung."""
    _log.info("[%s] %s", prefix, msg)
    if log_fn:
        log_fn(f"  [{prefix}] {msg}")


async def safe_wait(page: Page, ms: int = 2_000) -> None:
    """Wait for transition. Popup có thể đóng bất cứ lúc nào sau OAuth success."""
    from playwright._impl._errors import TargetClosedError
    try:
        await page.wait_for_timeout(ms)
    except TargetClosedError:
        _log.debug("[google] Page/popup closed during wait — OAuth likely succeeded")


async def wait_url_change(page: Page, *, timeout_ms: int = 15_000) -> str:
    """Đợi URL thay đổi so với hiện tại, trả về URL mới."""
    current = page.url
    try:
        await page.wait_for_url(
            lambda url: url != current,
            timeout=timeout_ms, wait_until="commit",
        )
    except PlaywrightTimeoutError:
        pass  # URL có thể không đổi nếu SPA, detect lại bằng state
    return page.url


async def dump_page_html(page: Page, label: str, log_fn: LogFn | None = None) -> None:
    """Dump HTML ra debug/ folder. Best-effort, không raise."""
    try:
        html = await page.content()
        debug_dir = pathlib.Path("debug")
        debug_dir.mkdir(exist_ok=True)
        path = debug_dir / f"google_{label}_{int(_time.time())}.html"
        path.write_text(html, encoding="utf-8")
        _log.debug("HTML dumped → %s (%d bytes)", path, len(html))
    except OSError as e:
        _log.debug("HTML dump failed: %s", e)
