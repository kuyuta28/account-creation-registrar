from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SYNC_SERVICE = ROOT / "src" / "api" / "services" / "sync_service.py"
NINEROUTER_SYNC = ROOT / "src" / "api" / "services" / "ninerouter_sync.py"


def test_sync_service_uses_async_postgres_helpers():
    source = SYNC_SERVICE.read_text(encoding="utf-8")

    assert "get_async_session" in source
    assert "get_accounts_async" in source
    assert "asyncio.to_thread(get_accounts" not in source
    assert "src.core.storage import db_path" not in source
    assert "from common.database import get_accounts\n" not in source
    assert "from common.database import get_accounts," not in source


def test_ninerouter_sync_uses_async_postgres_helpers():
    source = NINEROUTER_SYNC.read_text(encoding="utf-8")

    assert "get_async_session" in source
    assert "get_accounts_async" in source
    assert "asyncio.to_thread(get_accounts" not in source
    assert "src.core.storage import db_path" not in source
    assert "from common.database import get_accounts\n" not in source
    assert "from common.database import get_accounts," not in source
