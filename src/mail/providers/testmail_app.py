"""
mail/providers/testmail_app.py — testmail.app inbox provider.

Provider string format: "testmail.app:NAMESPACE:APIKEY"
Email format:           {namespace}.{tag}@inbox.testmail.app
API:                    GET https://api.testmail.app/api/json?apikey=...&namespace=...&tag=...
Free tier:              100 emails/month, tag tạo on-the-fly không cần pre-register
"""
from __future__ import annotations

import asyncio
import time

from .._base import TESTMAIL_BASE, TESTMAIL_PREFIX, LogFn, Mailbox, random_string, request_with_retry, _tprint


def _parts(provider: str) -> tuple[str, str]:
    """Parse 'testmail.app:NAMESPACE:APIKEY' → (namespace, api_key). Pure."""
    rest = provider[len(TESTMAIL_PREFIX):]
    ns, _, key = rest.partition(":")
    return ns, key


async def create_mailbox(provider: str) -> Mailbox:
    namespace, api_key = _parts(provider)
    tag = random_string(10)
    email = f"{namespace}.{tag}@inbox.testmail.app"
    return Mailbox(
        email=email,
        token=namespace,    # namespace stored in token field
        account_id=tag,
        base_url=TESTMAIL_BASE,
        provider="testmail.app",
        api_key=api_key,
    )


async def get_messages(box: Mailbox, timestamp_from: int = 0) -> list[dict]:
    """Fetch all messages for a mailbox tag."""
    params: dict = {
        "apikey": box.api_key,
        "namespace": box.token,
        "tag": box.account_id,
    }
    if timestamp_from:
        params["timestamp_from"] = timestamp_from
    label = f"testmail.app:{box.token}"
    response = await request_with_retry(
        "GET", f"{TESTMAIL_BASE}/api/json",
        provider_name=label,
        params=params,
        timeout=20,
    )
    response.raise_for_status()
    data = response.json()
    if data.get("result") != "success":
        return []
    return [
        {
            "id": str(e.get("id", "")),
            "from": {"address": e.get("from", "") or ""},
            "subject": e.get("subject", "") or "",
            "body": e.get("text", "") or e.get("html", "") or "",
            "text": e.get("text", "") or "",
            "html": e.get("html", "") or "",
        }
        for e in (data.get("emails") or [])
        if isinstance(e, dict)
    ]


async def get_message_body(box: Mailbox, message_id: str) -> str:
    """Fetch message body by re-fetching all emails and finding by ID."""
    msgs = await get_messages(box)
    for msg in msgs:
        if msg.get("id") == message_id:
            return msg.get("body", "") or msg.get("text", "") or msg.get("html", "") or ""
    return ""


async def wait_for_message(
    box: Mailbox,
    from_contains: str = "",
    subject_contains: str = "",
    timeout: int = 120,
    log_fn: LogFn | None = None,
) -> dict | None:
    _log = log_fn or _tprint
    label = f"testmail.app:{box.token}"
    timestamp_from = 0
    _log(f"Waiting for email ({label}, timeout={timeout}s, from='{from_contains}')...")
    deadline = time.monotonic() + timeout
    poll_no = 0

    while time.monotonic() < deadline:
        remaining = int(deadline - time.monotonic())
        poll_no += 1
        _log(f"  [mail] poll #{poll_no} ({remaining}s left)...")
        try:
            msgs = await get_messages(box, timestamp_from=timestamp_from)
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
