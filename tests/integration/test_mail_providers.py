"""
integration/test_mail_providers.py — Integration tests cho mail provider subsystem.

Dùng SQLite thật (tmpdir), KHÔNG mock gì cả.
Test full pipeline:
    upsert_mail_provider → DB → MailConfig.providers_for()

Bao phủ:
  - MailConfig.providers_for() query DB thật, không patch
  - Tag filtering end-to-end: per-domain tags
  - Domain mới không tự động có tags — user gán qua UI
  - Disabled provider bị lọc ra
  - Upsert idempotent: 5 lần insert = 1 row
  - DB không tồn tại → trả empty tuple
"""
from __future__ import annotations

from pathlib import Path

import pytest

from common.database import (
    _MailProvider,
    _get_engine,
    _engines,
    get_distinct_services,
    get_mail_providers,
    init_db,
    set_provider_domain_tags,
    upsert_mail_provider,
)


# ── Fixtures (scoped per-test, tmpdir SQLite) ─────────────────────────────────


@pytest.fixture
def db(tmp_path) -> Path:
    """Fresh SQLite DB seeded với mail.tm (qua init_db)."""
    db_path = tmp_path / "mail_integ.db"
    init_db(db_path)
    yield db_path
    # dispose engine để Windows không giữ lock file
    key = str(db_path.resolve())
    engine = _engines.pop(key, None)
    if engine:
        engine.dispose()


@pytest.fixture
def mail(db) -> "MailConfig":  # noqa: F821  — lazy import
    from src.config.settings import MailConfig
    return MailConfig(db_path=db)


# ── MailConfig.providers_for() với real DB ────────────────────────────────────


class TestMailConfigRealDB:
    """providers_for() gọi DB thật — không một dòng patch nào."""

    def test_seed_mail_tm_always_present(self, mail):
        providers = mail.providers_for()
        assert "https://api.mail.tm" in providers

    def test_upserted_provider_visible_in_all_providers(self, db, mail):
        upsert_mail_provider(db, "mailslurp.com", api_key="sk_integ_a")
        assert "mailslurp.com:sk_integ_a" in mail.providers_for()

    def test_new_domain_not_visible_for_service(self, db, mail):
        upsert_mail_provider(db, "mailslurp.com", api_key="sk_integ_b")
        # Domain mới không có tags → không visible cho service cụ thể
        providers = mail.providers_for("chatgpt")
        assert "mailslurp.com:sk_integ_b" not in providers

    def test_tagged_domain_visible_for_that_service(self, db, mail):
        upsert_mail_provider(db, "testmail.app", api_key="uuid-integ", server_id="ns_integ")
        set_provider_domain_tags(db, "testmail.app", ["testmail"])
        assert "testmail.app:ns_integ:uuid-integ" in mail.providers_for("testmail")

    def test_restricted_domain_invisible_to_other_service(self, db, mail):
        upsert_mail_provider(db, "testmail.app", api_key="uuid-x", server_id="ns_x")
        set_provider_domain_tags(db, "testmail.app", ["testmail"])
        assert "testmail.app:ns_x:uuid-x" not in mail.providers_for("openrouter")

    def test_providers_for_case_insensitive(self, db, mail):
        upsert_mail_provider(db, "mailslurp.com", api_key="sk_case")
        lower = mail.providers_for("chatgpt")
        upper = mail.providers_for("CHATGPT")
        assert set(lower) == set(upper)

    def test_disabled_provider_not_returned(self, db, mail):
        from sqlalchemy import update as sa_update
        from sqlalchemy.orm import Session

        upsert_mail_provider(db, "mailslurp.com", api_key="sk_disable_integ")
        with Session(_get_engine(db)) as s:
            s.execute(
                sa_update(_MailProvider)
                .where(
                    _MailProvider.provider_type == "mailslurp.com",
                    _MailProvider.api_key == "sk_disable_integ",
                )
                .values(disabled=True)
            )
            s.commit()
        assert "mailslurp.com:sk_disable_integ" not in mail.providers_for()

    def test_multiple_providers_all_returned(self, db, mail):
        for i in range(5):
            upsert_mail_provider(db, "mailslurp.com", api_key=f"sk_m{i}")
        providers = mail.providers_for()
        for i in range(5):
            assert f"mailslurp.com:sk_m{i}" in providers

    def test_upsert_idempotent_no_duplicate(self, db, mail):
        for _ in range(5):
            upsert_mail_provider(db, "mailslurp.com", api_key="sk_dup_integ")
        matching = [p for p in mail.providers_for() if p == "mailslurp.com:sk_dup_integ"]
        assert len(matching) == 1

    def test_missing_db_returns_empty(self, tmp_path):
        from src.config.settings import MailConfig
        mail_no_db = MailConfig(db_path=tmp_path / "nonexistent.db")
        providers = mail_no_db.providers_for()
        assert providers == ()


