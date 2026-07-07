"""
unit/test_database.py — Tests cho common/database.py

Dùng real SQLite trong tmpdir, không mock gì cả.
Bao phủ: init_db, CRUD, upsert, bulk, update_bulk.
"""
from __future__ import annotations

import pytest

from sqlalchemy import update as sa_update
from sqlalchemy.orm import Session

# Use common.database for shared functions
from common.database import (
    _MailProvider,
    _get_engine,
    bulk_insert,
    count_accounts,
    delete_account,
    delete_accounts,
    get_account_by_email,
    get_accounts,
    get_mail_providers,
    init_db,
    insert_account,
    update_account,
    update_accounts_bulk,
    upsert_account,
    upsert_mail_provider,
)
# AccountRecord is in registrar's src.core.storage
from src.core.storage import AccountRecord


def _rec(email="a@b.com", service="ELEVENLABS", **kw) -> AccountRecord:
    return AccountRecord(service=service, email=email, password="P@ssw0rd!", **kw)


class TestInitDb:
    def test_creates_db_file(self, tmp_path):
        db = tmp_path / "new.db"
        assert not db.exists()
        init_db(db)
        assert db.exists()

    def test_idempotent(self, tmp_db):
        # calling init_db again on same db should not raise
        init_db(tmp_db)


class TestInsertAndGet:
    def test_insert_and_get_by_email(self, tmp_db):
        insert_account(tmp_db, _rec(api_key="sk_test"))
        row = get_account_by_email(tmp_db, "ELEVENLABS", "a@b.com")
        assert row is not None
        assert row["email"] == "a@b.com"
        assert row["api_key"] == "sk_test"
        assert row["service"] == "ELEVENLABS"

    def test_get_unknown_email_returns_none(self, tmp_db):
        row = get_account_by_email(tmp_db, "ELEVENLABS", "nobody@nowhere.com")
        assert row is None

    def test_insert_duplicate_ignored(self, tmp_db):
        """INSERT IGNORE on duplicate service+email."""
        insert_account(tmp_db, _rec(api_key="first"))
        insert_account(tmp_db, _rec(api_key="second"))  # duplicate
        row = get_account_by_email(tmp_db, "ELEVENLABS", "a@b.com")
        assert row["api_key"] == "first"  # first wins

    def test_get_accounts_all(self, tmp_db):
        insert_account(tmp_db, _rec("a@a.com", "ELEVENLABS"))
        insert_account(tmp_db, _rec("b@b.com", "OPENROUTER"))
        all_rows = get_accounts(tmp_db)
        assert len(all_rows) == 2

    def test_get_accounts_filtered_by_service(self, tmp_db):
        insert_account(tmp_db, _rec("a@a.com", "ELEVENLABS"))
        insert_account(tmp_db, _rec("b@b.com", "OPENROUTER"))
        rows = get_accounts(tmp_db, "ELEVENLABS")
        assert len(rows) == 1
        assert rows[0]["email"] == "a@a.com"

    def test_get_accounts_empty_service(self, tmp_db):
        insert_account(tmp_db, _rec("a@a.com", "ELEVENLABS"))
        rows = get_accounts(tmp_db, "CHATGPT")
        assert rows == []


class TestUpdateAccount:
    def test_update_sets_fields(self, tmp_db):
        insert_account(tmp_db, _rec())
        ok = update_account(tmp_db, "ELEVENLABS", "a@b.com", disabled=True, api_key="sk_new")
        assert ok is True
        row = get_account_by_email(tmp_db, "ELEVENLABS", "a@b.com")
        assert row["disabled"] is True
        assert row["api_key"] == "sk_new"

    def test_update_nonexistent_returns_false(self, tmp_db):
        ok = update_account(tmp_db, "ELEVENLABS", "ghost@nowhere.com", disabled=True)
        assert ok is False


