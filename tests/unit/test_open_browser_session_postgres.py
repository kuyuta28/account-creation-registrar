from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OPEN_BROWSER_SESSION = ROOT / "src" / "api" / "tools" / "open_browser_session.py"


def test_open_browser_session_loads_sessions_from_postgres():
    source = OPEN_BROWSER_SESSION.read_text(encoding="utf-8")

    assert "get_async_session" in source
    assert "get_account_by_email_async" in source
    assert "get_mailbox_record_async" in source
    assert "sqlite3" not in source
    assert "SELECT session_state FROM accounts" not in source
    assert "_get_db_path" not in source
