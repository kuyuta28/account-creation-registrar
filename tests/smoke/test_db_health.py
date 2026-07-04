"""
smoke/test_db_health.py — DB smoke tests: fast sanity checks, no network.

Chạy < 1s. Mục đích: phát hiện ngay nếu DB schema, migrations,
hoặc mail_providers seed bị vỡ sau khi thay đổi code.
"""
from __future__ import annotations

import pytest

from src.core.database import (
    _engines,
    get_distinct_services,
    get_mail_providers,
    init_db,
    insert_account,
    upsert_mail_provider,
)
from src.core.storage import AccountRecord


@pytest.fixture(scope="module")
def smoke_db(tmp_path_factory):
    """Module-scoped DB: tạo một lần, dùng cho mọi smoke test."""
    db_path = tmp_path_factory.mktemp("smoke") / "smoke.db"
    init_db(db_path)
    yield db_path
    key = str(db_path.resolve())
    engine = _engines.pop(key, None)
    if engine:
        engine.dispose()


def test_init_db_creates_file(tmp_path):
    db = tmp_path / "new_smoke.db"
    assert not db.exists()
    init_db(db)
    assert db.exists()
    key = str(db.resolve())
    engine = _engines.pop(key, None)
    if engine:
        engine.dispose()


def test_init_db_idempotent(smoke_db):
    """Gọi init_db lần 2 không raise."""
    init_db(smoke_db)


def test_mail_tm_no_auto_tags(smoke_db):
    """mail.tm không tự động có tags — user gán qua UI."""
    for svc in get_distinct_services(smoke_db):
        rows = get_mail_providers(smoke_db, service_tag=svc)
        assert not any(r["connection_str"] == "https://api.mail.tm" for r in rows), (
            f"mail.tm KHÔNG được tự động có tag cho service '{svc}'"
        )


def test_upsert_and_get_provider(smoke_db):
    """Upsert 1 provider → get_mail_providers trả về đúng."""
    upsert_mail_provider(smoke_db, "mailslurp_legacy.local", api_key="sk_smoke_test")
    strs = {r["connection_str"] for r in get_mail_providers(smoke_db)}
    assert "mailslurp_legacy.local:sk_smoke_test" in strs


def test_insert_account_and_retrieve(smoke_db):
    """Bảng accounts hoạt động bình thường."""
    from src.core.database import get_account_by_email
    rec = AccountRecord(service="ELEVENLABS", email="smoke@test.invalid", password="Smoke@1234!")
    insert_account(smoke_db, rec)
    row = get_account_by_email(smoke_db, "ELEVENLABS", "smoke@test.invalid")
    assert row is not None
    assert row["email"] == "smoke@test.invalid"


def test_db_has_both_tables(smoke_db):
    """Verify schema: cả 'accounts' lẫn 'mail_providers' đều tồn tại."""
    from sqlalchemy import inspect as sa_inspect
    from src.core.database import _get_engine
    inspector = sa_inspect(_get_engine(smoke_db))
    table_names = set(inspector.get_table_names())
    assert "accounts" in table_names
    assert "mail_providers" in table_names
    assert "provider_domain_tags" in table_names
