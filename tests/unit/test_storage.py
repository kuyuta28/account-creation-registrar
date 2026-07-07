"""
unit/test_storage.py — Tests cho src/core/storage.py

Bao phủ: AccountRecord, serialize, codex auth export, sync functions.
Dùng real tmpdir, không mock file I/O.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from src.core.storage import (
    AccountRecord,
    Repo,
    build_codex_auth_path,
    build_target_codex_auth_path,
    export_codex_auth,
    export_openrouter_key,
    init_repo,
    is_auth_sync_enabled,
    matching_exporters,
    repo_save,
    safe_filename,
    serialize_account_record,
    should_export_codex_auth,
    should_export_openrouter_key,
    sync_auth_directory,
    sync_auth_file,
    sync_codex_auth_payload,
    write_json,
    read_json,
)
from src.config.settings import AuthSyncConfig, ClipRoxySyncConfig


# ── AccountRecord ─────────────────────────────────────────────────────────────

class TestAccountRecord:
    """AccountRecord dataclass + to_json_entry()"""

    def test_minimal_record(self):
        r = AccountRecord(service="ELEVENLABS", email="a@b.com", password="pw")
        assert r.service == "ELEVENLABS"
        assert r.email == "a@b.com"
        assert r.disabled is False

    def test_to_json_entry_basic(self):
        r = AccountRecord(service="ELEVENLABS", email="a@b.com", password="pw", api_key="sk_abc")
        d = serialize_account_record(r)
        assert d["email"] == "a@b.com"
        assert d["password"] == "pw"
        assert d["api_key"] == "sk_abc"
        assert "service" not in d

    def test_to_json_entry_omits_empty_api_key(self):
        r = AccountRecord(service="LEONARDO", email="a@b.com", password="pw")
        assert "api_key" not in serialize_account_record(r)

    def test_to_json_entry_omits_empty_tokens(self):
        r = AccountRecord(service="CHATGPT", email="a@b.com", password="pw")
        d = serialize_account_record(r)
        assert "refresh_token" not in d
        assert "access_token" not in d
        assert "id_token" not in d

    def test_to_json_entry_includes_timestamps_by_default(self):
        r = AccountRecord(service="ELEVENLABS", email="a@b.com", password="pw")
        d = serialize_account_record(r)
        assert "created_at" in d
        assert "updated_at" in d

    def test_to_json_entry_excludes_timestamps_when_false(self):
        r = AccountRecord(
            service="CHATGPT", email="a@b.com", password="pw",
            refresh_token="rt", token_type="codex",
        )
        d = serialize_account_record(r, include_timestamps=False)
        assert "created_at" not in d
        assert "updated_at" not in d
        assert d["type"] == "codex"

    def test_to_json_entry_token_type_as_type_key(self):
        r = AccountRecord(service="CHATGPT", email="a@b.com", password="pw", token_type="codex")
        assert serialize_account_record(r)["type"] == "codex"

    def test_credits_included_when_nonzero(self):
        r = AccountRecord(service="ELEVENLABS", email="a@b.com", password="pw", credits=100)
        assert serialize_account_record(r)["credits"] == 100

    def test_credits_omitted_when_zero(self):
        r = AccountRecord(service="ELEVENLABS", email="a@b.com", password="pw", credits=0)
        assert "credits" not in serialize_account_record(r)

    def test_frozen_immutable(self):
        r = AccountRecord(service="ELEVENLABS", email="a@b.com", password="pw")
        with pytest.raises((AttributeError, TypeError)):
            r.email = "other@b.com"  # type: ignore


class TestSerializeAccountRecord:
    """serialize_account_record() — pure serialization."""

    def test_excludes_service_field(self):
        r = AccountRecord(service="ELEVENLABS", email="x@y.com", password="pw")
        d = serialize_account_record(r)
        assert "service" not in d

    def test_includes_all_set_fields(self):
        r = AccountRecord(
            service="CHATGPT",
            email="x@y.com",
            password="pw",
            api_key="sk_123",
            refresh_token="rt",
            access_token="at",
            account_id="acc_1",
            id_token="it",
            expired="2099-01-01",
            last_refresh="2025-01-01",
            token_type="codex",
        )
        d = serialize_account_record(r, include_timestamps=False)
        assert d["api_key"] == "sk_123"
        assert d["refresh_token"] == "rt"
        assert d["access_token"] == "at"
        assert d["account_id"] == "acc_1"
        assert d["id_token"] == "it"
        assert d["expired"] == "2099-01-01"
        assert d["last_refresh"] == "2025-01-01"
        assert d["type"] == "codex"


# ── Codex auth helpers ────────────────────────────────────────────────────────

class TestCodexAuthHelpers:
    def test_should_export_codex_auth_true_for_chatgpt_codex(self):
        r = AccountRecord(service="CHATGPT", email="a@b.com", password="pw", token_type="codex")
        assert should_export_codex_auth(r) is True

    def test_should_export_codex_auth_false_for_non_chatgpt(self):
        r = AccountRecord(service="ELEVENLABS", email="a@b.com", password="pw", token_type="codex")
        assert should_export_codex_auth(r) is False

    def test_should_export_codex_auth_false_for_non_codex_type(self):
        r = AccountRecord(service="CHATGPT", email="a@b.com", password="pw", token_type="")
        assert should_export_codex_auth(r) is False

    def test_build_codex_auth_path(self):
        path = build_codex_auth_path(Path("D:/tmp"), "user@example.com")
        assert path.name == "codex-user@example.com-free.json"
        assert path.parent.name == "auth"

    def test_build_codex_auth_path_sanitizes_filename(self):
        """Email characters passthrough (no sanitization needed for normal email)."""
        path = build_codex_auth_path(Path("/tmp"), "codex@mail.com")
        assert "codex@mail.com" in str(path)

    def test_build_target_codex_auth_path(self):
        path = build_target_codex_auth_path(Path("/sync"), "user@example.com")
        assert path.parent == Path("/sync")
        assert "user@example.com" in path.name

    def test_matching_exporters_chatgpt_codex(self):
        r = AccountRecord(service="CHATGPT", email="a@b.com", password="pw", token_type="codex")
        exporters = matching_exporters(r)
        assert len(exporters) == 1

    def test_matching_exporters_non_codex(self):
        r = AccountRecord(service="ELEVENLABS", email="a@b.com", password="pw")
        assert matching_exporters(r) == []

    def test_is_auth_sync_enabled_true(self):
        cfg = AuthSyncConfig(enabled=True, target_dir=Path("/sync"))
        assert is_auth_sync_enabled(cfg) is True

    def test_is_auth_sync_enabled_false_when_disabled(self):
        cfg = AuthSyncConfig(enabled=False, target_dir=Path("/sync"))
        assert is_auth_sync_enabled(cfg) is False

    def test_is_auth_sync_enabled_false_when_none(self):
        assert is_auth_sync_enabled(None) is False


# ── File I/O helpers ──────────────────────────────────────────────────────────

class TestJsonIO:
    """write_json / read_json — real file I/O in tmpdir."""

    def test_write_and_read_dict(self, tmp_path):
        path = tmp_path / "data.json"
        write_json(path, {"key": "value", "num": 42})
        data = read_json(path, default={})
        assert data["key"] == "value"
        assert data["num"] == 42

    def test_write_and_read_list(self, tmp_path):
        path = tmp_path / "list.json"
        write_json(path, [{"email": "a@b.com"}])
        data = read_json(path, default=[])
        assert data[0]["email"] == "a@b.com"

    def test_write_creates_intermediate_dirs(self, tmp_path):
        nested = tmp_path / "a" / "b" / "c" / "data.json"
        write_json(nested, {"x": 1})
        assert nested.exists()

    def test_write_never_adds_utf8_bom(self, tmp_path):
        path = tmp_path / "no_bom.json"
        write_json(path, {"key": "val"})
        assert not path.read_bytes().startswith(b"\xef\xbb\xbf")

    def test_read_handles_utf8_bom(self, tmp_path):
        path = tmp_path / "bom.json"
        path.write_bytes(b"\xef\xbb\xbf" + b'[{"email":"bom@example.com"}]')
        data = read_json(path, default=[])

    def test_read_returns_default_when_file_missing(self, tmp_path):
        path = tmp_path / "nonexistent.json"
        assert read_json(path, default=[]) == []

    def test_read_returns_default_on_invalid_json(self, tmp_path):
        path = tmp_path / "bad.json"
        path.write_text("{ not valid json", encoding="utf-8")
        assert read_json(path, default=None) is None


# ── Auth sync ─────────────────────────────────────────────────────────────────

class TestAuthSync:
    """sync_codex_auth_payload, sync_auth_file, sync_auth_directory."""

    def test_sync_codex_auth_payload_writes_to_target(self, tmp_path):
        target = tmp_path / "external"
        cfg = AuthSyncConfig(enabled=True, target_dir=target)
        payload = {"email": "u@e.com", "type": "codex", "disabled": False}
        result = sync_codex_auth_payload("u@e.com", payload, cfg)
        assert result is not None
        assert result.exists()
        assert json.loads(result.read_text())["email"] == "u@e.com"

    def test_sync_codex_auth_payload_skips_when_disabled(self, tmp_path):
        cfg = AuthSyncConfig(enabled=False, target_dir=tmp_path)
        result = sync_codex_auth_payload("u@e.com", {"email": "u@e.com"}, cfg)
        assert result is None

    def test_sync_codex_auth_payload_skips_when_none(self):
        result = sync_codex_auth_payload("u@e.com", {"email": "u@e.com"}, None)
        assert result is None

    def test_sync_auth_file_copies_correctly(self, tmp_path):
        src = tmp_path / "auth" / "codex-x-free.json"
        write_json(src, {"email": "x@y.com", "disabled": False})
        target = tmp_path / "sync"
        target.mkdir()
        result = sync_auth_file(src, target)
        assert result is not None
        assert (target / src.name).exists()

    def test_sync_auth_file_returns_none_for_non_dict(self, tmp_path):
        src = tmp_path / "list.json"
        write_json(src, ["not", "a", "dict"])
        target = tmp_path / "sync"
        target.mkdir()
        result = sync_auth_file(src, target)
        assert result is None

    def test_sync_auth_directory_copies_all_json(self, tmp_path):
        base = tmp_path / "repo"
        auth_dir = base / "auth"
        auth_dir.mkdir(parents=True)
        target = tmp_path / "external"
        for i in range(3):
            write_json(auth_dir / f"codex-user{i}@x.com-free.json", {"email": f"user{i}@x.com"})
        synced = sync_auth_directory(base, target)
        assert len(synced) == 3

    def test_sync_auth_directory_returns_empty_when_no_auth_dir(self, tmp_path):
        result = sync_auth_directory(tmp_path / "nonexistent", tmp_path / "target")
        assert result == []

    def test_sync_auth_directory_no_bom_in_output(self, tmp_path):
        base = tmp_path / "repo"
        auth_dir = base / "auth"
        auth_dir.mkdir(parents=True)
        target = tmp_path / "external"
        write_json(auth_dir / "codex-u-free.json", {"email": "u@x.com"})
        synced = sync_auth_directory(base, target)
        assert len(synced) == 1
        assert not synced[0].read_bytes().startswith(b"\xef\xbb\xbf")


# ── Repo + repo_save ──────────────────────────────────────────────────────────

class TestRepoSave:
    """repo_save() với real SQLite — verify DB insert và codex export."""

    def test_save_inserts_to_db(self, tmp_repo, make_account):
        from src.core.database import get_account_by_email
        record = make_account(service="ELEVENLABS", email="el@test.com", api_key="sk_xyz")
        repo_save(tmp_repo, record)
        row = get_account_by_email(tmp_repo.db, "ELEVENLABS", "el@test.com")
        assert row is not None
        assert row["api_key"] == "sk_xyz"

    def test_save_chatgpt_codex_writes_auth_file(self, tmp_path):
        from src.config.settings import AppConfig
        repo = Repo(base_dir=tmp_path)
        init_repo(repo)
        record = AccountRecord(
            service="CHATGPT",
            email="codex-user@example.com",
            password="P@1",
            refresh_token="rt_123",
            access_token="at_123",
            account_id="acc_123",
            token_type="codex",
        )
        repo_save(repo, record)
        auth_path = tmp_path / "auth" / "codex-codex-user@example.com-free.json"
        assert auth_path.exists()
        payload = json.loads(auth_path.read_text(encoding="utf-8"))
        assert payload["email"] == "codex-user@example.com"
        assert payload["type"] == "codex"
        assert "created_at" not in payload

    def test_save_chatgpt_codex_syncs_to_target(self, tmp_path):
        target = tmp_path / "external"
        auth_sync = AuthSyncConfig(enabled=True, target_dir=target)
        repo = Repo(base_dir=tmp_path, auth_sync=auth_sync)
        init_repo(repo)
        record = AccountRecord(
            service="CHATGPT",
            email="codex-user@example.com",
            password="P@1",
            refresh_token="rt_sync",
            access_token="at_sync",
            token_type="codex",
        )
        repo_save(repo, record)
        synced_path = target / "codex-codex-user@example.com-free.json"
        assert synced_path.exists()
        payload = json.loads(synced_path.read_text())
        assert payload["email"] == "codex-user@example.com"
        assert not synced_path.read_bytes().startswith(b"\xef\xbb\xbf")

    def test_save_non_chatgpt_no_auth_file(self, tmp_path):
        repo = Repo(base_dir=tmp_path)
        init_repo(repo)
        record = AccountRecord(service="ELEVENLABS", email="el@test.com", password="pw")
        repo_save(repo, record)
        auth_dir = tmp_path / "auth"
        assert not auth_dir.exists() or len(list(auth_dir.glob("*.json"))) == 0


# ── OpenRouter exporter ───────────────────────────────────────────────────────


def _make_mock_http_client(get_data: list, put_capture: list | None = None):
    """Factory: trả mock httpx.Client context manager với GET/PUT canned responses."""
    from unittest.mock import MagicMock

    mock_get_resp = MagicMock()
    mock_get_resp.json.return_value = get_data
    mock_get_resp.raise_for_status.return_value = None

    mock_put_resp = MagicMock()
    mock_put_resp.raise_for_status.return_value = None

    mock_client = MagicMock()
    mock_client.get.return_value = mock_get_resp

    def _put(url, **kwargs):
        if put_capture is not None:
            put_capture.append(kwargs.get("json"))
        return mock_put_resp

    mock_client.put.side_effect = _put
    mock_client.__enter__ = lambda s: s
    mock_client.__exit__ = MagicMock(return_value=False)
    return mock_client


class TestOpenRouterExporter:
    """export_openrouter_key() — sync single key qua CLIProxyAPI Management REST API."""

    def test_should_export_true_for_openrouter_with_key(self):
        r = AccountRecord(service="OPENROUTER", email="a@b.com", password="pw", api_key="sk-or-xxx")
        assert should_export_openrouter_key(r) is True

    def test_should_export_false_for_non_openrouter(self):
        r = AccountRecord(service="ELEVENLABS", email="a@b.com", password="pw", api_key="sk_xxx")
        assert should_export_openrouter_key(r) is False

    def test_should_export_false_without_api_key(self):
        r = AccountRecord(service="OPENROUTER", email="a@b.com", password="pw")
        assert should_export_openrouter_key(r) is False

    def test_should_export_false_when_disabled(self):
        r = AccountRecord(service="OPENROUTER", email="a@b.com", password="pw", api_key="sk-or-xxx", disabled=True)
        assert should_export_openrouter_key(r) is False

    def test_matching_exporters_includes_openrouter(self):
        r = AccountRecord(service="OPENROUTER", email="a@b.com", password="pw", api_key="sk-or-xxx")
        exporters = matching_exporters(r)
        assert len(exporters) == 1
        assert exporters[0] is export_openrouter_key

    def test_export_adds_key_to_existing_list(self, tmp_path):
        from unittest.mock import patch
        initial = [{"name": "openrouter", "base-url": "https://openrouter.ai/api/v1", "api-key-entries": [{"api-key": "sk-exist"}], "models": []}]
        captured: list = []
        mock_client = _make_mock_http_client(initial, captured)

        cliproxy_sync = ClipRoxySyncConfig(management_url="http://localhost:8317")
        repo = Repo(base_dir=tmp_path, cliproxy_sync=cliproxy_sync)
        record = AccountRecord(service="OPENROUTER", email="a@b.com", password="pw", api_key="sk-or-new")

        with patch("httpx.Client", return_value=mock_client):
            export_openrouter_key(repo, record)

        assert len(captured) == 1
        keys = [e["api-key"] for e in captured[0][0]["api-key-entries"]]
        assert "sk-exist" in keys
        assert "sk-or-new" in keys

    def test_export_skips_duplicate_key(self, tmp_path):
        from unittest.mock import patch
        initial = [{"name": "openrouter", "base-url": "https://openrouter.ai/api/v1", "api-key-entries": [{"api-key": "sk-exist"}], "models": []}]
        captured: list = []
        mock_client = _make_mock_http_client(initial, captured)

        cliproxy_sync = ClipRoxySyncConfig(management_url="http://localhost:8317")
        repo = Repo(base_dir=tmp_path, cliproxy_sync=cliproxy_sync)
        record = AccountRecord(service="OPENROUTER", email="a@b.com", password="pw", api_key="sk-exist")

        with patch("httpx.Client", return_value=mock_client):
            export_openrouter_key(repo, record)

        # PUT không được gọi vì key đã tồn tại
        assert len(captured) == 0

    def test_export_creates_entry_if_missing(self, tmp_path):
        from unittest.mock import patch
        initial: list = []  # empty compat list
        captured: list = []
        mock_client = _make_mock_http_client(initial, captured)

        cliproxy_sync = ClipRoxySyncConfig(management_url="http://localhost:8317")
        repo = Repo(base_dir=tmp_path, cliproxy_sync=cliproxy_sync)
        record = AccountRecord(service="OPENROUTER", email="a@b.com", password="pw", api_key="sk-or-fresh")

        with patch("httpx.Client", return_value=mock_client):
            export_openrouter_key(repo, record)

        assert len(captured) == 1
        or_entry = captured[0][0]
        assert or_entry["base-url"] == "https://openrouter.ai/api/v1"
        assert or_entry["api-key-entries"][0]["api-key"] == "sk-or-fresh"

    def test_export_noop_when_no_cliproxy_sync(self, tmp_path):
        from unittest.mock import patch
        repo = Repo(base_dir=tmp_path)
        record = AccountRecord(service="OPENROUTER", email="a@b.com", password="pw", api_key="sk-or-xxx")
        with patch("httpx.Client") as mock_cls:
            export_openrouter_key(repo, record)
            mock_cls.assert_not_called()

    def test_repo_save_auto_syncs_openrouter(self, tmp_path):
        from unittest.mock import patch
        initial = [{"name": "openrouter", "base-url": "https://openrouter.ai/api/v1", "api-key-entries": [], "models": []}]
        captured: list = []
        mock_client = _make_mock_http_client(initial, captured)

        cliproxy_sync = ClipRoxySyncConfig(management_url="http://localhost:8317")
        repo = Repo(base_dir=tmp_path, cliproxy_sync=cliproxy_sync)
        init_repo(repo)

        record = AccountRecord(service="OPENROUTER", email="or@test.com", password="pw", api_key="sk-or-auto")
        with patch("httpx.Client", return_value=mock_client):
            repo_save(repo, record)

        assert len(captured) == 1
        keys = [e["api-key"] for e in captured[0][0]["api-key-entries"]]
        assert "sk-or-auto" in keys
