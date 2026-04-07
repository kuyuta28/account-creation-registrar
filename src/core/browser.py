"""
browser.py — Browser lifecycle helpers (camoufox).
open_browser() là điểm duy nhất trong codebase import AsyncCamoufox.
"""
from __future__ import annotations

import ctypes
import math
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from camoufox.async_api import AsyncCamoufox

from ..config.settings import AppConfig

Rect = tuple[int, int, int, int]  # x, y, width, height


_NO_THROTTLE_PREFS = {
    # Tắt background throttling khi browser mất focus / chạy background
    "dom.min_background_timeout_value": 0,
    "dom.min_timeout_value": 0,
    "dom.timeout.throttling_delay": 0,
    "dom.timeout.min_tracking_timeout_value": 0,
    "dom.timeout.min_tracking_origin_timeout_value": 0,
    "dom.suspend_inactive_tabs": False,
    "dom.browser_suspend_background_tabs": False,
    "browser.tab.delayedpaint": False,
    # Page Visibility API — ngăn Firefox chuyển sang "hidden" khi mất focus
    "dom.visibilityAPI.enabled": False,
    # Tắt throttle requestAnimationFrame khi background
    "layout.throttled_frame_rate": 0,
    "dom.requestAnimationFrame.sloppy": True,
    # Tắt process priority thay đổi khi background
    "dom.ipc.processPriorityManager.enabled": False,
    # Timer throttling
    "dom.timeout.budget_throttling_max_delay": 0,
    "dom.workers.throttling.enabled": False,
    # QUAN TRỌNG: Giữ frame rate khi window mất focus / bị occlude
    "gfx.frame-rate.background": 60,
    "widget.windows.window_occlusion_tracking.enabled": False,
    "toolkit.cosmeticAnimations.enabled": True,
}

@asynccontextmanager
async def open_browser(cfg: AppConfig, headless: bool | None = None) -> AsyncIterator:
    """Context manager duy nhất mở camoufox. Mọi registrar đều dùng cái này."""
    _headless = cfg.headless if headless is None else headless
    kwargs: dict = {
        "headless": _headless,
        "os": "windows",
        "firefox_user_prefs": _NO_THROTTLE_PREFS,
    }
    if cfg.proxy and cfg.proxy.server and cfg.proxy.enabled:
        proxy: dict = {"server": cfg.proxy.server}
        if cfg.proxy.username:
            proxy["username"] = cfg.proxy.username
        if cfg.proxy.password:
            proxy["password"] = cfg.proxy.password
        kwargs["proxy"] = proxy
    async with AsyncCamoufox(**kwargs) as browser:
        yield browser


def _screen_size() -> tuple[int, int]:
    """
    Kích thước màn hình trong LOGICAL pixels — đúng với hệ tọa độ Chrome
    dùng cho --window-position / --window-size.
    KHÔNG gọi SetProcessDPIAware() vì nó khiến GetSystemMetrics trả physical
    pixels trong khi Chrome dùng logical pixels → windows bị lệch.
    """
    try:
        user32 = ctypes.windll.user32
        w = user32.GetSystemMetrics(0)  # SM_CXSCREEN
        h = user32.GetSystemMetrics(1)  # SM_CYSCREEN
        if w > 0 and h > 0:
            return w, h
    except OSError:  # Windows API call failed — use safe default
        pass
    return 1920, 1080


def tile_rects(n: int) -> list[Rect]:
    """
    Chia màn hình thành n ô bằng nhau.
    n=1 → full screen
    n=2 → trái/phải
    n=3,4 → 2x2 grid
    n>4 → tự tính cols/rows
    """
    if n <= 1:
        w, h = _screen_size()
        return [(0, 0, w, h)]
    sw, sh = _screen_size()
    cols = math.ceil(math.sqrt(n))
    rows = math.ceil(n / cols)
    tw, th = sw // cols, sh // rows
    return [((i % cols) * tw, (i // cols) * th, tw, th) for i in range(n)]






