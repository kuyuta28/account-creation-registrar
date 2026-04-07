"""
page_utils.py — Shared Playwright page helpers (async).
Pure functions, no state.

Re-exports human mouse helpers từ human_mouse.py để các registrar
chỉ cần import 1 nơi:
  from ...core.page_utils import human_click_locator, human_click
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from playwright.async_api import Page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from .human_mouse import human_click, human_click_locator, human_move  # noqa: F401


async def safe_load(page: Page, timeout: int) -> None:
    """Wait for domcontentloaded, silently ignore timeout errors."""
    try:
        await page.wait_for_load_state("domcontentloaded", timeout=timeout)
    except (TimeoutError, PlaywrightTimeoutError):
        pass


async def safe_text(page: Page) -> str:
    """Get body inner text; return empty string on any error."""
    try:
        return await page.inner_text("body")
    except Exception:
        return ""


def _write_file(debug_dir: Path, name: str, content: str) -> None:
    debug_dir.mkdir(parents=True, exist_ok=True)
    (debug_dir / name).write_text(content, encoding="utf-8")


async def dump_debug_html(page: Page, name: str, debug_dir: Path) -> None:
    """Write current page HTML to debug_dir/<name>. Silent on error."""
    try:
        content = await page.content()
        await asyncio.to_thread(_write_file, debug_dir, name, content)
    except Exception:
        pass
