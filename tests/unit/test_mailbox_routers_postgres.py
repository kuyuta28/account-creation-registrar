from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
GMAIL_ROUTER = ROOT / "src" / "api" / "routers" / "gmail.py"
SMS_ROUTER = ROOT / "src" / "api" / "routers" / "sms.py"


def test_gmail_router_uses_async_postgres_helpers():
    source = GMAIL_ROUTER.read_text(encoding="utf-8")

    assert "get_async_session" in source
    assert "get_mailboxes_async" in source
    assert "asyncio.to_thread" not in source
    assert "src.core.storage import db_path" not in source
    assert "get_mailboxes," not in source
    assert "upsert_mailbox_record," not in source


def test_sms_router_uses_async_postgres_helpers():
    source = SMS_ROUTER.read_text(encoding="utf-8")

    assert "get_async_session" in source
    assert "get_sms_phones_async" in source
    assert "asyncio.to_thread" not in source
    assert "src.core.storage import db_path" not in source
    assert "get_sms_phones," not in source
    assert "upsert_sms_phone," not in source
