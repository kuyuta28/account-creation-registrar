"""
scripts/migrate_gmail_router.py — One-shot codemod to remove all SQLite
fallback paths from registrar/src/api/routers/gmail.py.

Inputs:
  - source: registrar/src/api/routers/gmail.py (read)
  - target: registrar/src/api/routers/gmail.py (written)

What it does:
  1. Strips `_db_path()` helper definition.
  2. Removes `from src.core.storage import db_path` (now unused).
  3. Replaces every `await asyncio.to_thread(<sync_fn>, _db_path(), *args)`:
       await asyncio.to_thread(sync_fn, _db_path(), email)
     into:
       async with get_async_session() as session:
           result = await async_fn(session, email)
     where `async_fn` is the corresponding _async variant.

  4. Replaces every `await <inbox_fn>(_db_path(), *args)`:
       msgs = await list_inbox(_db_path(), email, unread_only)
     into:
       msgs = await list_inbox(email, unread_only)
     (the inbox service has already been migrated to drop the db_path arg).

  5. Removes the import `asyncio` if no longer used.

Run this from the registrar repo root:
    python scripts/migrate_gmail_router.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

PATH = Path(__file__).resolve().parents[1] / "src/api/routers/gmail.py"

SYNC_TO_ASYNC = {
    "get_mailboxes": "get_mailboxes_async",
    "get_available_mailboxes_for_service": "get_available_mailboxes_for_service_async",
    "upsert_mailbox_record": "upsert_mailbox_record_async",
    "get_mailbox_record": "get_mailbox_record_async",
    "delete_mailbox_record": "delete_mailbox_record_async",
    "get_service_blocks": "get_service_blocks_async",
    "block_mailbox_for_service": "block_mailbox_for_service_async",
    "unblock_mailbox_for_service": "unblock_mailbox_for_service_async",
    "check_gmail_variations_availability": "check_gmail_variations_availability_async",
    "get_used_gmail_variations": "get_used_gmail_variations_async",
}


def find_balanced_paren(s: str, start: int) -> int:
    """Return index of the matching `)` for the `(` at `s[start]`."""
    assert s[start] == "("
    depth = 1
    i = start + 1
    while i < len(s) and depth > 0:
        ch = s[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    raise ValueError("unbalanced parens")


def transform(source: str) -> str:
    out: list[str] = []
    i = 0
    while i < len(source):
        # Pattern 1: `await asyncio.to_thread(<fn>, _db_path(), *rest)` -> async session block.
        idx = source.find("await asyncio.to_thread(", i)
        if idx != -1:
            out.append(source[i:idx])
            paren_start = idx + len("await asyncio.to_thread")
            paren_end = find_balanced_paren(source, paren_start)
            args_text = source[paren_start + 1:paren_end]
            rewritten = rewrite_to_thread(args_text)
            out.append(rewritten)
            i = paren_end + 1
            continue

        # Pattern 2: `await <inbox_fn>(_db_path(), *rest)` -> drop db_path.
        m = re.match(r"await (\w+)\(_db_path\(\),", source[i:])
        if m:
            name = m.group(1)
            paren_open = source.find("(", i)
            paren_end = find_balanced_paren(source, paren_open)
            args_text = source[paren_open + 1:paren_end]
            stripped = re.sub(r"^_db_path\(\),\s*", "", args_text)
            out.append(f"await {name}({stripped})")
            i = paren_end + 1
            continue

        out.append(source[i])
        i += 1

    result = "".join(out)

    # Strip the `_db_path()` helper definition entirely.
    result = re.sub(
        r"\n\ndef _db_path\(\):.*?\n\n(?=def )",
        "\n\n",
        result,
        count=1,
        flags=re.DOTALL,
    )
    # Drop the `from src.core.storage import db_path` line; nothing else
    # in the file uses it after _db_path is gone.
    result = re.sub(
        r"^from src\.core\.storage import db_path\s*\n",
        "",
        result,
        flags=re.MULTILINE,
    )
    return result


def rewrite_to_thread(args_text: str) -> str:
    """Rewrite the *contents* of `asyncio.to_thread(<fn>, ...)` into the
    `async with get_async_session() as session:` block."""
    # Find first top-level comma.
    depth = 0
    sep = -1
    for k, ch in enumerate(args_text):
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        elif ch == "," and depth == 0:
            sep = k
            break
    if sep == -1:
        raise SystemExit(f"cannot parse to_thread args: {args_text[:80]!r}")
    fn = args_text[:sep].strip()
    rest = args_text[sep + 1:].strip()
    if fn not in SYNC_TO_ASYNC:
        raise SystemExit(f"unknown sync fn: {fn!r}")
    async_fn = SYNC_TO_ASYNC[fn]
    if rest.startswith("_db_path(),"):
        rest = rest[len("_db_path(),"):].strip()
    elif rest == "_db_path()":
        rest = ""
    return (
        f"async with get_async_session() as session:\n        "
        f"await {async_fn}(session, {rest})"
    )


def main() -> None:
    original_bytes = PATH.read_bytes()
    if original_bytes.startswith(b"\xef\xbb\xbf"):
        original_bytes = original_bytes[3:]
    original = original_bytes.decode("utf-8")
    rewritten = transform(original)
    if rewritten == original:
        raise SystemExit("no changes made; patterns not matched")
    PATH.write_bytes(rewritten.encode("utf-8"))
    print(f"rewrote {PATH}")


if __name__ == "__main__":
    main()
