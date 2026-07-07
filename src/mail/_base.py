"""
mail/_base.py — Shared types, HTTP helper, và utilities dùng bởi tất cả providers.

Không import từ provider modules (tránh circular import).
"""
from __future__ import annotations

import asyncio
import datetime
import random
import string
from dataclasses import dataclass

import httpx

from collections.abc import Callable

LogFn = Callable[[str], None]


def _tprint(msg: str) -> None:
    ts = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=7))).strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")

# ── Provider prefix constants ─────────────────────────────────────────────────

TESTMAIL_PREFIX = "testmail.app:"
GUERRILLAMAIL_PREFIX = "guerrillamail.com"
MAILOSAUR_PREFIX = "mailosaur.com:"
GMAIL_PREFIX = "gmail.com"
SMS_WEBHOOK_PREFIX = "sms.webhook:"
AAR_PREFIX = "aar:"
_RETRYABLE = {429, 500, 502, 503, 504}

_DEFAULT_COOLDOWN_SEC = 120
_DEFAULT_MAX_CONSECUTIVE_FAILS = 3


def _mail_cfg():
    """Lazily load mail config — tránh circular import."""
    from ..config.settings import load_config
    return load_config().mail


def get_mail_tm_bases() -> tuple[str, ...]:
    return _mail_cfg().mail_tm_bases


def get_testmail_base() -> str:
    return _mail_cfg().testmail_base_url


def get_mailosaur_base() -> str:
    return _mail_cfg().mailosaur_base_url


def get_guerrillamail_base() -> str:
    return _mail_cfg().guerrillamail_base_url


def get_gmail_base() -> str:
    return _mail_cfg().gmail_base_url


def get_gmail_inbox_url() -> str:
    return _mail_cfg().gmail_inbox_url


def get_gmail_search_url_template() -> str:
    return _mail_cfg().gmail_search_url_template


# ── Dataclasses ───────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class MailCfg:
    """Immutable mail config — truyền vào create_mailbox() thay vì dùng global setter."""
    cooldown_sec: int = _DEFAULT_COOLDOWN_SEC
    max_consecutive_fails: int = _DEFAULT_MAX_CONSECUTIVE_FAILS
    testmail_monthly_quota: int = 100


@dataclass(frozen=True)
class Mailbox:
    """Immutable snapshot of một temp-mail inbox."""
    email: str
    token: str
    account_id: str
    base_url: str
    provider: str = "mail.tm"
    api_key: str = ""
    password: str = ""       # dùng cho Google OAuth popup login
    totp_secret: str = ""    # dùng cho Google 2FA
    phone: str = ""          # số điện thoại SIM gắn với account (dùng cho Google phone challenge)
    provider_id: int = 0     # mail_providers.id (testmail counting: bump usage khi nhận email)


# ── Pure utils ────────────────────────────────────────────────────────────────

def random_string(length: int = 12) -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=length))


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def provider_display_name(provider: str) -> str:
    """Human-readable label cho logging."""
    if provider.startswith(AAR_PREFIX):
        aar_name = provider[len(AAR_PREFIX):].split(":")[0]
        return f"aar:{aar_name}"
    if provider.startswith(TESTMAIL_PREFIX):
        ns = provider[len(TESTMAIL_PREFIX):].partition(":")[0]
        return f"testmail.app:{ns}"
    if provider == GUERRILLAMAIL_PREFIX or provider.startswith(GUERRILLAMAIL_PREFIX):
        return "guerrillamail.com"
    if provider.startswith(MAILOSAUR_PREFIX):
        rest = provider[len(MAILOSAUR_PREFIX):]
        server_id = rest.partition(":")[2]
        return f"mailosaur.com:{server_id}"
    return provider.replace("https://", "").replace("http://", "")


def provider_kind(provider: str) -> str:
    """Trả về loại provider: 'aar' | 'testmail.app' | 'guerrillamail.com' | 'mailosaur.com' | 'gmail.com' | 'mail.tm'."""
    if provider.startswith(AAR_PREFIX):
        return "aar"
    if provider.startswith(TESTMAIL_PREFIX):
        return "testmail.app"
    if provider == GUERRILLAMAIL_PREFIX or provider.startswith(GUERRILLAMAIL_PREFIX):
        return "guerrillamail.com"
    if provider.startswith(MAILOSAUR_PREFIX):
        return "mailosaur.com"
    if provider == GMAIL_PREFIX or provider.startswith(GMAIL_PREFIX + ":"):
        return "gmail.com"
    if provider.startswith(SMS_WEBHOOK_PREFIX) or provider == "sms.webhook":
        return "sms.webhook"
    return "mail.tm"


# ── HTTP helper ───────────────────────────────────────────────────────────────

def _retry_delay(response: httpx.Response | None, attempt: int) -> int:
    if response is not None:
        retry_after = response.headers.get("Retry-After", "").strip()
        if retry_after.isdigit():
            return max(1, int(retry_after))
    return min(30, 2 ** (attempt - 1) * 5)


async def request_with_retry(
    method: str, url: str, provider_name: str = "", max_retries: int = 3,
    log_fn: LogFn | None = None,
    retryable_codes: frozenset[int] | None = None,
    **kwargs,
) -> httpx.Response:
    _log = log_fn or _tprint
    _codes = retryable_codes if retryable_codes is not None else _RETRYABLE
    last_response: httpx.Response | None = None
    label = provider_name or url.rsplit("/", 1)[-1]
    async with httpx.AsyncClient() as client:
        for attempt in range(1, max_retries + 1):
            try:
                response = await client.request(method, url, **kwargs)
            except (httpx.ConnectError, httpx.TimeoutException) as exc:
                delay = min(30, 2 ** (attempt - 1) * 5)
                _log(f"  [mail] {label} -> network error (attempt {attempt}/{max_retries}): {exc}")
                if attempt < max_retries:
                    await asyncio.sleep(delay)
                    continue
                raise RuntimeError(f"{label} network error after {max_retries} attempts: {exc}") from exc
            if response.status_code not in _codes:
                return response
            last_response = response
            delay = _retry_delay(response, attempt)
            _log(f"  [mail] {label} -> {response.status_code} (attempt {attempt}/{max_retries}), waiting {delay}s...")
            if attempt < max_retries:
                await asyncio.sleep(delay)
    assert last_response is not None
    return last_response
