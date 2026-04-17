"""
aar_adapter.py — Async HTTP adapter wrapping AAR's mailbox API (port 8080).

Thay the `from core.base_mailbox import create_mailbox` truc tiep,
bay gio goi qua HTTP den AAR service.

Provider string format: "aar:{provider_name}" or "aar:{provider_name}:{base64_json_extra}"
Examples:
  "aar:tempmail_lol"                          — no config needed
  "aar:moemail:{b64({"moemail_api_url": ...})}"  — with config
  "aar:cfworker:{b64({"cfworker_api_url": ..., "cfworker_admin_token": ...})}"

Khong con co module-level state nua — state duoc quan ly boi AAR qua session_id.
"""
from __future__ import annotations

import base64
import json
import httpx

from .._base import LogFn, Mailbox, _tprint

AAR_PREFIX = "aar:"

# Default AAR base URL — override via config if needed
DEFAULT_AAR_BASE_URL = "http://127.0.0.1:8080"


def _get_aar_base_url() -> str:
    """Lay AAR base URL. Can be overridden via env/config in production."""
    return DEFAULT_AAR_BASE_URL


# ── Provider string helpers ───────────────────────────────────────────────────


def _parse_provider_str(provider_str: str) -> tuple[str, dict]:
    """Parse "aar:moemail" or "aar:moemail:{base64_json}" → (provider_name, extra_dict)."""
    rest = provider_str[len(AAR_PREFIX):]
    colon_pos = rest.find(":")
    if colon_pos == -1:
        return rest, {}
    provider_name = rest[:colon_pos]
    b64_extra = rest[colon_pos + 1:]
    try:
        extra = json.loads(base64.urlsafe_b64decode(b64_extra + "=="))
    except Exception as exc:
        raise ValueError(
            f"Invalid base64 JSON extra in AAR provider string {provider_str!r}: {exc}"
        ) from exc
    return provider_name, extra


# ── Public API ──────────────────────────────────────────────────────────────


async def create_mailbox(
    provider_str: str,
    proxy: str | None = None,
    log_fn: LogFn | None = None,
) -> Mailbox:
    """Tao AAR mailbox qua HTTP, tra ve Mailbox voi session_id lam token."""
    _log = log_fn or _tprint
    aar_provider, extra = _parse_provider_str(provider_str)

    base_url = _get_aar_base_url()
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{base_url}/api/mailbox/create",
            json={
                "provider": aar_provider,
                "extra": extra,
                "proxy": proxy,
            },
        )
        resp.raise_for_status()
        data = resp.json()

    session_id = data["session_id"]
    email = data["email"]
    account_id = data["account_id"]

    _log(f"Temp mail (aar:{aar_provider}): {email}")

    return Mailbox(
        email=email,
        token=session_id,  # session_id is our handle to AAR
        account_id=account_id,
        base_url=base_url,
        provider=provider_str,
    )


async def wait_for_message(
    box: Mailbox,
    from_contains: str = "",
    subject_contains: str = "",
    timeout: int = 120,
    poll_interval: int = 3,
    log_fn: LogFn | None = None,
) -> dict | None:
    """Poll for a new message matching filters."""
    _log = log_fn or _tprint

    keyword = from_contains or subject_contains

    base_url = box.base_url or _get_aar_base_url()
    async with httpx.AsyncClient(timeout=timeout + 10.0) as client:
        try:
            resp = await client.post(
                f"{base_url}/api/mailbox/wait-code",
                json={
                    "session_id": box.token,
                    "keyword": keyword,
                    "timeout": timeout,
                    "poll_interval": poll_interval,
                },
            )
            if resp.status_code == 408:
                _log(f"  [aar] timeout waiting for code ({timeout}s)")
                return None
            resp.raise_for_status()
            data = resp.json()
            _log(f"  [aar] got message id={data['message_id']} subject={data['subject']!r}")
            return {
                "id": data["message_id"],
                "subject": data["subject"],
                "from": data["from_addr"],
            }
        except httpx.TimeoutException:
            _log(f"  [aar] timeout waiting for code ({timeout}s)")
            return None


async def get_message_body(box: Mailbox, message_id: str) -> str:
    """Lay message body tu AAR cache."""
    base_url = box.base_url or _get_aar_base_url()
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            f"{base_url}/api/mailbox/message",
            params={"session_id": box.token, "message_id": message_id},
        )
        if resp.status_code == 404:
            return ""
        resp.raise_for_status()
        data = resp.json()
        return data.get("body", "")


async def get_messages(box: Mailbox) -> list[dict]:
    """Lay tat ca messages tu AAR cache."""
    base_url = box.base_url or _get_aar_base_url()
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            f"{base_url}/api/mailbox/messages",
            params={"session_id": box.token},
        )
        resp.raise_for_status()
        data = resp.json()
        return [
            {"id": m["message_id"], **m}
            for m in data.get("messages", [])
        ]