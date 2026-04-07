"""
image_lab.py — Artificial Analysis Image Lab automation.

Public API:
  run_image_lab(context, params, output_dir, log_fn) → list[Path]

DOM analysis (2026-03-23):
  - Prompt: textarea#prompt
  - Model checkboxes: [role="checkbox"], parentText = "#N\nModelName\nELO: ...\n$price/gen"
  - Clear all models: button "Clear"
  - Aspect ratio: button "1:1 (Square)" | "16:9 (Landscape)" | "9:16 (Portrait)" | "4:3" | "3:4"
  - Dimensions: button "512x512" | "768x768" | "1024x1024" | ... (changes by aspect ratio)
  - Generations: button "1x" (dropdown)
  - Start: button "Start Generation"
  - Download: download button per image (triggers browser download)
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from collections.abc import Callable

from playwright.async_api import BrowserContext

_IMAGE_LAB_URL = "https://artificialanalysis.ai/image/image-lab"

LogFn = Callable[[str], None]


@dataclass(frozen=True)
class ImageLabParams:
    prompt: str
    models: list[str]        # tên model chính xác, khớp với checkbox parentText
    aspect_ratio: str        # "1:1 (Square)" | "16:9 (Landscape)" | "9:16 (Portrait)" | "4:3" | "3:4"
    dimensions: str          # phải khớp button text sau khi chọn aspect ratio
    generations: int = 1     # số lần gen (button "1x" → chọn "Nx")


class SessionExpiredError(RuntimeError):
    pass


class GenerationFailedError(RuntimeError):
    pass


# ── Step helpers ─────────────────────────────────────────────────────────────

async def _verify_logged_in(page, log_fn: LogFn) -> None:
    """Raise SessionExpiredError nếu bị redirect về login."""
    await page.goto(_IMAGE_LAB_URL, wait_until="domcontentloaded")
    await page.wait_for_timeout(3000)
    if "/login" in page.url:
        raise SessionExpiredError("Session expired — redirect về login")
    log_fn(f"  Logged in: {page.url}")


async def _clear_models(page, log_fn: LogFn) -> None:
    """Uncheck tất cả model bằng nút Clear."""
    clear_btn = page.locator("button", has_text="Clear")
    await clear_btn.click()
    await page.wait_for_timeout(500)
    log_fn("  Cleared all models")


def _extract_model_name(parent_text: str) -> str:
    """
    Parse model name từ checkbox parentText.
    Format: "#1\nGPT Image 1.5 (high)\nELO: 1266\n$0.252/gen"
    → "GPT Image 1.5 (high)"
    """
    lines = [ln.strip() for ln in parent_text.strip().split("\n") if ln.strip()]
    # Bỏ dòng đầu "#N" và các dòng ELO / price
    for line in lines:
        if not line.startswith("#") and not line.startswith("ELO:") and not line.startswith("$"):
            return line
    return parent_text.strip()


async def _select_models(page, models: list[str], log_fn: LogFn) -> None:
    """
    Clear tất cả rồi check đúng các model trong danh sách.
    So sánh case-insensitive, strip whitespace.
    """
    await _clear_models(page, log_fn)

    want = {m.strip().lower() for m in models}
    checkboxes = page.locator('[role="checkbox"]')
    count = await checkboxes.count()

    selected = []
    for i in range(count):
        cb = checkboxes.nth(i)
        parent_text = await cb.evaluate(
            "el => (el.closest('label') || el.parentElement || {}).innerText || ''"
        )
        model_name = _extract_model_name(parent_text)
        if model_name.strip().lower() in want:
            state = await cb.get_attribute("data-state")
            if state != "checked":
                await cb.click()
                await page.wait_for_timeout(200)
            selected.append(model_name)

    if not selected:
        raise RuntimeError(f"Không tìm thấy model nào trong danh sách: {models}")
    log_fn(f"  Selected models: {selected}")


async def _set_aspect_ratio(page, aspect_ratio: str, log_fn: LogFn) -> None:
    """Click nút aspect ratio."""
    btn = page.locator("button", has_text=aspect_ratio).first
    await btn.click()
    await page.wait_for_timeout(400)
    log_fn(f"  Aspect ratio: {aspect_ratio}")


async def _set_dimensions(page, dimensions: str, log_fn: LogFn) -> None:
    """Click nút dimensions (xuất hiện sau khi chọn aspect ratio)."""
    btn = page.locator("button", has_text=dimensions).first
    await btn.click()
    await page.wait_for_timeout(400)
    log_fn(f"  Dimensions: {dimensions}")


async def _set_generations(page, generations: int, log_fn: LogFn) -> None:
    """
    Chọn số lần gen — click button '1x' rồi chọn option.
    Chỉ thực hiện nếu generations != 1.
    """
    if generations == 1:
        return
    gen_btn = page.locator("button", has_text="x").first
    await gen_btn.click()
    await page.wait_for_timeout(500)
    # Chọn option trong dropdown/popover
    option = page.locator(f'[role="option"]:has-text("{generations}x"), [role="menuitem"]:has-text("{generations}x")')
    await option.first.click()
    await page.wait_for_timeout(300)
    log_fn(f"  Generations: {generations}x")


async def _fill_prompt(page, prompt: str, log_fn: LogFn) -> None:
    """Fill prompt vào textarea."""
    ta = page.locator("textarea#prompt")
    await ta.fill(prompt)
    await page.wait_for_timeout(300)
    log_fn(f"  Prompt: {prompt[:60]}{'...' if len(prompt) > 60 else ''}")


async def _start_generation(page, log_fn: LogFn) -> None:
    """Click Start Generation — raise nếu button vẫn disabled."""
    start_btn = page.locator("button:has-text('Start Generation')").first
    is_disabled = await start_btn.is_disabled()
    if is_disabled:
        raise GenerationFailedError("Start Generation button vẫn disabled — kiểm tra prompt và models")
    await start_btn.click()
    log_fn("  Clicked Start Generation")


async def _count_existing_downloads(page) -> int:
    """Đếm số nút download hiện có trong history panel."""
    return await page.evaluate("""() => {
        return document.querySelectorAll('[aria-label="Download"], [title="Download"], svg[data-lucide="download"]').length;
    }""")


async def _wait_for_new_images(page, initial_count: int, model_count: int, timeout_sec: int, log_fn: LogFn) -> None:
    """
    Chờ cho đến khi số download buttons tăng thêm ít nhất model_count so với initial_count.
    """
    deadline = asyncio.get_event_loop().time() + timeout_sec
    log_fn(f"  Waiting for {model_count} image(s) (initial downloads: {initial_count})...")

    while asyncio.get_event_loop().time() < deadline:
        current = await _count_existing_downloads(page)
        new_count = current - initial_count
        if new_count >= model_count:
            log_fn(f"  ✅ {new_count} image(s) generated")
            return
        log_fn(f"  ... {new_count}/{model_count} ready")
        await page.wait_for_timeout(3000)

    raise GenerationFailedError(f"Timeout {timeout_sec}s — ảnh không xuất hiện")


async def _download_new_images(
    page,
    initial_count: int,
    output_dir: Path,
    log_fn: LogFn,
) -> list[Path]:
    """
    Tìm tất cả download buttons mới (index >= initial_count) và download.
    Download buttons được Playwright capture qua expect_download().
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Lấy tất cả download buttons hiện tại
    download_btns = page.locator('[aria-label="Download"], [title="Download"]')
    total = await download_btns.count()

    new_btns = list(range(initial_count, total))
    if not new_btns:
        raise GenerationFailedError("Không tìm thấy download button nào mới")

    paths: list[Path] = []
    for idx, btn_idx in enumerate(new_btns):
        btn = download_btns.nth(btn_idx)
        out_path = output_dir / f"image_{idx:02d}.png"
        async with page.expect_download() as download_info:
            await btn.click()
        download = await download_info.value
        await download.save_as(str(out_path))
        paths.append(out_path)
        log_fn(f"  Downloaded: {out_path.name}")

    return paths


