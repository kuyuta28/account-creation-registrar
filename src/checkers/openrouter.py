"""
checkers/openrouter.py — Check validity and usage for OpenRouter API keys.

API: GET https://openrouter.ai/api/v1/key   Header: Authorization: Bearer <key>

Public API (pure functions — no side effects except HTTP):
  check_key_async(api_key) -> CheckResult
  get_key_detail(api_key) -> dict   (full detail for UI modal)
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import httpx

from .base import CheckResult

if TYPE_CHECKING:
    from ..config.settings import OpenRouterConfig

_OPENROUTER_KEY_URL = "https://openrouter.ai/api/v1/key"  # default, override via OpenRouterConfig


async def check_key_async(
    api_key: str,
    cfg: OpenRouterConfig | None = None,
) -> CheckResult:
    """Async: check one OpenRouter API key — returns valid/invalid + basic usage."""
    if not api_key:
        return {"valid": False, "reason": "empty key"}
    url = cfg.key_check_url if cfg else _OPENROUTER_KEY_URL
    timeout = cfg.check_timeout_sec if cfg else 15
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(
                url,
                headers={"Authorization": f"Bearer {api_key}"},
            )
    except httpx.HTTPError as e:
        return {"valid": False, "reason": str(e)}

    if resp.status_code in (401, 403):
        return {"valid": False, "reason": f"invalid key ({resp.status_code})"}
    if resp.status_code != 200:
        return {"valid": False, "reason": f"HTTP {resp.status_code}"}

    data = resp.json().get("data", {})
    return {
        "valid": True,
        "reason": "",
        "label": data.get("label", ""),
        "is_free_tier": data.get("is_free_tier", True),
        "usage": data.get("usage", 0),
        "limit": data.get("limit"),
        "limit_remaining": data.get("limit_remaining"),
    }


async def get_key_detail(
    api_key: str,
    cfg: OpenRouterConfig | None = None,
) -> dict:
    """Fetch full detail for one OpenRouter API key — for UI display."""
    if not api_key:
        return {"valid": False, "error": "empty key"}
    url = cfg.key_check_url if cfg else _OPENROUTER_KEY_URL
    timeout = cfg.check_timeout_sec if cfg else 15
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(
                url,
                headers={"Authorization": f"Bearer {api_key}"},
            )
    except httpx.HTTPError as e:
        return {"valid": False, "error": str(e)}

    if resp.status_code in (401, 403):
        return {"valid": False, "error": f"invalid key ({resp.status_code})"}
    if resp.status_code != 200:
        return {"valid": False, "error": f"HTTP {resp.status_code}"}

    data = resp.json().get("data", {})
    return {
        "valid": True,
        "label": data.get("label", ""),
        "is_free_tier": data.get("is_free_tier", True),
        "limit": data.get("limit"),
        "limit_remaining": data.get("limit_remaining"),
        "limit_reset": data.get("limit_reset"),
        "include_byok_in_limit": data.get("include_byok_in_limit", False),
        "usage": data.get("usage", 0),
        "usage_daily": data.get("usage_daily", 0),
        "usage_weekly": data.get("usage_weekly", 0),
        "usage_monthly": data.get("usage_monthly", 0),
        "byok_usage": data.get("byok_usage", 0),
        "byok_usage_daily": data.get("byok_usage_daily", 0),
        "byok_usage_weekly": data.get("byok_usage_weekly", 0),
        "byok_usage_monthly": data.get("byok_usage_monthly", 0),
    }
