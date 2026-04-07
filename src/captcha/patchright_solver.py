"""
src/captcha/patchright_solver.py — Cloudflare Turnstile solver via patchright.

Dùng Chromium đã patch fingerprint. Navigate thẳng tới trang thật (có CF cookies
và JS environment thật) → Turnstile tự issue token.

Usage:
    token = await solve_turnstile_patchright_async(
        page_url="https://openrouter.ai/sign-up",
        site_key="0x4AAAAAAAWXJGBD7bONzLBd",
    )
"""
from __future__ import annotations

import asyncio
import time

from patchright.async_api import Page, async_playwright

_INJECT_JS = """\
(function () {
    'use strict';
    window.__patchright_tokens = [];
    const _orig = window.turnstile;
    function _wrap(obj) {
        if (!obj || obj.__patched) return obj;
        obj.__patched = true;
        const origRender = obj.render.bind(obj);
        obj.render = function(container, options) {
            const newCb = options && options.callback;
            if (newCb) {
                const wrapped = options.callback;
                options.callback = function(token) {
                    window.__patchright_tokens.push(token);
                    return wrapped(token);
                };
            }
            return origRender(container, options);
        };
    }
    if (_orig) {
        _wrap(_orig);
    }
    // intercept future window.turnstile assignments
    let _cached = window.turnstile;
    Object.defineProperty(window, 'turnstile', {
        get: () => _cached,
        set: (v) => { _wrap(v); _cached = v; },
        configurable: true,
    });
})();
"""


async def solve_turnstile_patchright_async(
    page_url: str,
    site_key: str,
    timeout: int = 60,
    action: str = "",
    cdata: str = "",
    headless: bool = True,
    viewport_width: int = 1280,
    viewport_height: int = 800,
    page_load_timeout_ms: int = 40_000,
    poll_interval_sec: float = 0.5,
) -> str:
    """
    Solve Cloudflare Turnstile bằng patchright bằng cách navigate tới trang thật.

    Cách hoạt động:
    - Navigate thẳng tới page_url (trang thật, có CF cookies đúng domain).
    - Inject JS hook để capture Turnstile callback token.
    - Poll đến khi có token, rồi trả về.

    Không cần API key, không credit.
    """
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=headless,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        try:
            ctx = await browser.new_context(
                locale="en-US",
                timezone_id="America/New_York",
                viewport={"width": viewport_width, "height": viewport_height},
            )
            await ctx.add_init_script(_INJECT_JS)
            page: Page = await ctx.new_page()

            await page.goto(page_url, wait_until="domcontentloaded", timeout=page_load_timeout_ms)

            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                tokens: list = await page.evaluate(
                    "() => window.__patchright_tokens || []"
                )
                if tokens:
                    return tokens[0]

                # check turnstile.getResponse()
                token: str = await page.evaluate(
                    "() => { try { return window.turnstile && window.turnstile.getResponse() || ''; } catch(e) { return ''; } }"
                )
                if token:
                    return token

                await asyncio.sleep(poll_interval_sec)

            raise RuntimeError(
                f"patchright Turnstile: timeout sau {timeout}s (url={page_url})"
            )
        finally:
            await browser.close()
