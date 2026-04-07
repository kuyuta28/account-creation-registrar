"""
mail/providers/gmail.py - Gmail provider dung Playwright headless voi session cookies.

Google chay security check nen httpx bi reject (401) khi goi Atom feed / REST API.
Cach duy nhat reliable: chay Camoufox headless voi storage_state da luu, scrape
truc tiep Gmail web UI giong nhu mot nguoi dung that su.

-- Luu y quan trong --
Atom feed (mail.google.com/mail/feed/atom/) tra 401 ca khi co session cookies.
Khong su dung IMAP (nhieu account bi ban). Khong dung OAuth (khong co credentials).
PHUONG PHAP DUY NHAT: Navigate Gmail #inbox, doi DOM render (4s), extract tr.zA rows.

Provider string format: "gmail.com"
Mailbox construction:   make_mailbox(email, google_auth_state) -> Mailbox

Public API:
  make_mailbox(email, google_auth_state) -> Mailbox
  get_messages(box, unread_only)         -> list[dict]
  search_messages(box, query)            -> list[dict]
  get_message_body(box, message_id)      -> str
  wait_for_message(box, ...)             -> dict | None
"""
from __future__ import annotations

import asyncio
import json
import platform
import time
import urllib.parse
from typing import TypedDict

from .._base import LogFn, Mailbox, _tprint


class GmailMessage(TypedDict):
    id: str        # jsthread attribute value, VD ":2w"
    subject: str
    from_: str     # sender name (key "from" trong JS, map sang "from_" để tránh clash keyword)
    date: str
    unread: bool

_PROVIDER   = "gmail.com"
_GMAIL_BASE = "https://mail.google.com"
_INBOX_URL  = "https://mail.google.com/mail/u/0/#inbox"
_SEARCH_URL = "https://mail.google.com/mail/u/0/#search/{query}"

# CSS selectors cho Gmail web UI
_EXTRACT_ROWS_JS = """() => {
    const rows = [];
    document.querySelectorAll("tr.zA").forEach(tr => {
        const id      = tr.getAttribute("jsthread") || tr.id || "";
        const subject = tr.querySelector(".y6")?.innerText?.trim() || "";
        const fromEl  = tr.querySelector(".zF") || tr.querySelector(".yP");
        const from    = (fromEl?.getAttribute("name") || fromEl?.innerText || "").trim();
        const date    = tr.querySelector(".xW span")?.title
                     || tr.querySelector(".xW span")?.innerText?.trim() || "";
        const unread  = tr.classList.contains("zE");
        rows.push({id, subject, from, date, unread});
    });
    return rows;
}"""

_EXTRACT_BODY_JS = """() => {
    const bodyEl = document.querySelector(".ii.gt div");
    return bodyEl ? bodyEl.innerHTML : null;
}"""


# -- Mailbox factory ----------------------------------------------------------

def make_mailbox(
    email: str,
    google_auth_state: str,
    password: str = "",
    totp_secret: str = "",
) -> Mailbox:
    """Tao Mailbox tu Gmail address + google_auth_state JSON (Playwright storage_state)."""
    return Mailbox(
        email=email,
        token=google_auth_state,
        account_id="",
        base_url=_GMAIL_BASE,
        provider=_PROVIDER,
        password=password,
        totp_secret=totp_secret,
    )


# -- Camoufox context manager -------------------------------------------------

class _GmailCtx:
    """Mo Camoufox headless voi Gmail storage_state, tra page."""

    def __init__(self, box: Mailbox):
        state = box.token
        self._state  = json.loads(state) if isinstance(state, str) else state
        self._cam    = None
        self._ctx    = None

    async def __aenter__(self):
        try:
            from camoufox.async_api import AsyncCamoufox
        except ImportError as exc:
            raise RuntimeError("camoufox khong duoc cai -- pip install camoufox") from exc

        _os = {"Windows": "windows", "Darwin": "macos", "Linux": "linux"}.get(platform.system(), "linux")
        self._cam = AsyncCamoufox(headless=True, os=_os)
        browser   = await self._cam.__aenter__()
        self._ctx = await browser.new_context(storage_state=self._state, no_viewport=True)
        return await self._ctx.new_page()

    async def __aexit__(self, *args):
        if self._ctx:
            await self._ctx.close()
        if self._cam:
            await self._cam.__aexit__(*args)


def _gmail_ctx(box: Mailbox) -> _GmailCtx:
    return _GmailCtx(box)


