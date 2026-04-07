"""
mail/providers/mailslurp_com.py — mailslurp.com inbox provider.

Provider string format: "mailslurp.com:SK_xxxxxxxxxxxx"
Email format:           {uuid}@mailslurp.com  (assigned by API)
API:                    REST, x-api-key header, free tier 200 inbound/month per key
"""
from __future__ import annotations


from .._base import MAILSLURP_BASE, MAILSLURP_PREFIX, LogFn, Mailbox, request_with_retry, _tprint


def _api_key(provider: str) -> str:
    """Parse 'mailslurp.com:SK_xxx' → 'SK_xxx'."""
    return provider[len(MAILSLURP_PREFIX):]


def _headers(api_key: str) -> dict[str, str]:
    return {"x-api-key": api_key, "Content-Type": "application/json"}


def _label(api_key: str) -> str:
    return f"mailslurp.com:...{api_key[-8:]}"


async def create_mailbox(provider: str, log_fn: LogFn | None = None) -> Mailbox:
    api_key = _api_key(provider)
    label = _label(api_key)
    response = await request_with_retry(
        "POST",
        f"{MAILSLURP_BASE}/inboxes/withDefaults",
        provider_name=label,
        max_retries=2,
        log_fn=log_fn,
        headers=_headers(api_key),
        timeout=15,
    )
    if response.status_code not in (200, 201):
        raise RuntimeError(f"{label} inbox creation failed: {response.status_code} {response.text[:200]}")
    data = response.json()
    return Mailbox(
        email=data["emailAddress"],
        token="",
        account_id=data["id"],
        base_url=MAILSLURP_BASE,
        provider="mailslurp.com",
        api_key=api_key,
    )


async def get_messages(box: Mailbox) -> list[dict]:
    response = await request_with_retry(
        "GET",
        f"{MAILSLURP_BASE}/inboxes/{box.account_id}/emails",
        provider_name=_label(box.api_key),
        headers={"x-api-key": box.api_key},
        params={"sort": "DESC", "size": 20},
        timeout=15,
    )
    if response.status_code == 404:
        return []
    response.raise_for_status()
    items = response.json()
    if not isinstance(items, list):
        return []
    return [
        {
            "id": str(item.get("id", "")),
            "from": {"address": item.get("from", "") or ""},
            "subject": item.get("subject", "") or "",
            "body": "",
            "_raw": item,
        }
        for item in items
        if isinstance(item, dict)
    ]


async def get_message_body(box: Mailbox, message_id: str) -> str:
    response = await request_with_retry(
        "GET",
        f"{MAILSLURP_BASE}/emails/{message_id}",
        provider_name=_label(box.api_key),
        headers={"x-api-key": box.api_key},
        timeout=15,
    )
    if response.status_code == 404:
        return ""
    response.raise_for_status()
    return response.json().get("body") or ""


async def wait_for_message(
    box: Mailbox,
    from_contains: str = "",
    subject_contains: str = "",
    timeout: int = 120,
    log_fn: LogFn | None = None,
) -> dict | None:
    _log = log_fn or _tprint
    label = _label(box.api_key)
    params: dict = {
        "inboxId": box.account_id,
        "timeout": timeout * 1000,
        "unreadOnly": "true",
    }
    _log(f"  [mail] {label} blocking wait (timeout={timeout}s)...")
    try:
        response = await request_with_retry(
            "GET",
            f"{MAILSLURP_BASE}/waitForLatestEmail",
            provider_name=label,
            max_retries=1,
            log_fn=log_fn,
            headers={"x-api-key": box.api_key},
            params=params,
            timeout=timeout + 15,
        )
        if response.status_code == 408:
            _log(f"  [mail] {label} wait timed out (no email)")
            return None
        response.raise_for_status()
        item = response.json()
        sender = item.get("from") or ""
        subject = item.get("subject") or ""
        from_ok = from_contains.lower() in sender.lower() if from_contains else True
        subj_ok = subject_contains.lower() in subject.lower() if subject_contains else True
        if not (from_ok and subj_ok):
            _log(f"  [mail] {label} got email but doesn't match filter (from={sender!r}, subject={subject!r})")
            return None
        body = item.get("body") or ""
        _log(f"  Got: '{subject}' from {sender}")
        return {
            "id": str(item.get("id", "")),
            "from": {"address": sender},
            "subject": subject,
            "body": body,
            "_raw": item,
        }
    except Exception as exc:  # noqa: BLE001 - mail provider best-effort
        _log(f"  [mail] {label} wait error: {exc}")
        return None