# ── Public API ────────────────────────────────────────────────────────────────

async def run_image_lab(
    context: BrowserContext,
    params: ImageLabParams,
    output_dir: Path,
    log_fn: LogFn,
    generation_timeout_sec: int = 300,
) -> list[Path]:
    """
    Login với context đã có session, gen ảnh theo params, download về output_dir.
    Raise SessionExpiredError nếu session hết hạn.
    Raise GenerationFailedError nếu gen thất bại.
    """
    page = await context.new_page()
    try:
        log_fn("[1] Verify session...")
        await _verify_logged_in(page, log_fn)

        log_fn("[2] Select models...")
        await _select_models(page, params.models, log_fn)

        log_fn("[3] Set aspect ratio & dimensions...")
        await _set_aspect_ratio(page, params.aspect_ratio, log_fn)
        await _set_dimensions(page, params.dimensions, log_fn)

        if params.generations != 1:
            log_fn("[4] Set generations...")
            await _set_generations(page, params.generations, log_fn)

        log_fn("[5] Fill prompt...")
        await _fill_prompt(page, params.prompt, log_fn)

        initial_count = await _count_existing_downloads(page)

        log_fn("[6] Start generation...")
        await _start_generation(page, log_fn)

        log_fn("[7] Waiting for images...")
        expected = len(params.models) * params.generations
        await _wait_for_new_images(page, initial_count, expected, generation_timeout_sec, log_fn)

        log_fn("[8] Downloading images...")
        paths = await _download_new_images(page, initial_count, output_dir, log_fn)

        return paths
    finally:
        await page.close()
