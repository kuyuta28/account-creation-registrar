from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROVIDERS_ROUTER = ROOT / "src" / "api" / "routers" / "providers.py"


def test_providers_router_uses_async_postgres_helpers():
    source = PROVIDERS_ROUTER.read_text(encoding="utf-8")

    assert "get_async_session" in source
    assert "get_provider_domains_async" in source
    assert "asyncio.to_thread" not in source
    assert "load_config().mail.db_path" not in source
    assert "from common.database import" not in source
