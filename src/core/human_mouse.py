"""
human_mouse.py — Human-like mouse movement cho Playwright dùng Bezier curves.

Thuật toán:
  - Cubic Bezier với 2 control points ngẫu nhiên → đường cong tự nhiên
  - Jitter nhỏ trên mỗi điểm → tay run nhẹ
  - Speed profile: accelerate → ease out (easing function)
  - Overshoot: di chuyển qua target 1 chút rồi quay lại

Public API:
  human_move(page, x, y)               → move chuột theo Bezier
  human_click(page, x, y)              → move + click
  human_click_locator(page, locator)   → resolve locator → human_click
"""
from __future__ import annotations

import asyncio
import math
import random
from typing import Literal

from playwright.async_api import Locator, Page

# ── Bezier helpers ─────────────────────────────────────────────────────────────

def _cubic_bezier(
    t: float,
    p0: tuple[float, float],
    p1: tuple[float, float],
    p2: tuple[float, float],
    p3: tuple[float, float],
) -> tuple[float, float]:
    """Cubic Bezier B(t) với 4 control points."""
    u = 1 - t
    x = u**3 * p0[0] + 3 * u**2 * t * p1[0] + 3 * u * t**2 * p2[0] + t**3 * p3[0]
    y = u**3 * p0[1] + 3 * u**2 * t * p1[1] + 3 * u * t**2 * p2[1] + t**3 * p3[1]
    return x, y


def _ease_in_out(t: float) -> float:
    """Smooth step: chậm ở đầu và cuối, nhanh ở giữa."""
    return t * t * (3 - 2 * t)


def _generate_bezier_path(
    x0: float, y0: float,
    x1: float, y1: float,
    steps: int = 40,
    jitter: float = 1.5,
) -> list[tuple[float, float]]:
    """
    Sinh path Bezier từ (x0,y0) → (x1,y1).
    Control points được đặt ngẫu nhiên để tạo đường cong tự nhiên.
    """
    dx = x1 - x0
    dy = y1 - y0

    # Control points: lệch ngẫu nhiên khỏi đường thẳng
    cp1 = (
        x0 + dx * random.uniform(0.2, 0.4) + random.uniform(-abs(dy) * 0.3, abs(dy) * 0.3),
        y0 + dy * random.uniform(0.2, 0.4) + random.uniform(-abs(dx) * 0.3, abs(dx) * 0.3),
    )
    cp2 = (
        x0 + dx * random.uniform(0.6, 0.8) + random.uniform(-abs(dy) * 0.3, abs(dy) * 0.3),
        y0 + dy * random.uniform(0.6, 0.8) + random.uniform(-abs(dx) * 0.3, abs(dx) * 0.3),
    )

    points: list[tuple[float, float]] = []
    for i in range(steps + 1):
        t = _ease_in_out(i / steps)
        x, y = _cubic_bezier(t, (x0, y0), cp1, cp2, (x1, y1))
        # Thêm jitter nhỏ (tay run)
        x += random.uniform(-jitter, jitter)
        y += random.uniform(-jitter, jitter)
        points.append((x, y))
    return points


# ── Public API ─────────────────────────────────────────────────────────────────

async def human_move(
    page: Page,
    x: float,
    y: float,
    steps: int | None = None,
    delay_ms: float | None = None,
) -> None:
    """
    Di chuyển chuột theo Bezier curve từ vị trí hiện tại đến (x, y).

    steps: số intermediate points (mặc định: tỉ lệ với khoảng cách)
    delay_ms: delay giữa các step (mặc định: random 3-8ms)
    """
    # Lấy vị trí chuột hiện tại qua JS
    cur = await page.evaluate("() => ({ x: window._hm_x || 0, y: window._hm_y || 0 })")
    x0, y0 = float(cur.get("x", 0)), float(cur.get("y", 0))

    dist = math.hypot(x - x0, y - y0)
    _steps = steps or max(20, int(dist / 8))
    _delay = delay_ms  # None = random per step

    path = _generate_bezier_path(x0, y0, x, y, steps=_steps)
    for px, py in path:
        await page.mouse.move(px, py)
        d = _delay if _delay is not None else random.uniform(3, 8)
        await asyncio.sleep(d / 1000)

    # Lưu vị trí cuối vào window để lần sau biết điểm xuất phát
    await page.evaluate(f"() => {{ window._hm_x = {x}; window._hm_y = {y}; }}")


async def human_click(
    page: Page,
    x: float,
    y: float,
    button: "Literal['left', 'middle', 'right']" = "left",
    hold_ms: float | None = None,
) -> None:
    """
    Move chuột đến (x, y) theo Bezier rồi click.
    hold_ms: giữ click bao lâu (ms). None = random 80-150ms
    """
    await human_move(page, x, y)
    # Pause ngắn trước khi click (reaction time)
    await asyncio.sleep(random.uniform(0.05, 0.12))
    _hold = (hold_ms or random.uniform(80, 150)) / 1000
    await page.mouse.down(button=button)
    await asyncio.sleep(_hold)
    await page.mouse.up(button=button)


async def human_click_locator(
    page: Page,
    locator: Locator,
    relative_x: float = 0.5,
    relative_y: float = 0.5,
    timeout: int = 10_000,
) -> None:
    """
    Resolve Playwright Locator → lấy bounding box → human_click vào điểm
    (relative_x, relative_y) bên trong element.

    relative_x/y: 0.0 = trái/trên, 1.0 = phải/dưới, 0.5 = center.
    """
    await locator.wait_for(state="visible", timeout=timeout)
    box = await locator.bounding_box()
    if box is None:
        raise RuntimeError(f"Cannot get bounding box for locator: {locator}")
    x = box["x"] + box["width"] * relative_x + random.uniform(-2, 2)
    y = box["y"] + box["height"] * relative_y + random.uniform(-2, 2)
    await human_click(page, x, y)