class TestDeleteAccount:
    def test_delete_removes_record(self, tmp_db):
        insert_account(tmp_db, _rec())
        ok = delete_account(tmp_db, "ELEVENLABS", "a@b.com")
        assert ok is True
        assert get_account_by_email(tmp_db, "ELEVENLABS", "a@b.com") is None

    def test_delete_nonexistent_returns_false(self, tmp_db):
        assert delete_account(tmp_db, "ELEVENLABS", "noone@none.com") is False

    def test_delete_accounts_batch(self, tmp_db):
        for i in range(3):
            insert_account(tmp_db, _rec(f"u{i}@x.com"))
        deleted = delete_accounts(tmp_db, "ELEVENLABS", {"u0@x.com", "u1@x.com"})
        assert deleted == 2
        assert get_account_by_email(tmp_db, "ELEVENLABS", "u2@x.com") is not None


class TestUpsertAccount:
    def test_upsert_inserts_when_new(self, tmp_db):
        upsert_account(tmp_db, _rec(api_key="initial"))
        row = get_account_by_email(tmp_db, "ELEVENLABS", "a@b.com")
        assert row["api_key"] == "initial"

    def test_upsert_updates_when_exists(self, tmp_db):
        insert_account(tmp_db, _rec(api_key="old"))
        upsert_account(tmp_db, _rec(api_key="new"))
        row = get_account_by_email(tmp_db, "ELEVENLABS", "a@b.com")
        assert row["api_key"] == "new"


class TestCountAccounts:
    def test_count_zero_when_empty(self, tmp_db):
        assert count_accounts(tmp_db, "ELEVENLABS") == 0

    def test_count_matches_inserts(self, tmp_db):
        for i in range(5):
            insert_account(tmp_db, _rec(f"u{i}@x.com"))
        assert count_accounts(tmp_db, "ELEVENLABS") == 5


class TestBulkInsert:
    def test_bulk_insert_returns_count(self, tmp_db):
        records = [_rec(f"u{i}@x.com", "CHATGPT") for i in range(5)]
        n = bulk_insert(tmp_db, records)
        assert n == 5

    def test_bulk_insert_all_retrievable(self, tmp_db):
        records = [_rec(f"u{i}@x.com") for i in range(3)]
        bulk_insert(tmp_db, records)
        rows = get_accounts(tmp_db, "ELEVENLABS")
        assert len(rows) == 3

    def test_bulk_insert_empty_returns_zero(self, tmp_db):
        assert bulk_insert(tmp_db, []) == 0


class TestUpdateAccountsBulk:
    def test_bulk_update_modifies_all(self, tmp_db):
        for i in range(3):
            insert_account(tmp_db, _rec(f"u{i}@x.com"))
        updates = [{"email": f"u{i}@x.com", "api_key": f"sk_{i}"} for i in range(3)]
        count = update_accounts_bulk(tmp_db, "ELEVENLABS", updates)
        # Returns count of all operations: 3 base updates + 3 extension upserts = 6
        assert count == 6
        for i in range(3):
            row = get_account_by_email(tmp_db, "ELEVENLABS", f"u{i}@x.com")
            assert row["api_key"] == f"sk_{i}"


# ── mail_providers + provider_domain_tags ────────────────────────────────────


