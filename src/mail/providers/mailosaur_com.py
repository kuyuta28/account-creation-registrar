"""
mail/providers/mailosaur_com.py — Mailosaur REST API mail provider.

Provider string format: "mailosaur.com:API_KEY:SERVER_ID"
Email format:           {random_tag}@{SERVER_ID}.mailosaur.net
API auth:               HTTP Basic Auth (username="api", password=API_KEY)
API base:               https://mailosaur.com/api

Docs: https://mailosaur.com/docs/api
"""
from __future__ import annotations

import asyncio
import time

from .._base import MAILOSAUR_BASE, MAILOSAUR_PREFIX, LogFn, Mailbox, random_string, request_with_retry, _tprint


def _parts(provider: str) -> tuple[str, str]:
    """Parse 'mailosaur.com:API_KEY:SERVER_ID' → (api_key, server_id). Pure."""
    rest = provider[len(MAILOSAUR_PREFIX):]
    api_key, _, server_id = rest.partition(":")
    return api_key, server_id


def _auth(api_key: str) -> tuple[str, str]:
    """HTTP Basic Auth tuple — username='api', password=API_KEY."""
    return ("api", api_key)


async def create_mailbox(provider: str) -> Mailbox:
    """Tạo mailbox mới — chỉ generate địa chỉ email, không cần API call."""
    api_key, server_id = _parts(provider)
    tag = random_string(12)
    email = f"{tag}@{server_id}.mailosaur.net"
    return Mailbox(
        email=email,
        token=server_id,    # server_id stored in token
        account_id=tag,
        base_url=MAILOSAUR_BASE,
        provider="mailosaur.com",
        api_key=api_key,
    )


async def get_messages(box: Mailbox) -> list[dict]:
    """Fetch tất cả messages từ server inbox."""
    label = f"mailosaur.com:{box.token}"
    url = f"{MAILOSAUR_BASE}/messages"
    response = await request_with_retry(
        "GET", url,
        provider_name=label,
        params={"server": box.token},
        auth=_auth(box.api_key),
        timeout=20,
    )
    if response.status_code == 401:
        raise RuntimeError("Mailosaur auth failed (401) — kiểm tra API key")
    response.raise_for_status()
    data = response.json()
    items = data.get("items", []) or []
    return [
        {
            "id": str(item.get("id", "")),
            "from": {"address": _extract_sender(item)},
            "subject": item.get("subject", "") or "",
            "body": _extract_body(item),
            "html": _extract_html(item),
            "text": _extract_text(item),
        }
        for item in items
        if isinstance(item, dict)
        and _is_addressed_to(item, box.email)
    ]


async def get_message_body(box: Mailbox, message_id: str) -> str:
    """Fetch full message body theo ID."""
    label = f"mailosaur.com:{box.token}"
    url = f"{MAILOSAUR_BASE}/messages/{message_id}"
    response = await request_with_retry(
        "GET", url,
        provider_name=label,
        auth=_auth(box.api_key),
        timeout=20,
    )
    if response.status_code == 401:
        raise RuntimeError("Mailosaur auth failed (401) — kiểm tra API key")
    response.raise_for_status()
    data = response.json()
    html = (data.get("html") or {}).get("body") or ""
    text = (data.get("text") or {}).get("body") or ""
    return html or text


async def wait_for_message(
    box: Mailbox,
    from_contains: str = "",
    subject_contains: str = "",
    timeout: int = 120,
    log_fn: LogFn | None = None,
) -> dict | None:
    _log = log_fn or _tprint
    label = f"mailosaur.com:{box.token}"
    _log(f"Waiting for email ({label}, timeout={timeout}s, from='{from_contains}')...")
    deadline = time.monotonic() + timeout
    poll_no = 0

    while time.monotonic() < deadline:
        remaining = int(deadline - time.monotonic())
        poll_no += 1
        _log(f"  [mail] poll #{poll_no} ({remaining}s left)...")
        try:
            msgs = await get_messages(box)
            for msg in msgs:
                sender = msg.get("from", {}).get("address", "")
                subject = msg.get("subject", "")
                from_ok = from_contains.lower() in sender.lower() if from_contains else True
                subj_ok = subject_contains.lower() in subject.lower() if subject_contains else True
                if from_ok and subj_ok:
                    _log(f"  Got: '{subject}' from {sender}")
                    return msg
        except Exception as exc:  # noqa: BLE001 - mail provider best-effort
            _log(f"  Poll error: {exc}")
        await asyncio.sleep(5)

    _log("  Timed out waiting for email")
    return None


# ── Pure helpers ──────────────────────────────────────────────────────

def _extract_sender(item: dict) -> str:
    sender_list = item.get("from", []) or []
    if isinstance(sender_list, list) and sender_list:
        return sender_list[0].get("email", "") or ""
    if isinstance(sender_list, dict):
        return sender_list.get("email", "") or ""
    return ""


def _extract_body(item: dict) -> str:
    return _extract_html(item) or _extract_text(item)


def _extract_html(item: dict) -> str:
    html_obj = item.get("html") or {}
    if isinstance(html_obj, dict):
        return html_obj.get("body", "") or ""
    return ""


def _extract_text(item: dict) -> str:
    text_obj = item.get("text") or {}
    if isinstance(text_obj, dict):
        return text_obj.get("body", "") or ""
    return ""


def _is_addressed_to(item: dict, email: str) -> bool:
    """Kiểm tra message có phải gửi đến email này không."""
    to_list = item.get("to", []) or []
    email_lower = email.lower()
    for recipient in to_list:
        if isinstance(recipient, dict):
            addr = (recipient.get("email") or "").lower()
            if addr == email_lower:
                return True
    return False
