"""
refresh_aa_models.py — Browser Gateway task: scrape model list live từ AA Image Lab.

Chạy trên host (gateway mở browser camoufox). KHÔNG trong container.
Flow: load 1 AA account có session valid → goto Image Lab → extract Next.js RSC
flight payload (self.__next_f) → parse model list đầy đủ (id UUID + name + elo +
price + creator + endpoints) → trả về.

Bỏ cache file aa_models.json — UI gọi endpoint refresh mỗi khi cần model tươi.
Flight payload là nguồn dữ liệu chính thức của AA UI (chứa đầy đủ fields, kể cả
khi model chưa được render checkbox).
"""
from __future__ import annotations

import json
import re
from typing import Any

from playwright.async_api import Browser

from ....core.google_oauth._helpers import LogFn
from ._registry import register  # noqa: F401  — side-effect: đăng ký task

# Pattern match 1 model object trong RSC flight JSON.
# RSC flight encode JSON với backslash escape: \"id\":\"...\" → regex dùng \\".
_MODEL_RE = re.compile(
    r'\\"id\\":\\"([0-9a-f-]{36})\\",\\"name\\":\\"([^"\\]+)\\",\\"createdAt\\":\\"[^"]*\\".*?'
    r'\\"ttiElo\\":([\d.]+|null),\\"itiElo\\":([\d.]+|null),\\"creator\\":\{\\"name\\":\\"([^"\\]*)\\",\\"logo\\":\\"([^"\\]*)\\".*?'
    r'\\"ttiPricePerGeneration\\":([\d.]+|null),\\"itiPricePerGeneration\\":([\d.]+|null),\\"hasTtiEndpoint\\":(true|false),\\"hasItiEndpoint\\":(true|false)',
    re.DOTALL,
)


@register("refresh_aa_models", engine="camoufox")
async def refresh_aa_models(
    *, browser: Browser, args: dict[str, Any], log_fn: LogFn | None = None,
) -> dict[str, Any]:
    """Scrape model list live từ AA Image Lab via RSC flight payload.

    args: {"email": str}  — AA account có session valid.
    Trả về {"by_mode": {"all": [...], "text_to_image": [...], "image_editing": [...]}}.
    """
    from common.database._async import get_accounts_async
    from common.database._engine import get_async_session
    from ....config.settings import load_config

    email = args["email"]
    cfg = load_config()
    aa_cfg = cfg.artificialanalysis
    log = log_fn or (lambda m: None)

    async with get_async_session() as session:
        rows = await get_accounts_async(session, "ARTIFICIALANALYSIS")
    account = next((r for r in rows if r.get("email") == email), None)
    if not account:
        raise RuntimeError(f"Không tìm thấy AA account {email}")
    state_raw = account.get("session_state")
    if not state_raw:
        raise RuntimeError(f"Account {email} chưa có session_state")
    state = json.loads(state_raw)

    ctx = await browser.new_context(storage_state=state)
    try:
        page = await ctx.new_page()
        log(f"[1/3] Opening {aa_cfg.image_lab_url}...")
        await page.goto(aa_cfg.image_lab_url, wait_until="domcontentloaded", timeout=cfg.timeouts.page_load * 2)
        await page.wait_for_timeout(aa_cfg.image_lab_login_wait_ms)
        if "/login" in page.url:
            raise RuntimeError(f"Session {email} expired — redirect về login")

        log("[2/3] Extracting Next.js RSC flight payload...")
        flight = await page.evaluate("""() => {
            const chunks = [];
            for (const s of document.querySelectorAll('script')) {
                const t = s.textContent || '';
                if (t.includes('__next_f')) chunks.push(t);
            }
            return chunks.join('\\n');
        }""")

        models = _parse_models_from_flight(flight)
        if not models:
            raise RuntimeError(
                f"Không parse được model nào từ flight payload (len={len(flight)}). "
                "AA có thể đổi format RSC — dump flight để kiểm tra."
            )
        log(f"[3/3] Parsed {len(models)} models.")
        return {
            "by_mode": {
                "all": models,
                "text_to_image": [m for m in models if m["hasTtiEndpoint"]],
                "image_editing": [m for m in models if m["hasItiEndpoint"]],
            },
        }
    finally:
        await ctx.close()


def _parse_models_from_flight(flight: str) -> list[dict[str, Any]]:
    """Parse model list từ Next.js RSC flight payload."""
    models: list[dict[str, Any]] = []
    seen: set[str] = set()
    for m in _MODEL_RE.finditer(flight):
        mid, name, tti_elo, iti_elo, creator, logo, tti_price, iti_price, has_tti, has_iti = m.groups()
        if mid in seen:
            continue
        seen.add(mid)
        models.append({
            "id": mid,
            "name": name,
            "creator": creator,
            "creatorLogo": logo,
            "ttiElo": _to_float(tti_elo),
            "itiElo": _to_float(iti_elo),
            "ttiPricePerGeneration": _to_float(tti_price),
            "itiPricePerGeneration": _to_float(iti_price),
            "hasTtiEndpoint": has_tti == "true",
            "hasItiEndpoint": has_iti == "true",
        })
    return models


def _to_float(s: str) -> float | None:
    return None if s == "null" else float(s)