class TestMailProvidersDB:
    """Tests cho mail_providers + provider_domain_tags — real SQLite, zero mocks."""

    def test_init_db_seeds_mail_tm(self, tmp_db):
        rows = get_mail_providers(tmp_db)
        assert any(r["connection_str"] == "https://api.mail.tm" for r in rows)

    def test_upsert_creates_provider(self, tmp_db):
        upsert_mail_provider(tmp_db, "mailosaur.com", api_key="sk_unitabc", label="unit")
        rows = get_mail_providers(tmp_db)
        assert any(r["connection_str"] == "mailosaur.com:sk_unitabc" for r in rows)

    def test_upsert_returns_integer_id(self, tmp_db):
        pid = upsert_mail_provider(tmp_db, "mailosaur.com", api_key="sk_id_check")
        assert isinstance(pid, int)
        assert pid > 0

    def test_upsert_idempotent_no_duplicate_rows(self, tmp_db):
        for _ in range(3):
            upsert_mail_provider(tmp_db, "mailosaur.com", api_key="sk_idem")
        matching = [r for r in get_mail_providers(tmp_db) if r["connection_str"] == "mailosaur.com:sk_idem"]
        assert len(matching) == 1

    def test_get_returns_all_active_providers(self, tmp_db):
        upsert_mail_provider(tmp_db, "mailosaur.com", api_key="sk_a")
        upsert_mail_provider(tmp_db, "mailosaur.com", api_key="sk_b")
        conn_strs = {r["connection_str"] for r in get_mail_providers(tmp_db)}
        assert "mailosaur.com:sk_a" in conn_strs
        assert "mailosaur.com:sk_b" in conn_strs

    def test_new_domain_has_no_tags(self, tmp_db):
        """Domain mới không tự động có tags — user phải gán qua UI."""
        upsert_mail_provider(tmp_db, "mailosaur.com", api_key="sk_any_tag")
        # Không có tags → không visible cho bất kỳ service nào
        rows = get_mail_providers(tmp_db, service_tag="chatgpt")
        assert not any(r["connection_str"] == "mailosaur.com:sk_any_tag" for r in rows)
        # Nhưng vẫn visible khi query all (không filter service)
        all_rows = get_mail_providers(tmp_db)
        assert any(r["connection_str"] == "mailosaur.com:sk_any_tag" for r in all_rows)

    def test_specific_tag_only_visible_to_that_service(self, tmp_db):
        from common.database import set_provider_domain_tags
        upsert_mail_provider(tmp_db, "testmail.app", api_key="uuid-tag-test", server_id="ns1")
        # Restrict testmail.app domain đến only "testmail" tag
        set_provider_domain_tags(tmp_db, "testmail.app", ["testmail"])
        assert any(
            r["connection_str"] == "testmail.app:ns1:uuid-tag-test"
            for r in get_mail_providers(tmp_db, service_tag="testmail")
        )
        assert not any(
            r["connection_str"] == "testmail.app:ns1:uuid-tag-test"
            for r in get_mail_providers(tmp_db, service_tag="openrouter")
        )

    def test_disabled_provider_excluded(self, tmp_db):
        upsert_mail_provider(tmp_db, "mailosaur.com", api_key="sk_will_disable")
        with Session(_get_engine(tmp_db)) as s:
            s.execute(
                sa_update(_MailProvider)
                .where(
                    _MailProvider.provider_type == "mailosaur.com",
                    _MailProvider.api_key == "sk_will_disable",
                )
                .values(disabled=True)
            )
            s.commit()
        rows = get_mail_providers(tmp_db)
        assert not any(r["connection_str"] == "mailosaur.com:sk_will_disable" for r in rows)

    def test_row_has_expected_keys(self, tmp_db):
        upsert_mail_provider(tmp_db, "mailosaur.com", api_key="sk_fields", label="test_label")
        row = next(r for r in get_mail_providers(tmp_db) if r["connection_str"] == "mailosaur.com:sk_fields")
        for key in ("id", "provider_type", "api_key", "server_id", "connection_str", "label", "disabled", "fail_count", "created_at"):
            assert key in row, f"missing key: {key}"
        assert row["label"] == "test_label"
        assert row["provider_type"] == "mailosaur.com"
        assert row["api_key"] == "sk_fields"
        assert row["server_id"] == ""
        assert row["disabled"] is False

    def test_nonexistent_db_returns_empty(self, tmp_path):
        rows = get_mail_providers(tmp_path / "ghost.db")
        assert rows == []

    def test_service_tag_none_returns_all(self, tmp_db):
        upsert_mail_provider(tmp_db, "mailosaur.com", api_key="sk_all")
        upsert_mail_provider(tmp_db, "testmail.app", api_key="uuid-all", server_id="ns2")
        all_rows = get_mail_providers(tmp_db, service_tag=None)
        conn_strs = {r["connection_str"] for r in all_rows}
        assert "mailosaur.com:sk_all" in conn_strs
        assert "testmail.app:ns2:uuid-all" in conn_strs

