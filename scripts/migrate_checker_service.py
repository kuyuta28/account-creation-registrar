"""
Migrate src/api/services/checker_service.py from sync SQLite calls to
async Postgres. Run from registrar repo root:

    python scripts/migrate_checker_service.py
"""
from __future__ import annotations

import re
from pathlib import Path

PATH = Path(__file__).resolve().parents[1] / "src/api/services/checker_service.py"


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


SYNC_TO_ASYNC = {
    "update_account": "update_account_async",
    "get_accounts": "get_accounts_async",
    "get_account_by_email": "get_account_by_email_async",
}


def transform(source: str) -> str:
    out: list[str] = []
    i = 0
    while i < len(source):
        idx = source.find("await asyncio.to_thread(", i)
        if idx == -1:
            out.append(source[i:])
            break
        out.append(source[i:idx])
        paren_start = idx + len("await asyncio.to_thread")
        paren_end = find_balanced(source, paren_start)
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
        # Skip non-DB helpers (lambda, _del_acc, etc.) and inline lambdas
        # that have no top-level comma. Leave those calls as-is.
        if sep == -1 or "lambda" in args or "_del_acc" in args:
            out.append(source[idx:paren_end + 1])
            i = paren_end + 1
            continue
        fn = args[:sep].strip()
        rest = args[sep + 1:].strip()
        async_fn = SYNC_TO_ASYNC[fn]
        # Drop leading `_db_path(),` if present
        if rest.startswith("_db_path(),"):
            rest = rest[len("_db_path(),"):].strip()
        # Detect **kwargs (splat) at the end
        # We need to build session block. Use the indentation of the
        # original line to match.
        # Get leading indent of original line
        line_start = source.rfind("\n", 0, idx) + 1
        indent = source[line_start:idx]
        # Build the new call. The original may have been assigned to
        # a variable (e.g. `x = await asyncio.to_thread(...)`); when
        # we wrap it in a `with` block we must drop the `x = ` prefix
        # or Python raises a syntax error.
        line_end = source.find("\n", idx)
        prefix = source[idx:line_end]  # text after the original line starts
        # Detect `xxx = await` and drop the assignment
        # Use a regex to find the assignment form
        m_assign = re.match(r"\s*(\w+)\s*=\s*await asyncio\.to_thread\(", prefix)
        if m_assign:
            var = m_assign.group(1)
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
