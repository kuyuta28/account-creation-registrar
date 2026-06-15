from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CHECKER_SERVICE = ROOT / "src" / "api" / "services" / "checker_service.py"


def test_checker_service_uses_async_postgres_helpers():
    source = CHECKER_SERVICE.read_text(encoding="utf-8")

    assert "get_async_session" in source
    assert "get_accounts_async" in source
    assert "get_account_by_email_async" in source
    assert "update_account_async" in source
    assert "asyncio.to_thread(update_account" not in source
    assert "asyncio.to_thread(get_account_by_email" not in source
    assert "asyncio.to_thread(get_accounts" not in source
    assert "src.core.storage import db_path" not in source
