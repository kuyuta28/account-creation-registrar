"""run_image_lab_one.py — Browser Gateway task: gen ảnh Image Lab cho 1 AA account.

Chạy trên host (gateway mở camoufox). KHÔNG trong container. Container gọi
run_browser_task("run_image_lab_one") per-account (batch concurrent ở container).

Flow: load session_state → new_context(storage_state) → run_image_lab →
download ảnh vào tmp dir → đọc base64 → trả về. Container ghi ảnh ra output_dir.
"""
from __future__ import annotations

import base64
import tempfile
from pathlib import Path
from typing import Any

from playwright.async_api import Browser

from ....core.google_oauth._helpers import LogFn
from ._registry import register  # noqa: F401  — side-effect: đăng ký task


@register("run_image_lab_one", engine="camoufox")
async def run_image_lab_one(
    *, browser: Browser, args: dict[str, Any], log_fn: LogFn | None = None,
) -> dict[str, Any]:
    """Gen ảnh Image Lab cho 1 AA account (camoufox).

    args: {"email": str, "params": {prompt, models, aspect_ratio, dimensions, generations}}
    Trả về {"email": str, "ok": True, "images": [{"name","data"}]} hoặc raise.
    """
    import json

    from common.database._async import get_account_by_email_async
    from common.database._engine import get_async_session
    from ....config.settings import load_config
    from ....services.artificialanalysis_ai.image_lab import ImageLabParams, run_image_lab

    email = args["email"]
    cfg = load_config()
    log = log_fn or (lambda m: None)

    async with get_async_session() as session:
        acc = await get_account_by_email_async(session, "ARTIFICIALANALYSIS", email)
    if not acc:
        raise ValueError(f"Account không tồn tại: ARTIFICIALANALYSIS/{email}")
    session_json = acc.get("session_state", "")
    if not session_json:
        raise RuntimeError(f"Không có session_state cho {email}")
    storage_state = json.loads(session_json)

    params = ImageLabParams(**args["params"])

    tmp_dir = Path(tempfile.mkdtemp(prefix="imagelab_"))
    ctx = await browser.new_context(storage_state=storage_state)
    try:
        await run_image_lab(
            context=ctx,
            params=params,
            output_dir=tmp_dir,
            image_lab_url=cfg.artificialanalysis.image_lab_url,
            log_fn=log,
            login_wait_ms=cfg.artificialanalysis.image_lab_login_wait_ms,
            poll_interval_ms=cfg.artificialanalysis.image_lab_poll_interval_ms,
            generation_timeout_sec=cfg.artificialanalysis.image_lab_generation_timeout_sec,
        )
    finally:
        await ctx.close()

    images = []
    for f in sorted(tmp_dir.glob("*.png")):
        images.append({"name": f.name, "data": base64.b64encode(f.read_bytes()).decode()})
        f.unlink()
    try:
        tmp_dir.rmdir()
    except OSError:
        pass

    log(f"✅ Image Lab {email}: {len(images)} image(s)")
    return {"email": email, "ok": True, "images": images}
