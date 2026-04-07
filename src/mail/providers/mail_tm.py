"""
mail/providers/mail_tm.py — mail.tm inbox provider.

Provider string format: "https://api.mail.tm"  (base URL trực tiếp)
Email format:           {random}@{domain}
API:                    REST, JWT bearer token
"""
from __future__ import annotations

import asyncio
import random
import time

from .._base import LogFn, Mailbox, auth_headers, provider_display_name, random_string, request_with_retry, _tprint

_MAIL_TM_RETRY_DOMAINS = ("mail.tm", "mail.gw")


async def create_mailbox(base_url: str, log_fn: LogFn | None = None) -> Mailbox:
    label = provider_display_name(base_url)
    domain = await _fetch_domain(base_url, label, log_fn)
    email = f"{random_string(10)}@{domain}"
    password = random_string(16)

    reg = await request_with_retry(
        "POST", f"{base_url}/accounts", provider_name=label, max_retries=1,
        log_fn=log_fn, json={"address": email, "password": password}, timeout=15,
    )
    if reg.status_code not in (200, 201):
        raise RuntimeError(f"{label} account creation failed: {reg.status_code} {reg.text}")
    account_id = reg.json().get("id", "")

    tok = await request_with_retry(
        "POST", f"{base_url}/token", provider_name=label, max_retries=1,
        log_fn=log_fn, json={"address": email, "password": password}, timeout=15,
    )
    tok.raise_for_status()
    token = tok.json()["token"]
    return Mailbox(email=email, token=token, account_id=account_id, base_url=base_url, provider="mail.tm")


async def get_messages(box: Mailbox) -> list[dict]:
    response = await request_with_retry(
        "GET", f"{box.base_url}/messages",
        provider_name=provider_display_name(box.base_url),
        headers=auth_headers(box.token), timeout=15,
    )
    response.raise_for_status()
    return response.json().get("hydra:member", [])


async def get_message_body(box: Mailbox, message_id: str) -> str:
    response = await request_with_retry(
        "GET", f"{box.base_url}/messages/{message_id}",
        provider_name=provider_display_name(box.base_url),
        headers=auth_headers(box.token), timeout=15,
    )
    response.raise_for_status()
    data = response.json()
    return data.get("text", "") or (data.get("html") or [""])[0]


async def wait_for_message(
    box: Mailbox,
    from_contains: str = "",
    subject_contains: str = "",
    timeout: int = 120,
    poll_interval: int = 5,
    log_fn: LogFn | None = None,
) -> dict | None:
    _log = log_fn or _tprint
    _log(f"Waiting for email (timeout={timeout}s, from='{from_contains}')...")
    deadline = time.monotonic() + timeout
    seen_ids: set = set()
    poll_no = 0

    while time.monotonic() < deadline:
        remaining = int(deadline - time.monotonic())
        poll_no += 1
        _log(f"  [mail] poll #{poll_no} ({remaining}s left)...")
        try:
            for msg in await get_messages(box):
                mid = msg.get("id", "")
                if mid in seen_ids:
                    continue
                seen_ids.add(mid)
                sender = msg.get("from", {}).get("address", "")
                subject = msg.get("subject", "")
                from_ok = from_contains.lower() in sender.lower() if from_contains else True
                subj_ok = subject_contains.lower() in subject.lower() if subject_contains else True
                if from_ok and subj_ok:
                    _log(f"  Got: '{subject}' from {sender}")
                    msg["body"] = await get_message_body(box, mid)
                    return msg
        except Exception as exc:  # noqa: BLE001 - mail provider best-effort
            _log(f"  Poll error: {exc}")
        await asyncio.sleep(poll_interval)

    _log("  Timed out waiting for email")
    return None


async def _fetch_domain(base_url: str, label: str, log_fn: LogFn | None = None) -> str:
    response = await request_with_retry("GET", f"{base_url}/domains", provider_name=label, max_retries=1, log_fn=log_fn, timeout=15)
    response.raise_for_status()
    members = response.json().get("hydra:member", [])
    if not members:
        raise RuntimeError(f"No domains available from {label}")
    return random.choice(members)["domain"]
