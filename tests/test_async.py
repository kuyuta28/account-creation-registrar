"""
test_async.py — Unit tests cho async conversion.
Covers: config_service, account_service, capsolver, checkers, API routes.
No network, no I/O — all external calls mocked.
"""
from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, _ROOT)


# ─────────────────────────────────────────────────────────────────────────────
# capsolver._run_sync — safe coroutine execution
# ─────────────────────────────────────────────────────────────────────────────

class TestRunSync(unittest.TestCase):
    """_run_sync must work both inside and outside an event loop."""

    def test_outside_event_loop(self):
        from src.captcha.capsolver import _run_sync

        async def _coro():
            return 42

        self.assertEqual(_run_sync(_coro()), 42)

    def test_inside_event_loop(self):
        """Gọi _run_sync từ TRONG event loop → chạy qua thread, không deadlock."""
        from src.captcha.capsolver import _run_sync

        async def _coro():
            return "hello"

        async def _main():
            return _run_sync(_coro())

        result = asyncio.run(_main())
        self.assertEqual(result, "hello")

    def test_exception_propagation(self):
        from src.captcha.capsolver import _run_sync

        async def _fail():
            raise ValueError("boom")

        with self.assertRaises(ValueError):
            _run_sync(_fail())


class TestDetectProvider(unittest.TestCase):
    def test_ezcaptcha_priority(self):
        from src.captcha.capsolver import _detect_provider
        name, key = _detect_provider("ez_key", "cap_key", "two_key")
        self.assertEqual(name, "ezcaptcha")
        self.assertEqual(key, "ez_key")

    def test_twocaptcha_fallback(self):
        from src.captcha.capsolver import _detect_provider
        name, key = _detect_provider("", "cap_key", "two_key")
        self.assertEqual(name, "2captcha")
        self.assertEqual(key, "two_key")

    def test_capsolver_last(self):
        from src.captcha.capsolver import _detect_provider
        name, key = _detect_provider("", "cap_key", "")
        self.assertEqual(name, "capsolver")

    def test_no_key_raises(self):
        from src.captcha.capsolver import _detect_provider
        with self.assertRaises(RuntimeError):
            _detect_provider("", "", "")


# ─────────────────────────────────────────────────────────────────────────────
# checkers — pure functions + async mocked
# ─────────────────────────────────────────────────────────────────────────────

class TestParseTokenResponse(unittest.TestCase):
    """_parse_token_response is pure — no I/O."""

    def test_basic_parse(self):
        import base64
        import json
        from src.checkers.chatgpt import _parse_token_response

        # Tạo fake JWT
        header = base64.urlsafe_b64encode(json.dumps({"alg": "RS256"}).encode()).decode().rstrip("=")
        payload_dict = {
            "https://api.openai.com/auth": {"chatgpt_account_id": "acc_123"},
            "exp": 9999999999,
        }
        payload = base64.urlsafe_b64encode(json.dumps(payload_dict).encode()).decode().rstrip("=")
        fake_at = f"{header}.{payload}.signature"

        token_data = {
            "access_token": fake_at,
            "refresh_token": "rt_new",
            "id_token": "id_tok",
            "expires_in": 3600,
        }
        result = _parse_token_response(token_data, "rt_old")
        self.assertEqual(result["access_token"], fake_at)
        self.assertEqual(result["refresh_token"], "rt_new")
        self.assertEqual(result["account_id"], "acc_123")
        self.assertIn("expired", result)
        self.assertIn("last_refresh", result)


class TestParseUserResponse(unittest.TestCase):
    """_parse_user_response is pure — no I/O."""

    def test_valid_response(self):
        from src.checkers.elevenlabs import _parse_user_response

        data = {
            "subscription": {
                "tier": "free",
                "status": "active",
                "character_count": 200,
                "character_limit": 10000,
                "next_character_count_reset_unix": 1700000000,
            },
        }
        result = _parse_user_response(data)
        self.assertTrue(result["valid"])
        self.assertEqual(result["tier"], "free")
        self.assertEqual(result["characters_used"], 200)
        self.assertEqual(result["characters_remaining"], 9800)


