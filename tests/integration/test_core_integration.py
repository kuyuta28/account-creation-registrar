"""
integration/test_core_integration.py — Integration tests cho core/ modules.

Test full pipeline THẬT — không mock. Dùng SQLite tmpdir.

Bao phủ:
  - google_oauth package re-exports: import public API → no circular imports
  - storage + database pipeline: init_repo → repo_save → DB verify
  - enums used across layers: JobStatus/CheckStatus serialization roundtrip
  - gmail_variations + normalize: generate → normalize = base email
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.core.database import get_account_by_email, init_db
from src.core.database._engine import _engines
from src.core.storage import db_path


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def db(tmp_path) -> Path:
    real_db = db_path(tmp_path)
    real_db.parent.mkdir(parents=True, exist_ok=True)
    init_db(real_db)
    yield real_db
    key = str(real_db.resolve())
    engine = _engines.pop(key, None)
    if engine:
        engine.dispose()


# ── google_oauth package integration ─────────────────────────────────────────


class TestGoogleOAuthPackage:
    """Verify google_oauth/ package exports hoạt động — không circular imports."""

    def test_import_public_api(self):
        from src.core.google_oauth import (
            GOOGLE_SIGNIN_URL,
            LOGIN_TIMEOUT_MS,
            LogFn,
            detect_page_state,
            dump_page_html,
            handle_oauth_popup,
            login_google_on_page,
            short_url,
        )
        assert isinstance(GOOGLE_SIGNIN_URL, str)
        assert isinstance(LOGIN_TIMEOUT_MS, int)
        assert callable(detect_page_state)
        assert callable(handle_oauth_popup)
        assert callable(login_google_on_page)
        assert callable(dump_page_html)
        assert callable(short_url)

    def test_short_url_pure_function(self):
        from src.core.google_oauth import short_url
        url = "https://accounts.google.com/v3/signin/identifier?continue=https://example.com&very=long&query=params"
        result = short_url(url)
        assert len(result) < len(url)
        assert "accounts.google.com" in result

    def test_google_page_state_enum_available(self):
        from src.core.enums import GooglePageState
        from src.core.google_oauth import detect_page_state
        # detect_page_state trả GooglePageState → verify enum usable
        assert GooglePageState.LOGIN_EMAIL.value == "login_email"


# ── storage + database pipeline ──────────────────────────────────────────────


class TestStorageDatabasePipeline:
    """repo_save() → DB insert → get_account_by_email() verify."""

    def test_save_and_retrieve_elevenlabs(self, db, tmp_path):
        from src.core.storage import AccountRecord, Repo, init_repo, repo_save

        repo = Repo(base_dir=tmp_path)
        init_repo(repo)

        record = AccountRecord(
            service="ELEVENLABS",
            email="integ-el@test.com",
            password="P@ss1234",
            api_key="sk_integration_xyz",
        )
        repo_save(repo, record)

        row = get_account_by_email(db, "ELEVENLABS", "integ-el@test.com")
        assert row is not None
        assert row["email"] == "integ-el@test.com"
        assert row["api_key"] == "sk_integration_xyz"

    def test_save_chatgpt_codex_creates_auth_file(self, db, tmp_path):
        from src.core.storage import AccountRecord, Repo, init_repo, repo_save

        repo = Repo(base_dir=tmp_path)
        init_repo(repo)

        record = AccountRecord(
            service="CHATGPT",
            email="integ-codex@example.com",
            password="P@ssw0rd",
            refresh_token="rt_integ",
            access_token="at_integ",
            account_id="acc_integ",
            token_type="codex",
        )
        repo_save(repo, record)

        auth_path = tmp_path / "auth" / "codex-integ-codex@example.com-free.json"
        assert auth_path.exists()

        payload = json.loads(auth_path.read_text(encoding="utf-8"))
        assert payload["email"] == "integ-codex@example.com"
        assert payload["type"] == "codex"
        assert payload["refresh_token"] == "rt_integ"

    def test_save_multiple_services(self, db, tmp_path):
        from src.core.storage import AccountRecord, Repo, init_repo, repo_save

        repo = Repo(base_dir=tmp_path)
        init_repo(repo)

        for svc in ("ELEVENLABS", "CHATGPT", "LEONARDO"):
            record = AccountRecord(
                service=svc,
                email=f"multi-{svc.lower()}@test.com",
                password="pw",
            )
            repo_save(repo, record)

        for svc in ("ELEVENLABS", "CHATGPT", "LEONARDO"):
            row = get_account_by_email(db, svc, f"multi-{svc.lower()}@test.com")
            assert row is not None


# ── enums cross-layer ─────────────────────────────────────────────────────────


class TestEnumsCrossLayer:
    """Enums được dùng ở nhiều layer — verify serialization roundtrip."""

    def test_job_status_json_roundtrip(self):
        from src.core.enums import JobStatus
        status = JobStatus.RUNNING
        serialized = json.dumps({"status": status})
        deserialized = json.loads(serialized)
        assert deserialized["status"] == "running"
        assert JobStatus(deserialized["status"]) is JobStatus.RUNNING

    def test_check_status_json_roundtrip(self):
        from src.core.enums import CheckStatus
        for s in CheckStatus:
            serialized = json.dumps({"result": s})
            deserialized = json.loads(serialized)
            assert CheckStatus(deserialized["result"]) is s

    def test_error_code_used_in_schemas(self):
        from src.api.schemas import ErrorCode
        from src.core.enums import ErrorCode as CoreErrorCode
        assert ErrorCode is CoreErrorCode  # re-export, not copy


# ── gmail_variations + normalize roundtrip ────────────────────────────────────


class TestGmailVariationsIntegration:
    """generate_variations → normalize_gmail = base email."""

    def test_all_variations_normalize_back(self):
        from src.core.gmail_variations import generate_variations, normalize_gmail

        base = "testuser@gmail.com"
        variations = generate_variations(base)

        for v in variations:
            normalized = normalize_gmail(v.email)
            assert normalized == base, (
                f"Variation {v.email!r} (technique={v.technique}) "
                f"normalized to {normalized!r}, expected {base!r}"
            )

    def test_dot_variations_are_unique(self):
        from src.core.gmail_variations import generate_variations

        results = generate_variations(
            "abc@gmail.com",
            use_plus=False, use_dot=True, use_googlemail=False,
        )
        emails = [r.email for r in results]
        assert len(emails) == len(set(emails)), "Duplicate dot variations found"
