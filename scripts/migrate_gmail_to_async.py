"""
Migrate src/api/routers/gmail.py from sync SQLite to async Postgres.
Run from registrar repo root:
    python scripts/migrate_gmail_to_async.py
"""
from __future__ import annotations

import re
from pathlib import Path

PATH = Path(__file__).resolve().parents[1] / "src/api/routers/gmail.py"


def find_balanced(s: str, start: int) -> int:
    depth = 1
    i = start + 1
    while i < len(s) and depth > 0:
        if s[i] == "(":
            depth += 1
        elif s[i] == ")":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


# Map sync -> async for all functions called in gmail.py
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


def transform(source: str) -> str:
    out: list[str] = []
    i = 0
    while i < len(source):
        # Pattern 1: await asyncio.to_thread(<fn>, _db_path(), *rest)
        idx = source.find("await asyncio.to_thread(", i)
        if idx == -1:
            out.append(source[i:])
            break
        out.append(source[i:idx])
        paren_start = idx + len("await asyncio.to_thread")
        paren_end = find_balanced(source, paren_start)
        if paren_end == -1:
            out.append(source[idx:])
            break
        args = source[paren_start + 1:paren_end]
        # Find first top-level comma
        depth = 0
        sep = -1
        for k, ch in enumerate(args):
            if ch in "([{":
                depth += 1
            elif ch in ")]}":
                depth -= 1
            elif ch == "," and depth == 0:
                sep = k
                break
        if sep == -1:
            out.append(source[idx:paren_end + 1])
            i = paren_end + 1
            continue
        fn = args[:sep].strip()
        rest = args[sep + 1:].strip()
        if fn not in SYNC_TO_ASYNC:
            # Unknown sync fn — leave as-is
            out.append(source[idx:paren_end + 1])
            i = paren_end + 1
            continue
        async_fn = SYNC_TO_ASYNC[fn]
        # Drop leading `_db_path(),`
        if rest.startswith("_db_path(),"):
            rest = rest[len("_db_path(),"):].strip()
        line_start = source.rfind("\n", 0, idx) + 1
        line_text = source[line_start:idx]
        indent = source[line_start:line_start + (len(line_text) - len(line_text.lstrip()))]
        m_assign = re.match(r"^(\s*)(\w+)\s*=\s*$", line_text)
        if m_assign:
            var = m_assign.group(2)
            new_call = (
                f"async with get_async_session() as session:\n"
                f"{indent}    {var} = await {async_fn}(session, {rest})"
            )
        else:
            new_call = (
                f"async with get_async_session() as session:\n"
                f"{indent}    await {async_fn}(session, {rest})"
            )
        out.append(new_call)
        i = paren_end + 1
    return "".join(out)


def main() -> None:
    b = PATH.read_bytes()
    if b.startswith(b"\xef\xbb\xbf"):
        b = b[3:]
    s = b.decode("utf-8")
    new = transform(s)
    if new == s:
        raise SystemExit("no changes")
    PATH.write_bytes(new.encode("utf-8"))
    print(f"rewrote {PATH}")


if __name__ == "__main__":
    main()