# ── Tag semantics ─────────────────────────────────────────────────────────────


class TestTagSemantics:
    """Per-domain tags — kiểm tra từng trường hợp."""

    def test_new_domain_no_auto_tags(self, db):
        upsert_mail_provider(db, "mailslurp.com", api_key="sk_universal")
        # Domain mới không tự động có tags — không visible cho bất kỳ service
        for svc in get_distinct_services(db):
            rows = get_mail_providers(db, service_tag=svc)
            assert not any(r["connection_str"] == "mailslurp.com:sk_universal" for r in rows), (
                f"Domain mới KHÔNG được tự động có tags, but found for: {svc}"
            )

    def test_restricted_domain_not_served_to_other_service(self, db):
        upsert_mail_provider(db, "testmail.app", api_key="uuid-spec", server_id="ns_spec")
        set_provider_domain_tags(db, "testmail.app", ["elevenlabs"])
        assert any(
            r["connection_str"] == "testmail.app:ns_spec:uuid-spec"
            for r in get_mail_providers(db, service_tag="elevenlabs")
        )
        assert not any(
            r["connection_str"] == "testmail.app:ns_spec:uuid-spec"
            for r in get_mail_providers(db, service_tag="chatgpt")
        )

    def test_set_domain_tags_affects_all_providers(self, db):
        upsert_mail_provider(db, "mailslurp.com", api_key="sk_multi_a")
        upsert_mail_provider(db, "mailslurp.com", api_key="sk_multi_b")
        set_provider_domain_tags(db, "mailslurp.com", ["chatgpt", "elevenlabs"])
        for svc in ("chatgpt", "elevenlabs"):
            rows = get_mail_providers(db, service_tag=svc)
            strs = {r["connection_str"] for r in rows}
            assert "mailslurp.com:sk_multi_a" in strs
            assert "mailslurp.com:sk_multi_b" in strs
        # openrouter not in tags → not returned
        rows_other = get_mail_providers(db, service_tag="openrouter")
        strs_other = {r["connection_str"] for r in rows_other}
        assert "mailslurp.com:sk_multi_a" not in strs_other

    def test_no_service_filter_returns_all_active(self, db):
        upsert_mail_provider(db, "mailslurp.com", api_key="sk_no_filter")
        upsert_mail_provider(db, "testmail.app", api_key="uuid-nf", server_id="ns_nf")
        all_strs = {r["connection_str"] for r in get_mail_providers(db)}
        assert "mailslurp.com:sk_no_filter" in all_strs
        assert "testmail.app:ns_nf:uuid-nf" in all_strs


# ── Data shape ────────────────────────────────────────────────────────────────


class TestProviderRowShape:
    """Verify cấu trúc dict trả về từ get_mail_providers."""

    def test_row_contains_required_fields(self, db):
        upsert_mail_provider(db, "mailslurp.com", api_key="sk_shape", label="shape_label")
        row = next(r for r in get_mail_providers(db) if r["connection_str"] == "mailslurp.com:sk_shape")
        for field in ("id", "provider_type", "api_key", "server_id", "connection_str",
                      "label", "disabled", "fail_count", "created_at", "updated_at"):
            assert field in row, f"Row thiếu field: {field}"

    def test_row_values_correct_types(self, db):
        upsert_mail_provider(db, "mailslurp.com", api_key="sk_types", label="types")
        row = next(r for r in get_mail_providers(db) if r["connection_str"] == "mailslurp.com:sk_types")
        assert isinstance(row["id"], int)
        assert isinstance(row["api_key"], str)
        assert isinstance(row["disabled"], bool)
        assert isinstance(row["fail_count"], int)
        assert row["disabled"] is False
        assert row["fail_count"] == 0

    def test_label_stored_correctly(self, db):
        upsert_mail_provider(db, "mailslurp.com", api_key="sk_lbl", label="custom-label-123")
        row = next(r for r in get_mail_providers(db) if r["connection_str"] == "mailslurp.com:sk_lbl")
        assert row["label"] == "custom-label-123"

    def test_provider_type_stored_correctly(self, db):
        upsert_mail_provider(db, "testmail.app", api_key="uuid-pt", server_id="ns_pt")
        row = next(r for r in get_mail_providers(db) if r["connection_str"] == "testmail.app:ns_pt:uuid-pt")
        assert row["provider_type"] == "testmail.app"
        assert row["api_key"] == "uuid-pt"
        assert row["server_id"] == "ns_pt"