def _check_logged_in(url: str) -> None:
    if "accounts.google.com" in url or "ServiceLogin" in url:
        raise RuntimeError(
            "Gmail session het han -- can refresh Google session truoc "
            "(goi api.refreshMailboxSession hoac dung Get All Sessions tren UI)."
        )


# -- Public API ---------------------------------------------------------------

async def get_messages(box: Mailbox, unread_only: bool = False) -> list[GmailMessage]:
    """
    Lay danh sach emails tu Gmail inbox.
    Scrape Gmail web UI (tr.zA DOM rows) qua Camoufox headless.
    """
    async with _gmail_ctx(box) as page:
        await page.goto(_INBOX_URL, wait_until="domcontentloaded", timeout=30_000)
        await page.wait_for_timeout(4_000)
        _check_logged_in(page.url)
        rows: list[GmailMessage] = await page.evaluate(_EXTRACT_ROWS_JS)

    return [r for r in rows if r.get("unread")] if unread_only else rows


async def search_messages(box: Mailbox, query: str) -> list[GmailMessage]:
    """
    Lay emails khop Gmail search query.
    Vi du: query="from:noreply@elevenlabs.io" hoac "subject:verify"
    """
    url = _SEARCH_URL.format(query=urllib.parse.quote(query))
    async with _gmail_ctx(box) as page:
        await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        await page.wait_for_timeout(4_000)
        _check_logged_in(page.url)
        rows: list[GmailMessage] = await page.evaluate(_EXTRACT_ROWS_JS)
        return rows


async def get_message_body(box: Mailbox, message_id: str) -> str:
    """
    Mo email theo jsthread ID va lay noi dung HTML.
    message_id: gia tri jsthread tu get_messages() (vi du ":2w").
    """
    async with _gmail_ctx(box) as page:
        await page.goto(_INBOX_URL, wait_until="domcontentloaded", timeout=30_000)
        await page.wait_for_timeout(3_000)
        _check_logged_in(page.url)

        clicked: bool = await page.evaluate(
            """(tid) => {
                const row = document.querySelector(`tr[jsthread="${tid}"]`);
                if (row) { row.click(); return true; }
                return false;
            }""",
            message_id,
        )
        if not clicked:
            raise RuntimeError(f"Khong tim thay email voi jsthread={message_id!r} trong inbox")

        await page.wait_for_selector(".ii.gt", timeout=15_000)
        body = await page.evaluate(_EXTRACT_BODY_JS)

    if body is None:
        raise RuntimeError(
            f"Gmail: khong tim thay element '.ii.gt div' cho message {message_id} "
            "-- email co the chua load xong hoac Gmail thay doi DOM structure"
        )
    return body


async def wait_for_message(
    box: Mailbox,
    from_contains: str = "",
    subject_contains: str = "",
    timeout: int = 120,
    poll_interval: int = 12,
    log_fn: LogFn | None = None,
) -> GmailMessage | None:
    """
    Poll Gmail inbox/search den khi tim duoc email khop filter hoac het timeout.
    Moi lan poll mo mot browser headless rieng (stateless).
    Neu co filter, dung Gmail search de nhanh hon.
    Tra dict hoac None neu timeout.
    """
    _log = log_fn or _tprint
    _log(f"[gmail] Cho email (timeout={timeout}s, from='{from_contains}', subject='{subject_contains}')...")

    if from_contains or subject_contains:
        parts = []
        if from_contains:
            parts.append(f"from:{from_contains}")
        if subject_contains:
            parts.append(f"subject:{subject_contains}")
        _poll = lambda: search_messages(box, " ".join(parts))  # noqa: E731
    else:
        _poll = lambda: get_messages(box)  # noqa: E731

    deadline  = time.monotonic() + timeout
    seen_ids: set[str] = set()

    while time.monotonic() < deadline:
        msgs = await _poll()
        for m in reversed(msgs):
            mid = m.get("id", "")
            if mid in seen_ids:
                continue
            seen_ids.add(mid)

            from_ok    = not from_contains    or from_contains.lower()    in m.get("from", "").lower()
            subject_ok = not subject_contains or subject_contains.lower() in m.get("subject", "").lower()
            if from_ok and subject_ok:
                _log(f"[gmail] Nhan duoc email: subject='{m.get('subject', '')}'")
                return m

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        _log(f"[gmail] Chua co email phu hop, thu lai sau {poll_interval}s...")
        await asyncio.sleep(min(poll_interval, remaining))

    _log(f"[gmail] Timeout {timeout}s -- khong nhan duoc email khop filter")
    return None