class TestIsExpired(unittest.TestCase):
    def test_empty_string(self):
        from src.checkers.chatgpt import is_expired
        self.assertTrue(is_expired(""))

    def test_future_date(self):
        from src.checkers.chatgpt import is_expired
        self.assertFalse(is_expired("2099-01-01T00:00:00+00:00"))

    def test_past_date(self):
        from src.checkers.chatgpt import is_expired
        self.assertTrue(is_expired("2020-01-01T00:00:00+00:00"))


class TestCheckKeyAsyncMocked(unittest.IsolatedAsyncioTestCase):
    """check_key (async) with mocked httpx."""

    async def test_empty_key(self):
        from src.checkers.elevenlabs import check_key
        result = await check_key("")
        self.assertFalse(result["valid"])
        self.assertEqual(result["reason"], "empty key")

    @patch("src.checkers.elevenlabs.httpx.AsyncClient")
    async def test_valid_key(self, mock_client_cls):
        from src.checkers.elevenlabs import check_key

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "subscription": {
                "tier": "starter",
                "status": "active",
                "character_count": 100,
                "character_limit": 5000,
                "next_character_count_reset_unix": 1700000000,
            },
        }
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        result = await check_key("sk_test")
        self.assertTrue(result["valid"])
        self.assertEqual(result["tier"], "starter")

    @patch("src.checkers.elevenlabs.httpx.AsyncClient")
    async def test_invalid_key_401(self, mock_client_cls):
        from src.checkers.elevenlabs import check_key

        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        result = await check_key("sk_bad")
        self.assertFalse(result["valid"])
        self.assertIn("401", result["reason"])


class TestCheckAccountAsyncMocked(unittest.IsolatedAsyncioTestCase):
    """check_account (async) with mocked httpx."""

    async def test_no_refresh_token(self):
        from src.checkers.chatgpt import check_account
        acc = {"refresh_token": "", "access_token": "", "expired": ""}
        result = await check_account(acc, "client_id")
        self.assertFalse(result["valid"])
        self.assertIn("no refresh_token", result["reason"])

    @patch("src.checkers.chatgpt.refresh_token", new_callable=AsyncMock)
    async def test_refresh_fails(self, mock_refresh):
        from src.checkers.chatgpt import check_account
        mock_refresh.return_value = None
        acc = {"refresh_token": "rt", "access_token": "", "expired": ""}
        result = await check_account(acc, "cid")
        self.assertFalse(result["valid"])
        self.assertIn("refresh failed", result["reason"])


# ─────────────────────────────────────────────────────────────────────────────
# config_service — async file I/O via to_thread
# ─────────────────────────────────────────────────────────────────────────────

class TestConfigServiceAsync(unittest.IsolatedAsyncioTestCase):

    async def test_list_config_files(self):
        from src.api.services import config_service as svc
        with patch.object(svc, "_CONFIG_DIR", Path(tempfile.mkdtemp())) as tmp:
            (tmp / "a.yaml").write_text("a: 1")
            (tmp / "b.yaml").write_text("b: 2")
            (tmp / "c.txt").write_text("not yaml")
            result = await svc.list_config_files()
            self.assertEqual(result, ["a.yaml", "b.yaml"])

    async def test_read_write_config_raw(self):
        from src.api.services import config_service as svc
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "test.yaml").write_text("key: value\n", encoding="utf-8")
            with patch.object(svc, "_CONFIG_DIR", tmp_path):
                content = await svc.read_config_raw("test.yaml")
                self.assertIn("key: value", content)

                await svc.write_config_raw("new_key: 123\n", "test.yaml")
                updated = await svc.read_config_raw("test.yaml")
                self.assertIn("new_key: 123", updated)

    async def test_write_invalid_yaml_raises(self):
        from src.api.services import config_service as svc
        import yaml
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(svc, "_CONFIG_DIR", Path(tmp)):
                # Tạo file trước
                (Path(tmp) / "bad.yaml").write_text("ok: 1")
                # YAML invalid (tab character in value context fails)
                with self.assertRaises(Exception):
                    await svc.write_config_raw("a: {\n  b: ]\n}", "bad.yaml")

    async def test_read_config_dict(self):
        from src.api.services import config_service as svc
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "cfg.yaml").write_text("x: 10\ny: 20\n", encoding="utf-8")
            with patch.object(svc, "_CONFIG_DIR", Path(tmp)):
                d = await svc.read_config_dict("cfg.yaml")
                self.assertEqual(d, {"x": 10, "y": 20})

    async def test_add_mailslurp_key(self):
        from src.api.services import config_service as svc
        import yaml
        with tempfile.TemporaryDirectory() as tmp:
            mail_path = Path(tmp) / "mail.yaml"
            mail_path.write_text(
                yaml.dump({"mail": {"mailslurp_api_keys": ["key1"]}}, sort_keys=False),
                encoding="utf-8",
            )
            with patch.object(svc, "_CONFIG_DIR", Path(tmp)):
                total = await svc.add_mailslurp_key("key2")
                self.assertEqual(total, 2)

                # Duplicate → same count
                total = await svc.add_mailslurp_key("key2")
                self.assertEqual(total, 2)


