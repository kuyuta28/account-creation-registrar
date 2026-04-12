"""
services/elevenlabs/onboarding.py
Pure function — no class state, no globals.
Takes page + injected deps, returns nothing (side-effect: advances page past onboarding).
"""
from __future__ import annotations

from playwright.async_api import Page

from ...config.settings import AppConfig
from common.page_utils import dump_debug_html as _dump_debug
from ..protocols import LogFn


async def handle_onboarding(page: Page, log_fn: LogFn, cfg: AppConfig) -> None:
    """
    Step through ElevenLabs onboarding until URL leaves /onboarding.
    Dumps HTML each step for debugging.
    """
    t = cfg.timeouts
    log_fn("  Handling onboarding...")

    for step in range(15):
        await page.wait_for_timeout(t.step_delay)

        if "onboarding" not in page.url:
            log_fn("  ✓ Onboarding complete")
            return

        await _dump_debug(page, f"onboarding_step_{step}.html", cfg.debug_dir)
        page_text = await page.inner_text("body")
        log_fn(f"  [step {step}] {page_text[:120].strip()!r}")

        await _maybe_click_age_checkbox(page, log_fn, t.click_delay)
        await _click_advance_button(page, log_fn, step)

    log_fn("  ⚠️ Onboarding may not be fully complete")


# ── private helpers ───────────────────────────────────────────────────────────

async def _maybe_click_age_checkbox(page: Page, log_fn: LogFn, click_delay: int) -> None:
    """Click the age-of-18 checkbox if present (JS click bypasses opacity:0 wrapper)."""
    if "age of 18" not in await page.inner_text("body"):
        return
    try:
        clicked = await page.evaluate("""() => {
            const cb = document.querySelector("button[role='checkbox']");
            if (cb && cb.getAttribute('data-state') === 'unchecked') {
                cb.click();
                return true;
            }
            return false;
        }""")
        log_fn(f"  → Age checkbox JS click: {clicked}")
        await page.wait_for_timeout(click_delay)
    except Exception as e:  # noqa: BLE001 - best-effort UI action - log and continue
        log_fn(f"  ⚠️ Checkbox error: {e}")


async def _click_advance_button(page: Page, log_fn: LogFn, step: int) -> None:
    """Click the first visible advance button in priority order."""
    for label in ("Continue", "Next", "Skip", "Get started", "Finish"):
        try:
            btns = page.get_by_role("button", name=label)
            for i in range(await btns.count()):
                b = btns.nth(i)
                if await b.is_visible() and await b.is_enabled():
                    await b.click()
                    log_fn(f"  → Clicked '{label}'")
                    return
        except Exception:  # noqa: BLE001 — best-effort optional UI action
            pass
    log_fn(f"  ⚠️ Step {step}: no advance button found")
