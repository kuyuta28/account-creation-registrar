"""
debug_aa_edit.py — Browser Gateway debug task: khảo sát AA Image Editing API.

Không đoán AA API. Task này:
1. Load AA account session → mở Image Lab.
2. Bật network capture.
3. Switch sang tab Image Editing (click tab thật).
4. Dump tất cả network request (URL + method + status + post-data).
5. Dump HTML sau khi switch tab.

Trả về {"requests": [...], "html": "..."} để inspect, code edit-image dựa trên
request thật (upload endpoint + generate payload với sourceImageId).
"""
from __future__ import annotations

import json
from typing import Any

from playwright.async_api import Browser, Error as PlaywrightError

from ....core.google_oauth._helpers import LogFn
from ._registry import register  # noqa: F401


@register("debug_aa_edit", engine="camoufox")
async def debug_aa_edit(
    *, browser: Browser, args: dict[str, Any], log_fn: LogFn | None = None,
) -> dict[str, Any]:
    email = args["email"]
    log_lines: list[str] = []
    def log(m: str) -> None:
        log_lines.append(m)
        if log_fn:
            log_fn(m)

    from common.database._async import get_accounts_async
    from common.database._engine import get_async_session
    from ....config.settings import load_config

    cfg = load_config()
    aa_cfg = cfg.artificialanalysis

    async with get_async_session() as session:
        rows = await get_accounts_async(session, "ARTIFICIALANALYSIS")
    account = next((r for r in rows if r.get("email") == email), None)
    if not account:
        raise RuntimeError(f"Không tìm thấy AA account {email}")
    state = json.loads(account["session_state"])

    ctx = await browser.new_context(storage_state=state)
    captured: list[dict[str, Any]] = []

    page = await ctx.new_page()

    def _on_request(req):
        if req.method == "GET":
            return
        captured.append({
            "method": req.method,
            "url": req.url,
            "post_data": (req.post_data or "")[:2000],
            "resource_type": req.resource_type,
        })

    page.on("request", _on_request)
    page.on("response", lambda r: None)  # keep response ref alive

    log(f"[1] goto {aa_cfg.image_lab_url}")
    await page.goto(aa_cfg.image_lab_url, wait_until="networkidle", timeout=cfg.timeouts.page_load * 3)
    await page.wait_for_timeout(2_000)
    log(f"    url after goto: {page.url}")
    if "/login" in page.url:
        raise RuntimeError(f"Session {email} expired")

    log("[2] dump inputs (lab page)")
    inputs = await page.evaluate("""() => {
        const out = [];
        document.querySelectorAll('input, textarea, [role=button], button, [role=tab]').forEach(el => {
            out.push({
                tag: el.tagName,
                type: el.type || el.getAttribute('type') || null,
                role: el.getAttribute('role'),
                name: el.name || null,
                accept: el.accept || null,
                text: (el.textContent || '').trim().slice(0, 60),
                placeholder: el.placeholder || null,
                aria: el.getAttribute('aria-label') || null,
            });
        });
        return out;
    }""")
    log(f"    {len(inputs)} inputs")

    # Click "Image Editing" toggle (text exact, không phải "Image Editing Leaderboard").
    log("[3] click Image Editing toggle")
    try:
        # Ưu tiên button/div có text exact "Image Editing".
        clicked = await page.evaluate("""() => {
            const els = Array.from(document.querySelectorAll('button, div, a, span'));
            const t = els.find(e => (e.textContent||'').trim() === 'Image Editing');
            if (t) { t.click(); return true; }
            return false;
        }""")
        log(f"    clicked={clicked}")
    except PlaywrightError as exc:
        log(f"    click failed: {exc}")
    await page.wait_for_timeout(3_000)

    log("[4] dump inputs after edit toggle")
    inputs = await page.evaluate("""() => {
        const out = [];
        document.querySelectorAll('input, textarea, [role=button], button').forEach(el => {
            out.push({
                tag: el.tagName,
                type: el.type || el.getAttribute('type') || null,
                role: el.getAttribute('role'),
                name: el.name || null,
                accept: el.accept || null,
                text: (el.textContent || '').trim().slice(0, 60),
                placeholder: el.placeholder || null,
                aria: el.getAttribute('aria-label') || null,
            });
        });
        return out;
    }""")
    log(f"    {len(inputs)} inputs after edit")

    # Upload 1 ảnh test (1x1 PNG) vào input[type=file] để bắt upload endpoint.
    log("[5] upload test image to capture upload API")
    import base64
    import tempfile
    import os as _os
    # 1x1 red PNG (67 bytes).
    png_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
    tmp = _os.path.join(tempfile.gettempdir(), "aa_edit_test.png")
    with open(tmp, "wb") as f:
        f.write(base64.b64decode(png_b64))

    responses: list[dict] = []
    def _on_response(resp):
        if resp.request.method == "GET":
            return
        try:
            body = resp.text()[:1500] if resp.request.resource_type in ("xhr", "fetch", "document") else ""
        except PlaywrightError:
            body = ""
        responses.append({
            "method": resp.request.method,
            "url": resp.url,
            "status": resp.status,
            "request_body": (resp.request.post_data or "")[:1500],
            "response_body": body,
        })
    page.on("response", _on_response)

    try:
        file_input = page.locator('input[type=file]').first
        await file_input.set_input_files(tmp)
        log("    file set, waiting for upload network...")
        await page.wait_for_timeout(3_000)
    except PlaywrightError as exc:
        log(f"    upload failed: {exc}")

    # Fill prompt + click Generate để bắt generate-edit request (chứa image).
    log("[6] fill prompt + click Generate")
    try:
        await page.locator('textarea').first.fill("add a hat", timeout=5_000)
        # Tìm "Start Generation" button (text = "Start Generation⌘↵").
        gen_btn = page.get_by_role("button", name="Start Generation")
        count = await gen_btn.count()
        log(f"    start-gen buttons found: {count}")
        if count > 0:
            await gen_btn.first.click(timeout=5_000)
            log("    clicked start generation")
        await page.wait_for_timeout(12_000)
    except PlaywrightError as exc:
        log(f"    generate failed: {exc}")

    html = await page.content()
    log(f"[7] done. captured {len(captured)} reqs, {len(responses)} responses.")

    # Dump full HTML ra file để inspect offline (tìm upload input, edit toggle).
    import os
    dump_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "logs", "debug_aa_edit.html")
    with open(dump_path, "w", encoding="utf-8") as f:
        f.write(html)
    log(f"    html dumped to logs/debug_aa_edit.html ({len(html)} bytes)")

    return {
        "url": page.url,
        "logs": log_lines,
        "inputs": inputs[:60],
        "requests": captured,
        "responses": responses,
        "html_len": len(html),
        "html_head": html[:4000],
    }
