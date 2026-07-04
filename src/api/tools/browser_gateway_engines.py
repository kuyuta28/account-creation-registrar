"""
browser_gateway_engines.py — Engine abstraction cho Browser Gateway (chạy trên host).

Mỗi engine trả về Playwright Browser (camoufox yield Browser Firefox; edge/chromium yield
Chromium). Automation code dùng Playwright API (page.locator, ctx.storage_state, ...) —
không đổi giữa engine.

Chỉ import trong gateway (host). Container không import module này.
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from typing import AsyncIterator

from playwright.async_api import Browser

_log = logging.getLogger("browser_gateway.engines")

ENGINES = ("camoufox", "edge", "chromium")

# Firefox prefs: tắt background throttling khi browser mất focus (giống common/browser.py).
_NO_THROTTLE_PREFS = {
    "dom.min_background_timeout_value": 0,
    "dom.min_timeout_value": 0,
    "dom.timeout.throttling_delay": 0,
    "dom.timeout.min_tracking_timeout_value": 0,
    "dom.timeout.min_tracking_origin_timeout_value": 0,
    "dom.suspend_inactive_tabs": False,
    "dom.browser_suspend_background_tabs": False,
    "browser.tab.delayedpaint": False,
    "dom.visibilityAPI.enabled": False,
    "layout.throttled_frame_rate": 0,
    "dom.requestAnimationFrame.sloppy": True,
    "dom.ipc.processPriorityManager.enabled": False,
    "dom.timeout.budget_throttling_max_delay": 0,
    "dom.workers.throttling.enabled": False,
    "gfx.frame-rate.background": 60,
    "widget.windows.window_occlusion_tracking.enabled": False,
    "toolkit.cosmeticAnimations.enabled": True,
}


def _screen_size() -> tuple[int, int]:
    """Kích thước monitor lớn nhất (logical px) qua screeninfo. Fallback 1920x1080."""
    try:
        from screeninfo import get_monitors
        m = max(get_monitors(), key=lambda m: m.width * m.height)
        if m.width > 0 and m.height > 0:
            return m.width, m.height
    except Exception:  # noqa: BLE001 — screeninfo fail → safe default
        pass
    return 1920, 1080


def _proxy_dict(proxy) -> dict | None:
    """ProxyConfig (common shape) → playwright proxy dict, hoặc None."""
    if not proxy or not getattr(proxy, "enabled", False) or not getattr(proxy, "server", ""):
        return None
    p: dict = {"server": proxy.server}
    if getattr(proxy, "username", ""):
        p["username"] = proxy.username
    if getattr(proxy, "password", ""):
        p["password"] = proxy.password
    return p


# Camoufox 0.4.11 có bug transient: đôi khi Firefox patched fail đọc config inject
# → "Failed to read the configuration file. Please contact your system administrator"
# (upstream issue #506, chưa fix). Hoặc launch hang tới timeout. Đây là lỗi launch tạm
# thời của chính camoufox, KHÔNG phải sai flow — retry lại cùng engine là cách xử lý đúng.
# Vẫn camoufox, không fallback. Timeout launch ngắn (60s) để retry nhanh, không kẹt slot.
_CAMOUFOX_LAUNCH_MAX_ATTEMPTS = 3
_CAMOUFOX_LAUNCH_TIMEOUT_MS = 60_000


def _camoufox_kwargs(*, headless: bool, proxy_dict: dict | None) -> dict:
    kwargs: dict = {"headless": headless, "os": "windows", "timeout": _CAMOUFOX_LAUNCH_TIMEOUT_MS}
    # Non-headless: set window = màn hình thật (qua screeninfo) + no-throttle prefs
    # để cửa sổ vừa khít desktop, không tràn ra ngoài, và không bị throttle background.
    if not headless:
        kwargs["window"] = _screen_size()
        kwargs["firefox_user_prefs"] = _NO_THROTTLE_PREFS
    if proxy_dict:
        kwargs["proxy"] = proxy_dict
    return kwargs


@asynccontextmanager
async def open_browser(engine: str, *, headless: bool, proxy=None) -> AsyncIterator[Browser]:
    """Mở browser theo engine, yield Playwright Browser.

    engine: "camoufox" | "edge" | "chromium"
    proxy:  ProxyConfig hoặc None
    """
    engine = (engine or "camoufox").lower()
    if engine not in ENGINES:
        raise ValueError(f"Unknown engine {engine!r}. Valid: {ENGINES}")

    proxy_dict = _proxy_dict(proxy)

    if engine == "camoufox":
        from camoufox.async_api import AsyncCamoufox
        kwargs = _camoufox_kwargs(headless=headless, proxy_dict=proxy_dict)
        ctx = None
        last_exc: Exception | None = None
        for attempt in range(1, _CAMOUFOX_LAUNCH_MAX_ATTEMPTS + 1):
            ctx = AsyncCamoufox(**kwargs)
            try:
                browser = await ctx.__aenter__()
                break  # launch OK
            except Exception as exc:  # noqa: BLE001 — camoufox launch transient failure
                last_exc = exc
                _log.warning(
                    "camoufox launch fail (attempt %d/%d): %s",
                    attempt, _CAMOUFOX_LAUNCH_MAX_ATTEMPTS, exc,
                )
                with suppress(Exception):
                    await ctx.__aexit__(type(exc), exc, exc.__traceback__)
                ctx = None
                if attempt < _CAMOUFOX_LAUNCH_MAX_ATTEMPTS:
                    await asyncio.sleep(1.0)
        else:
            assert last_exc is not None
            raise last_exc
        try:
            yield browser
        finally:
            await ctx.__aexit__(None, None, None)
        return

    # edge | chromium — plain playwright (patchright có error class riêng, không khớp
    # với playwright.async_api.TimeoutError mà automation code đang catch → crash).
    # Edge channel qua playwright Chromium vẫn là Edge thật, đủ cho Google login.
    from playwright.async_api import async_playwright
    async with async_playwright() as pw:
        launch_kwargs: dict = {"headless": headless}
        if engine == "edge":
            launch_kwargs["channel"] = "msedge"
        if proxy_dict:
            launch_kwargs["proxy"] = proxy_dict
        browser = await pw.chromium.launch(**launch_kwargs)
        try:
            yield browser
        finally:
            await browser.close()
