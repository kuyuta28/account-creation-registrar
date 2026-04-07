"""
src/core/guard.py — Typed probe helpers thay thế `except Exception: continue`.

VẤN ĐỀ cũ:
    for loc in locators:
        try:
            await loc.wait_for(state="visible", timeout=3000)
            return loc   # found
        except Exception:   # ← BLE001: swallow toàn bộ, kể cả KeyboardInterrupt
            continue

VẤN ĐỀ: `except Exception` cũng catch MemoryError, SystemExit, KeyboardInterrupt (qua
BaseException subclasses KHÔNG phải Exception), nhưng quan trọng hơn: nó ẩn mọi lỗi
THẬT sự (network, DOM detached, v.v.) vì Playwright raise PlaywrightTimeoutError cho
"không tìm thấy" — chỉ cần catch đúng type đó.

SOLUTION: các helpers dưới đây chỉ catch đúng PlaywrightTimeoutError (locator probe)
hoặc TimeoutError (asyncio timeout). Các lỗi khác vẫn propagate.

DÙNG:
    # Thay `except Exception: continue`:
    if await try_locator(page.locator("button.submit")):
        await page.locator("button.submit").click()

    # Tìm locator đầu tiên trong danh sách:
    btn = await first_visible(page, ["button.submit", "input[type=submit]"])
    if btn is None:
        raise RuntimeError("Không tìm thấy submit button")
    await btn.click()
"""
from __future__ import annotations

from typing import Literal

from playwright.async_api import Locator, Page, TimeoutError as PlaywrightTimeoutError


async def try_locator(
    locator: Locator,
    *,
    state: "Literal['attached', 'detached', 'hidden', 'visible']" = "visible",
    timeout_ms: int = 3_000,
) -> bool:
    """
    Probe một locator — chỉ catch PlaywrightTimeoutError, KHÔNG swallow lỗi khác.

    Trả về True nếu locator đạt state mong muốn, False nếu timeout.
    Raise bất kỳ lỗi nào KHÔNG phải timeout (DOM error, browser crash, v.v.)
    """
    try:
        await locator.first.wait_for(state=state, timeout=timeout_ms)
        return True
    except PlaywrightTimeoutError:
        return False


async def first_visible(
    page: Page,
    selectors: list[str],
    *,
    timeout_ms: int = 3_000,
) -> Locator | None:
    """
    Tìm locator đầu tiên visible từ danh sách selectors.
    Trả None nếu không có cái nào visible trong timeout.
    """
    for sel in selectors:
        loc = page.locator(sel)
        if await try_locator(loc, timeout_ms=timeout_ms):
            return loc
    return None


async def click_first_visible(
    page: Page,
    selectors: list[str],
    *,
    timeout_ms: int = 3_000,
) -> bool:
    """
    Click locator đầu tiên visible. Trả True nếu click được, False nếu không có gì.
    Dùng khi click là best-effort (optional). Nếu click là bắt buộc, check return value.
    """
    loc = await first_visible(page, selectors, timeout_ms=timeout_ms)
    if loc is None:
        return False
    await loc.click()
    return True


async def try_close_popup(page: Page, *, timeout_ms: int = 2_000) -> None:
    """
    Thử đóng popup/dialog thường gặp (cookie consent, onboarding skip, v.v.)
    Silent nếu không có popup — đây là use case hợp lệ duy nhất cho best-effort.
    """
    close_selectors = [
        'button[aria-label*="close" i]',
        'button[aria-label*="dismiss" i]',
        'button:has-text("Skip")',
        'button:has-text("Later")',
        'button:has-text("No thanks")',
    ]
    await click_first_visible(page, close_selectors, timeout_ms=timeout_ms)