# ─────────────────────────────────────────────────────────────────────────────
# account_service — async CRUD + batch
# ─────────────────────────────────────────────────────────────────────────────

class TestAccountServiceAsync(unittest.IsolatedAsyncioTestCase):

    async def test_list_accounts_calls_to_thread(self):
        """list_accounts wraps sync DB call in asyncio.to_thread."""
        import src.api.services.account_service as svc
        with patch.object(svc, "get_accounts", return_value=[]) as mock_get:
            result = await svc.list_accounts("CHATGPT")
            mock_get.assert_called_once_with(svc._DB_PATH, "CHATGPT")
            self.assertEqual(result, [])

    async def test_get_account_found(self):
        import src.api.services.account_service as svc
        fake = {"email": "a@b.com", "service": "CHATGPT"}
        with patch.object(svc, "get_account_by_email", return_value=fake):
            result = await svc.get_account("CHATGPT", "a@b.com")
            self.assertEqual(result["email"], "a@b.com")

    async def test_get_account_not_found(self):
        import src.api.services.account_service as svc
        with patch.object(svc, "get_account_by_email", return_value=None):
            result = await svc.get_account("CHATGPT", "x@y.com")
            self.assertIsNone(result)

    async def test_update_account_fields(self):
        import src.api.services.account_service as svc
        with patch.object(svc, "update_account", return_value=True) as mock_upd:
            ok = await svc.update_account_fields("CHATGPT", "a@b.com", disabled=True)
            self.assertTrue(ok)
            mock_upd.assert_called_once_with(svc._DB_PATH, "CHATGPT", "a@b.com", disabled=True)

    async def test_remove_account(self):
        import src.api.services.account_service as svc
        with patch.object(svc, "delete_account", return_value=True):
            ok = await svc.remove_account("CHATGPT", "a@b.com")
            self.assertTrue(ok)

    async def test_check_and_persist_not_found(self):
        import src.api.services.checker_service as svc
        with patch.object(svc, "get_account_by_email", return_value=None):
            result = await svc.check_and_persist("CHATGPT", "no@one.com")
            self.assertEqual(result["error"], "not found")

    async def test_check_and_persist_unsupported_service(self):
        import src.api.services.checker_service as svc
        with patch.object(svc, "get_account_by_email", return_value={"email": "a@b.com"}):
            with self.assertRaises(ValueError):
                await svc.check_and_persist("UNKNOWN", "a@b.com")

    async def test_get_batch_status_default(self):
        import src.api.services.checker_service as svc
        status = await svc.get_batch_status()
        self.assertIn("running", status)
        self.assertIn("total", status)

    async def test_start_batch_check_no_accounts(self):
        import src.api.services.checker_service as svc
        with patch.object(svc, "get_accounts", return_value=[]):
            # Reset batch state
            async with svc._batch_lock:
                svc._batch["running"] = False
            result = await svc.start_batch_check()
            self.assertEqual(result["error"], "no accounts to check")


# ─────────────────────────────────────────────────────────────────────────────
# API routes — TestClient (handles async routes transparently)
# ─────────────────────────────────────────────────────────────────────────────

# Patch target = nơi import (router module), KHÔNG phải nơi define (service module)
_ACC_R = "src.api.routers.accounts"


