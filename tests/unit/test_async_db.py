"""
unit/test_async_db.py — Tests cho async database operations.

Bao phủ:
  - _async.py: insert_account_async, get_account_by_email_async, update_account_async
  - _providers_async.py: get_providers_async, upsert_provider_async
  - _engine.py: init_async_db, get_async_session

Uses real PostgreSQL (test container or existing dev instance).
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import MagicMock

import pytest


# ── Skip if no PostgreSQL ──────────────────────────────────────────────────────

def _has_postgres():
    import os
    return bool(os.getenv("DATABASE_URL"))


pytestmark = pytest.mark.skipif(
    not _has_postgres(),
    reason="DATABASE_URL not set — requires PostgreSQL",
)


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def db_url():
    import os
    return os.getenv("DATABASE_URL")


@pytest.fixture
async def engine(db_url):
    from common.database._engine import init_async_db, get_async_engine
    init_async_db(db_url)
    eng = get_async_engine()
    yield eng
    await eng.dispose()


@pytest.fixture
async def session(engine):
    from common.database._engine import get_async_session
    async with get_async_session() as sess:
        yield sess


# ── _engine: init_async_db ────────────────────────────────────────────────────


class TestAsyncEngineInit:
    def test_init_sets_engine(self, db_url):
        from common.database._engine import init_async_db, get_async_engine
        init_async_db(db_url)
        eng = get_async_engine()
        assert eng is not None

    @pytest.mark.asyncio
    async def test_session_executes_query(self, db_url):
        from common.database._engine import init_async_db, get_async_session
        from sqlalchemy import text
        init_async_db(db_url)
        async with get_async_session() as sess:
            result = await sess.execute(text("SELECT 1 as test"))
            assert result.scalar() == 1

    @pytest.mark.asyncio
    async def test_session_commits_transaction(self, db_url):
        from common.database._engine import init_async_db, get_async_session
        from sqlalchemy import text
        init_async_db(db_url)
        async with get_async_session() as sess:
            await sess.execute(text("SELECT 1"))
            await sess.commit()


# ── _async: insert_account_async ───────────────────────────────────────────────


class TestInsertAccountAsync:
    @pytest.mark.asyncio
    async def test_insert_new_account(self, db_url):
        from common.database._engine import init_async_db, get_async_session
        from common.database._async import insert_account_async

        init_async_db(db_url)

        class FakeRecord:
            service = "TEST"
            email = "async-test@test.com"
            password = "pass123"
            created_at = "2026-04-24 00:00:00 UTC"

        async with get_async_session() as sess:
            result = await insert_account_async(sess, FakeRecord())
            assert result is True

        # Cleanup
        from sqlalchemy import text
        async with get_async_session() as sess:
            await sess.execute(
                text("DELETE FROM accounts WHERE service = 'TEST' AND email = 'async-test@test.com'")
            )
            await sess.commit()

    @pytest.mark.asyncio
    async def test_insert_duplicate_returns_false(self, db_url):
        from common.database._engine import init_async_db, get_async_session
        from common.database._async import insert_account_async

        init_async_db(db_url)

        class FakeRecord:
            service = "TEST"
            email = "async-dup@test.com"
            password = "pass123"
            created_at = "2026-04-24 00:00:00 UTC"

        async with get_async_session() as sess:
            await insert_account_async(sess, FakeRecord())
            # Try insert again
            result = await insert_account_async(sess, FakeRecord())
            assert result is False

        # Cleanup
        from sqlalchemy import text
        async with get_async_session() as sess:
            await sess.execute(
                text("DELETE FROM accounts WHERE service = 'TEST' AND email = 'async-dup@test.com'")
            )
            await sess.commit()

    @pytest.mark.asyncio
    async def test_insert_with_extension_data(self, db_url):
        from sqlalchemy import text
        from common.database._engine import init_async_db, get_async_session
        from common.database._async import insert_account_async

        init_async_db(db_url)

        class FakeRecord:
            service = "OPENROUTER"
            email = "async-or@test.com"
            password = "pass123"
            created_at = "2026-04-24 00:00:00 UTC"

        ext_data = {
            "api_key": "sk-test-or-async",
            "credits": 1000,
        }

        async with get_async_session() as sess:
            await insert_account_async(sess, FakeRecord(), ext_data=ext_data)
            result = await sess.execute(
                text("SELECT api_key FROM accounts_openrouter WHERE account_id = (SELECT id FROM accounts WHERE email = 'async-or@test.com')")
            )
            row = result.scalar_one_or_none()
            assert row == "sk-test-or-async"

        # Cleanup
        async with get_async_session() as sess:
            await sess.execute(
                text("DELETE FROM accounts WHERE email = 'async-or@test.com'")
            )
            await sess.commit()


# ── _async: get_account_by_email_async ───────────────────────────────────────


class TestGetAccountByEmailAsync:
    @pytest.mark.asyncio
    async def test_get_existing_account(self, db_url):
        from common.database._engine import init_async_db, get_async_session
        from common.database._async import insert_account_async, get_account_by_email_async

        init_async_db(db_url)

        class FakeRecord:
            service = "TEST"
            email = "async-get@test.com"
            password = "secret456"
            created_at = "2026-04-24 00:00:00 UTC"

        async with get_async_session() as sess:
            await insert_account_async(sess, FakeRecord())
            account = await get_account_by_email_async(sess, "TEST", "async-get@test.com")
            assert account is not None
            assert account["email"] == "async-get@test.com"
            assert account["password"] == "secret456"

        # Cleanup
        from sqlalchemy import text
        async with get_async_session() as sess:
            await sess.execute(
                text("DELETE FROM accounts WHERE email = 'async-get@test.com'")
            )
            await sess.commit()

    @pytest.mark.asyncio
    async def test_get_nonexistent_returns_none(self, db_url):
        from common.database._engine import init_async_db, get_async_session
        from common.database._async import get_account_by_email_async

        init_async_db(db_url)

        async with get_async_session() as sess:
            account = await get_account_by_email_async(sess, "NONEXISTENT", "not@found.com")
            assert account is None


# ── _async: update_account_async ──────────────────────────────────────────────


class TestUpdateAccountAsync:
    @pytest.mark.asyncio
    async def test_update_existing_account(self, db_url):
        from common.database._engine import init_async_db, get_async_session
        from common.database._async import insert_account_async, update_account_async

        init_async_db(db_url)

        class FakeRecord:
            service = "TEST"
            email = "async-update@test.com"
            password = "oldpass"
            created_at = "2026-04-24 00:00:00 UTC"

        async with get_async_session() as sess:
            await insert_account_async(sess, FakeRecord())
            count = await update_account_async(sess, "TEST", "async-update@test.com", {"password": "newpass"})
            assert count == 1

            # Verify update
            from common.database._async import get_account_by_email_async
            account = await get_account_by_email_async(sess, "TEST", "async-update@test.com")
            assert account["password"] == "newpass"

        # Cleanup
        from sqlalchemy import text
        async with get_async_session() as sess:
            await sess.execute(
                text("DELETE FROM accounts WHERE email = 'async-update@test.com'")
            )
            await sess.commit()

    @pytest.mark.asyncio
    async def test_update_nonexistent_returns_zero(self, db_url):
        from common.database._engine import init_async_db, get_async_session
        from common.database._async import update_account_async

        init_async_db(db_url)

        async with get_async_session() as sess:
            count = await update_account_async(sess, "NONEXISTENT", "not@found.com", {"password": "x"})
            assert count == 0


# ── _providers_async: get_providers_async ─────────────────────────────────────


class TestGetProvidersAsync:
    @pytest.mark.asyncio
    async def test_get_all_active_providers(self, db_url):
        from common.database._engine import init_async_db, get_async_session
        from common.database._providers_async import get_providers_async

        init_async_db(db_url)

        async with get_async_session() as sess:
            providers = await get_providers_async(sess)
            assert isinstance(providers, list)

    @pytest.mark.asyncio
    async def test_get_providers_with_tag(self, db_url):
        from common.database._engine import init_async_db, get_async_session
        from common.database._providers_async import get_providers_async

        init_async_db(db_url)

        async with get_async_session() as sess:
            providers = await get_providers_async(sess, service_tag="elevenlabs")
            assert isinstance(providers, list)


# ── _providers_async: upsert_provider_async ────────────────────────────────────


class TestUpsertProviderAsync:
    @pytest.mark.asyncio
    async def test_insert_new_provider(self, db_url):
        from common.database._engine import init_async_db, get_async_session
        from common.database._providers_async import upsert_provider_async

        init_async_db(db_url)

        async with get_async_session() as sess:
            pid = await upsert_provider_async(
                sess,
                provider_type="testprovider.test",
                api_key="test-key-async",
                server_id="test-server",
                label="Test Provider Async",
            )
            assert pid > 0

        # Cleanup
        from sqlalchemy import text
        async with get_async_session() as sess:
            await sess.execute(
                text("DELETE FROM mail.mail_providers WHERE provider_type = 'testprovider.test'")
            )
            await sess.commit()

    @pytest.mark.asyncio
    async def test_upsert_updates_existing(self, db_url):
        from common.database._engine import init_async_db, get_async_session
        from common.database._providers_async import upsert_provider_async

        init_async_db(db_url)

        async with get_async_session() as sess:
            pid1 = await upsert_provider_async(
                sess,
                provider_type="testprovider2.test",
                api_key="key1",
                label="First Label",
            )
            pid2 = await upsert_provider_async(
                sess,
                provider_type="testprovider2.test",
                api_key="key1",
                label="Updated Label",
            )
            # Same row updated, not new insert
            assert pid1 == pid2

        # Cleanup
        from sqlalchemy import text
        async with get_async_session() as sess:
            await sess.execute(
                text("DELETE FROM mail.mail_providers WHERE provider_type = 'testprovider2.test'")
            )
            await sess.commit()
