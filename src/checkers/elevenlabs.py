"""
checkers/elevenlabs.py — Check validity and quota for ElevenLabs API keys.

API: GET https://api.elevenlabs.io/v1/user   Header: xi-api-key: <key>

Public API (pure functions — no side effects except HTTP):
  check_key(api_key) -> CheckResult
  format_row(email, result) -> str
  main() -> None
"""
from __future__ import annotations

import asyncio
from datetime import datetime, UTC
from typing import TYPE_CHECKING

import httpx

from ..config.settings import load_config
from src.core.account_record import Repo
from .base import CheckResult

if TYPE_CHECKING:
    from ..config.settings import ElevenLabsConfig


# ── pure functions ────────────────────────────────────────────────────────────


def _parse_user_response(data: dict) -> CheckResult:
    """Pure: parse ElevenLabs /v1/user response → CheckResult."""
    sub = data.get("subscription", {})
    used = sub.get("character_count", 0)
    limit = sub.get("character_limit", 0)
    reset_unix = sub.get("next_character_count_reset_unix")
    reset_dt = (
        datetime.fromtimestamp(reset_unix, tz=UTC).strftime("%Y-%m-%d")
        if reset_unix else "unknown"
    )
    return {
        "valid": True,
        "tier": sub.get("tier", "unknown"),
        "status": sub.get("status", "unknown"),
        "characters_used": used,
        "characters_limit": limit,
        "characters_remaining": limit - used,
        "resets_on": reset_dt,
        "reason": "",
    }


_TTS_CHECK_URL = "https://api.elevenlabs.io/v1/text-to-speech/21m00Tcm4TlvDq8ikWAM/stream"
_TTS_CHECK_PAYLOAD = {
    "text": ".",
    "model_id": "eleven_multilingual_v2",
    "voice_settings": {"stability": 0.5, "similarity_boost": 0.5},
}


async def _check_tts_real(api_key: str, timeout: int) -> str | None:
    """Thực hiện TTS request thật để detect unusual_activity.
    Returns: None nếu OK, error string nếu lỗi.
    """
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                _TTS_CHECK_URL,
                headers={"xi-api-key": api_key, "Content-Type": "application/json"},
                json=_TTS_CHECK_PAYLOAD,
            )
    except httpx.HTTPError as e:
        return f"network error: {e}"
    if resp.status_code == 401:
        body = resp.text
        if "detected_unusual_activity" in body:
            return "unusual_activity — free tier blocked by ElevenLabs (proxy/VPN)"
        return f"invalid key (401 on TTS): {body[:200]}"
    if resp.status_code == 402:
        # free tier không dùng được library voice qua API — key vẫn valid
        return None
    if resp.status_code not in (200, 206):
        return f"TTS HTTP {resp.status_code}: {resp.text[:200]}"
    return None


async def check_key(
    api_key: str,
    cfg: ElevenLabsConfig | None = None,
) -> CheckResult:
    """Check one ElevenLabs API key — gồm cả real TTS request để detect unusual_activity."""
    if not api_key:
        return {"valid": False, "reason": "empty key"}
    url = cfg.api_user_url if cfg else "https://api.elevenlabs.io/v1/user"
    timeout = cfg.check_timeout_sec if cfg else 10
    try:
        user_resp, tts_err = await asyncio.gather(
            _fetch_user(api_key, url, timeout),
            _check_tts_real(api_key, timeout),
        )
    except Exception as e:  # noqa: BLE001 - HTTP boundary - log and return None
        return {"valid": False, "reason": str(e)}

    # user check failed
    if isinstance(user_resp, str):
        return {"valid": False, "reason": user_resp}

    # TTS thật bị block
    if tts_err is not None:
        return {"valid": False, "reason": tts_err}

    return _parse_user_response(user_resp)


async def _fetch_user(api_key: str, url: str, timeout: int) -> dict | str:
    """Returns parsed JSON dict hoặc error string."""
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(url, headers={"xi-api-key": api_key})
    except httpx.HTTPError as e:
        return str(e)
    if resp.status_code == 401:
        body = resp.text
        if "detected_unusual_activity" in body:
            return "unusual_activity — free tier blocked by ElevenLabs (proxy/VPN)"
        return "invalid key (401)"
    if resp.status_code != 200:
        return f"HTTP {resp.status_code}"
    return resp.json()


def format_row(email: str, result: CheckResult) -> str:
    """Format one table row. Pure — no I/O."""
    if result["valid"]:
        return (
            f"{email:<35} {'✅':<6} {result['status']:<10} "
            f"{result['characters_used']:>8,} {result['characters_limit']:>8,} "
            f"{result['characters_remaining']:>10,} {result['resets_on']:<12}"
        )
    return (
        f"{email:<35} {'❌':<6} {'':<10} {'':>8} {'':>8} {'':>10} {'':12}"
        f" {result['reason']}"
    )


async def print_table(accounts: list) -> None:
    """Print a formatted status table for a list of account dicts."""
    print(f"\nChecking {len(accounts)} account(s)...\n")
    print(
        f"{'Email':<35} {'Valid':<6} {'Status':<10} "
        f"{'Used':>8} {'Limit':>8} {'Remaining':>10} {'Resets':<12} Reason"
    )
    print("-" * 110)
    results = await asyncio.gather(*[check_key(acc.get("api_key", "")) for acc in accounts])
    for acc, result in zip(accounts, results):
        print(format_row(acc.get("email", "?"), result))


async def _main_async() -> None:
    cfg      = load_config()
    repo     = Repo(base_dir=cfg.base_dir)
    from common.database._async import get_accounts_async
    accounts = await get_accounts_async(service="elevenlabs")

    if not accounts:
        print("No ElevenLabs accounts found.")
        return

    await print_table(accounts)


def main() -> None:
    asyncio.run(_main_async())


if __name__ == "__main__":
    main()
