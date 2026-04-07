"""mail/providers/aar_adapter.py — Async adapter wrapping AAR's synchronous BaseMailbox providers.

Provider string format: "aar:{provider_name}" or "aar:{provider_name}:{base64_json_extra}"
Examples:
  "aar:tempmail_lol"                          — no config needed
  "aar:moemail:{b64({"moemail_api_url": ...})}"  — with config
  "aar:cfworker:{b64({"cfworker_api_url": ..., "cfworker_admin_token": ...})}"

Module-level state:
  _aar_instances : email → (BaseMailbox, MailboxAccount)
  _message_cache : "{email}:{msg_id}" → msg dict {id, subject, from_addr, body, html_body}
"""
from __future__ import annotations

import asyncio
import base64
import json
import time
from collections.abc import Callable
from typing import Any

from .._base import LogFn, Mailbox, _tprint

AAR_PREFIX = "aar:"

# ── Module-level state ────────────────────────────────────────────────────────
_aar_instances: dict[str, tuple[Any, Any]] = {}   # email → (BaseMailbox, MailboxAccount)
_message_cache: dict[str, dict] = {}              # "{email}:{msg_id}" → msg dict


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


# ── Public API ────────────────────────────────────────────────────────────────

async def create_mailbox(
    provider_str: str,
    proxy: str | None = None,
    log_fn: LogFn | None = None,
) -> Mailbox:
    """Create an AAR mailbox, register it in state, return project Mailbox."""
    _log = log_fn or _tprint
    aar_provider, extra = _parse_provider_str(provider_str)

    loop = asyncio.get_event_loop()

    def _create_sync():
        from core.base_mailbox import create_mailbox as aar_factory
        box = aar_factory(aar_provider, extra, proxy)
        account = box.get_email()
        return box, account

    box, account = await loop.run_in_executor(None, _create_sync)
    _aar_instances[account.email] = (box, account)
    _log(f"Temp mail (aar:{aar_provider}): {account.email}")

    return Mailbox(
        email=account.email,
        token=account.account_id,
        account_id=account.account_id,
        base_url="",
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
    """Poll for a new message matching filters. Caches body for get_message_body()."""
    _log = log_fn or _tprint
    entry = _aar_instances.get(box.email)
    if entry is None:
        raise RuntimeError(f"No AAR mailbox instance found for {box.email!r}")

    aar_box, account = entry
    loop = asyncio.get_event_loop()

    known_ids: set[str] = await loop.run_in_executor(
        None, aar_box.get_current_ids, account
    )

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        frozen_ids = frozenset(known_ids)

        def _fetch_sync(fids=frozen_ids):
            return aar_box.fetch_new_messages(account, set(fids))

        new_msgs: list[dict] = await loop.run_in_executor(None, _fetch_sync)

        for msg in new_msgs:
            mid = msg.get("id", "")
            if mid:
                known_ids.add(mid)

            subject = msg.get("subject", "")
            from_addr = msg.get("from_addr", "")

            if from_contains and from_contains.lower() not in from_addr.lower():
                _log(f"  [aar] skip msg id={mid!r} from={from_addr!r} (want {from_contains!r})")
                continue
            if subject_contains and subject_contains.lower() not in subject.lower():
                _log(f"  [aar] skip msg id={mid!r} subject={subject!r} (want {subject_contains!r})")
                continue

            # Cache full message for get_message_body()
            cache_key = f"{box.email}:{mid}"
            _message_cache[cache_key] = msg
            _log(f"  [aar] got message id={mid!r} subject={subject!r}")

            return {"id": mid, "subject": subject, "from": from_addr}

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        await asyncio.sleep(min(float(poll_interval), remaining))

    return None


async def get_message_body(box: Mailbox, message_id: str) -> str:
    """Return cached message body (HTML preferred, fallback to text)."""
    cache_key = f"{box.email}:{message_id}"
    msg = _message_cache.get(cache_key)
    if msg is None:
        return ""
    return msg.get("html_body", "") or msg.get("body", "")


async def get_messages(box: Mailbox) -> list[dict]:
    """Return all cached messages for this mailbox."""
    prefix = f"{box.email}:"
    return [
        {"id": key[len(prefix):], **msg}
        for key, msg in _message_cache.items()
        if key.startswith(prefix)
    ]