class TestAccountsRouter(unittest.TestCase):
    """Accounts routes → async def → TestClient handles them."""

    def _client(self):
        from fastapi.testclient import TestClient
        from src.api.server import app
        return TestClient(app, raise_server_exceptions=False)

    @patch(f"{_ACC_R}.list_accounts", new_callable=AsyncMock)
    def test_get_accounts_empty(self, mock_list):
        mock_list.return_value = []
        c = self._client()
        r = c.get("/api/v1/accounts")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["data"], [])

    @patch(f"{_ACC_R}.list_accounts", new_callable=AsyncMock)
    def test_get_accounts_with_service_filter(self, mock_list):
        mock_list.return_value = [{"email": "x@y.com", "service": "CHATGPT"}]
        c = self._client()
        r = c.get("/api/v1/accounts?service=CHATGPT")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()["data"]), 1)
        mock_list.assert_called_with("CHATGPT")

    @patch(f"{_ACC_R}.get_account", new_callable=AsyncMock)
    def test_get_one_not_found(self, mock_get):
        mock_get.return_value = None
        c = self._client()
        r = c.get("/api/v1/accounts/CHATGPT/no@one.com")
        self.assertEqual(r.status_code, 404)

    @patch(f"{_ACC_R}.get_account", new_callable=AsyncMock)
    def test_get_one_found(self, mock_get):
        mock_get.return_value = {"email": "a@b.com", "service": "CHATGPT"}
        c = self._client()
        r = c.get("/api/v1/accounts/CHATGPT/a@b.com")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["data"]["email"], "a@b.com")

    @patch(f"{_ACC_R}.update_account_fields", new_callable=AsyncMock)
    def test_patch_account_ok(self, mock_update):
        mock_update.return_value = True
        c = self._client()
        r = c.patch("/api/v1/accounts/CHATGPT/a@b.com", json={"disabled": True})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["data"]["updated"])

    @patch(f"{_ACC_R}.update_account_fields", new_callable=AsyncMock)
    def test_patch_account_not_found(self, mock_update):
        mock_update.return_value = False
        c = self._client()
        r = c.patch("/api/v1/accounts/CHATGPT/a@b.com", json={"disabled": True})
        self.assertEqual(r.status_code, 404)

    def test_patch_account_no_fields(self):
        c = self._client()
        r = c.patch("/api/v1/accounts/CHATGPT/a@b.com", json={})
        self.assertEqual(r.status_code, 400)

    @patch(f"{_ACC_R}.remove_account", new_callable=AsyncMock)
    def test_delete_account_ok(self, mock_del):
        mock_del.return_value = True
        c = self._client()
        r = c.delete("/api/v1/accounts/CHATGPT/a@b.com")
        self.assertEqual(r.status_code, 200)

    @patch(f"{_ACC_R}.remove_account", new_callable=AsyncMock)
    def test_delete_account_not_found(self, mock_del):
        mock_del.return_value = False
        c = self._client()
        r = c.delete("/api/v1/accounts/CHATGPT/a@b.com")
        self.assertEqual(r.status_code, 404)

    @patch(f"{_ACC_R}.check_and_persist", new_callable=AsyncMock)
    def test_check_one_valid(self, mock_check):
        mock_check.return_value = {"valid": True, "check_status": "valid"}
        c = self._client()
        r = c.post("/api/v1/accounts/check?service=CHATGPT&email=a@b.com")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["data"]["valid"])

    @patch(f"{_ACC_R}.check_and_persist", new_callable=AsyncMock)
    def test_check_one_not_found(self, mock_check):
        mock_check.return_value = {"error": "not found"}
        c = self._client()
        r = c.post("/api/v1/accounts/check?service=CHATGPT&email=x@y.com")
        self.assertEqual(r.status_code, 404)

    @patch(f"{_ACC_R}.get_batch_status", new_callable=AsyncMock)
    def test_check_all_status(self, mock_status):
        mock_status.return_value = {"running": False, "total": 0, "checked": 0}
        c = self._client()
        r = c.get("/api/v1/accounts/check-all/status")
        self.assertEqual(r.status_code, 200)
        self.assertIn("running", r.json()["data"])

    @patch(f"{_ACC_R}.start_batch_check", new_callable=AsyncMock)
    def test_check_all_already_running(self, mock_start):
        mock_start.return_value = {"error": "already running"}
        c = self._client()
        r = c.post("/api/v1/accounts/check-all")
        self.assertEqual(r.status_code, 409)


_CFG_R = "src.api.routers.config"


class TestConfigRouter(unittest.TestCase):
    """Config routes → async def → TestClient."""

    def _client(self):
        from fastapi.testclient import TestClient
        from src.api.server import app
        return TestClient(app, raise_server_exceptions=False)

    @patch(f"{_CFG_R}.list_config_files", new_callable=AsyncMock)
    def test_get_config_files(self, mock_list):
        mock_list.return_value = ["config.yaml", "mail.yaml"]
        c = self._client()
        r = c.get("/api/v1/config/files")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["data"]["files"], ["config.yaml", "mail.yaml"])

    @patch(f"{_CFG_R}.read_config_raw", new_callable=AsyncMock)
    def test_get_config_raw(self, mock_read):
        mock_read.return_value = "key: value\n"
        c = self._client()
        r = c.get("/api/v1/config/raw?file=config.yaml")
        self.assertEqual(r.status_code, 200)
        self.assertIn("key: value", r.json()["data"]["content"])

    @patch(f"{_CFG_R}.read_config_raw", new_callable=AsyncMock)
    def test_get_config_raw_not_found(self, mock_read):
        mock_read.side_effect = FileNotFoundError("nope")
        c = self._client()
        r = c.get("/api/v1/config/raw?file=nope.yaml")
        self.assertEqual(r.status_code, 404)

    @patch(f"{_CFG_R}.write_config_raw", new_callable=AsyncMock)
    def test_put_config_raw(self, mock_write):
        mock_write.return_value = None
        c = self._client()
        r = c.put("/api/v1/config/raw?file=config.yaml", json={"content": "a: 1\n"})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["data"]["saved"])

    @patch(f"{_CFG_R}.write_config_raw", new_callable=AsyncMock)
    def test_put_config_raw_invalid_yaml(self, mock_write):
        mock_write.side_effect = Exception("invalid yaml")
        c = self._client()
        r = c.put("/api/v1/config/raw?file=config.yaml", json={"content": "bad"})
        self.assertEqual(r.status_code, 400)

    @patch(f"{_CFG_R}.read_config_dict", new_callable=AsyncMock)
    def test_get_config(self, mock_read):
        mock_read.return_value = {"llm": {"model": "gpt-4"}}
        c = self._client()
        r = c.get("/api/v1/config")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["data"]["llm"]["model"], "gpt-4")

    @patch(f"{_CFG_R}.add_mailslurp_key", new_callable=AsyncMock)
    def test_add_mailslurp_key(self, mock_add):
        mock_add.return_value = 3
        c = self._client()
        r = c.post("/api/v1/config/mail/add-key", json={"key": "new_key"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["data"]["total"], 3)

    def test_add_mailslurp_key_empty(self):
        c = self._client()
        r = c.post("/api/v1/config/mail/add-key", json={"key": ""})
        self.assertEqual(r.status_code, 400)


class TestRegistrationRouter(unittest.TestCase):
    """Registration routes → async def → TestClient."""

    def _client(self):
        from fastapi.testclient import TestClient
        from src.api.server import app
        return TestClient(app, raise_server_exceptions=False)

    def test_get_services(self):
        c = self._client()
        r = c.get("/api/v1/registration/services")
        self.assertEqual(r.status_code, 200)
        self.assertIsInstance(r.json(), (dict, list))

    @patch("src.api.routers.registration.list_jobs", return_value=[])
    def test_get_jobs_empty(self, _mock):
        c = self._client()
        r = c.get("/api/v1/registration/jobs")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["data"], [])


# ─────────────────────────────────────────────────────────────────────────────
# capsolver async API — mocked httpx
# ─────────────────────────────────────────────────────────────────────────────

class TestCapsolverAsync(unittest.IsolatedAsyncioTestCase):

    @patch("src.captcha.capsolver.httpx.AsyncClient")
    async def test_get_balance_async(self, mock_client_cls):
        from src.captcha.capsolver import get_balance_async

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"errorId": 0, "balance": 42.5}
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        balance = await get_balance_async("test_key", "ezcaptcha")
        self.assertEqual(balance, 42.5)

    @patch("src.captcha.capsolver.httpx.AsyncClient")
    async def test_get_balance_async_error(self, mock_client_cls):
        from src.captcha.capsolver import get_balance_async

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"errorId": 1, "errorDescription": "invalid key"}
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        with self.assertRaises(RuntimeError):
            await get_balance_async("bad_key", "ezcaptcha")


if __name__ == "__main__":
    unittest.main()
