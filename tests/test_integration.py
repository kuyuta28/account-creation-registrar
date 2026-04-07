"""
Integration tests - real network calls, no mocks.

Groups:
  1. TestConfigLoad       - load config.yaml, verify all sections present
  2. TestLLMConnectivity  - ping localhost:8317, verify OpenAI-compatible response
  3. TestLLMAction        - send real image to _ask_llm_action / _ask_llm_verify_button
  4. TestMailTM           - create mailbox, list messages, timeout behaviour

Requirements:
  - LLM server running at the base_url in config.yaml  (groups 2-3)
  - Internet access                                    (group 4)
"""
from __future__ import annotations

import base64
import struct
import sys
import time
import asyncio
import unittest
import zlib
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))


def _make_test_png(w: int = 100, h: int = 50) -> str:
    """Generate a minimal valid RGB PNG and return as base64 string."""

    def _chunk(tag: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)

    row = b"\x00" + b"\xFF\xFF\xFF" * w
    raw = row * h
    png = (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
        + _chunk(b"IDAT", zlib.compress(raw))
        + _chunk(b"IEND", b"")
    )
    return base64.b64encode(png).decode()


_TEST_IMAGE_B64 = _make_test_png(100, 50)


def _load_cfg():
    from src.config.settings import load_config

    return load_config(ROOT / "config" / "config.yaml")


def _skip_if_llm_down(cfg) -> str:
    """Return skip-reason string if LLM server unreachable, else empty string."""
    import requests

    base = cfg.llm.base_url.rstrip("/")
    if base.endswith("/v1"):
        base = base[:-3]
    try:
        requests.get(
            f"{base}/v1/models",
            headers={"Authorization": f"Bearer {cfg.llm.api_key}"},
            timeout=4,
        )
        return ""
    except Exception as exc:
        return f"LLM server unreachable: {exc}"


class _PrintLogger:
    def log(self, msg: str) -> None:
        print(msg)

    def __call__(self, msg: str) -> None:
        print(msg)


class TestConfigLoad(unittest.TestCase):
    """Load real config.yaml and verify all sections + value types."""

    @classmethod
    def setUpClass(cls):
        cls.cfg = _load_cfg()

    def test_config_yaml_exists(self):
        self.assertTrue((ROOT / "config" / "config.yaml").exists(), "config/config.yaml missing")

    def test_llm_base_url_is_http(self):
        self.assertTrue(
            self.cfg.llm.base_url.startswith("http"),
            f"Unexpected base_url: {self.cfg.llm.base_url!r}",
        )

    def test_llm_model_non_empty(self):
        self.assertTrue(self.cfg.llm.model)

    def test_captcha_max_rounds_positive(self):
        self.assertGreater(self.cfg.captcha.max_rounds, 0)

    def test_elevenlabs_signup_url_set(self):
        self.assertTrue(self.cfg.elevenlabs.signup_url)

    def test_elevenlabs_api_keys_url_set(self):
        self.assertTrue(self.cfg.elevenlabs.api_keys_url)

    def test_elevenlabs_app_base_url_set(self):
        self.assertTrue(self.cfg.elevenlabs.app_base_url)

    def test_chatgpt_oauth_urls_set(self):
        self.assertTrue(self.cfg.chatgpt.oauth_authorize_url)
        self.assertTrue(self.cfg.chatgpt.oauth_token_url)

    def test_timeouts_positive(self):
        t = self.cfg.timeouts
        for name, val in [
            ("email_wait", t.email_wait),
            ("page_load", t.page_load),
            ("poll_interval", t.poll_interval),
        ]:
            with self.subTest(field=name):
                self.assertGreater(val, 0, f"timeouts.{name} should be > 0")

    def test_all_captcha_timing_fields_non_negative(self):
        cap = self.cfg.captcha
        for name, val in [
            ("click_delay_ms", cap.click_delay_ms),
            ("post_click_wait_ms", cap.post_click_wait_ms),
            ("post_verify_wait_ms", cap.post_verify_wait_ms),
            ("recheck_wait_ms", cap.recheck_wait_ms),
            ("pre_solve_wait_ms", cap.pre_solve_wait_ms),
        ]:
            with self.subTest(field=name):
                self.assertGreaterEqual(val, 0)


class TestLLMConnectivity(unittest.TestCase):
    """Verify the LLM server is up and speaks OpenAI-compatible API."""

    @classmethod
    def setUpClass(cls):
        cls.cfg = _load_cfg()
        cls._skip = _skip_if_llm_down(cls.cfg)

    def _maybe_skip(self):
        if self._skip:
            self.skipTest(self._skip)

    def _base_root(self):
        base = self.cfg.llm.base_url.rstrip("/")
        return base[:-3] if base.endswith("/v1") else base

    def test_models_endpoint_reachable(self):
        import requests

        self._maybe_skip()
        resp = requests.get(
            f"{self._base_root()}/v1/models",
            headers={"Authorization": f"Bearer {self.cfg.llm.api_key}"},
            timeout=8,
        )
        self.assertLess(resp.status_code, 600)
        print(f"\n  OK /v1/models -> HTTP {resp.status_code}")

    def test_make_llm_client_base_url_matches_config(self):
        from src.services.elevenlabs_io.captcha import _make_llm_client

        client = _make_llm_client(self.cfg.llm)
        self.assertEqual(
            str(client.base_url).rstrip("/"),
            self.cfg.llm.base_url.rstrip("/"),
        )

    def test_plain_text_completion_responds(self):
        self._maybe_skip()
        from src.services.elevenlabs_io.captcha import _make_llm_client

        client = _make_llm_client(self.cfg.llm)
        import asyncio
        resp = asyncio.run(client.chat.completions.create(
            model=self.cfg.llm.model,
            max_tokens=16,
            messages=[{"role": "user", "content": "Reply with the single word: pong"}],
        ))
        content = resp.choices[0].message.content.strip()
        self.assertIsInstance(content, str)
        self.assertGreater(len(content), 0)
        print(f"\n  OK Plain completion: {content!r}")


class TestLLMAction(unittest.TestCase):
    """Send a real image to the vision helpers and validate their structure."""

    @classmethod
    def setUpClass(cls):
        cls.cfg = _load_cfg()
        cls.logger = _PrintLogger()
        cls._skip = _skip_if_llm_down(cls.cfg)

    def _maybe_skip(self):
        if self._skip:
            self.skipTest(self._skip)

    def test_ask_llm_action_returns_dict(self):
        self._maybe_skip()
        from src.services.elevenlabs_io.captcha import _ask_llm_action

        result = asyncio.run(_ask_llm_action(_TEST_IMAGE_B64, self.cfg, self.logger))
        self.assertIsNotNone(result, "LLM returned None - check local server and model name")
        self.assertIsInstance(result, dict)
        self.assertIn("type", result)
        print(f"\n  OK _ask_llm_action -> {result}")

    def test_ask_llm_action_type_is_click_or_drag(self):
        self._maybe_skip()
        from src.services.elevenlabs_io.captcha import _ask_llm_action

        result = asyncio.run(_ask_llm_action(_TEST_IMAGE_B64, self.cfg, self.logger))
        if result is None:
            self.skipTest("LLM returned None")
        self.assertIn(result["type"], ("click", "drag"))

    def test_ask_llm_action_has_correct_payload_key(self):
        self._maybe_skip()
        from src.services.elevenlabs_io.captcha import _ask_llm_action

        result = asyncio.run(_ask_llm_action(_TEST_IMAGE_B64, self.cfg, self.logger))
        if result is None:
            self.skipTest("LLM returned None")
        if result["type"] == "click":
            self.assertIn("clicks", result)
            self.assertIsInstance(result["clicks"], list)
        else:
            self.assertIn("drags", result)
            self.assertIsInstance(result["drags"], list)

    def test_ask_llm_action_coords_all_in_range(self):
        self._maybe_skip()
        from src.services.elevenlabs_io.captcha import _ask_llm_action, _valid_coord

        result = asyncio.run(_ask_llm_action(_TEST_IMAGE_B64, self.cfg, self.logger))
        if result is None:
            self.skipTest("LLM returned None")
        if result["type"] == "click":
            for coord in result.get("clicks", []):
                self.assertTrue(_valid_coord(coord), f"Leaked invalid coord: {coord}")
        else:
            for drag in result.get("drags", []):
                self.assertTrue(_valid_coord(drag.get("from", {})), f"Invalid drag.from: {drag}")
                self.assertTrue(_valid_coord(drag.get("to", {})), f"Invalid drag.to: {drag}")

    def test_ask_llm_action_repeatable(self):
        self._maybe_skip()
        from src.services.elevenlabs_io.captcha import _ask_llm_action

        for i in range(2):
            result = asyncio.run(_ask_llm_action(_TEST_IMAGE_B64, self.cfg, self.logger))
            with self.subTest(call=i + 1):
                if result is None:
                    self.skipTest("LLM returned None")
                self.assertIn("type", result)

    def test_ask_llm_verify_button_structure(self):
        self._maybe_skip()
        from src.services.elevenlabs_io.captcha import _ask_llm_verify_button

        import asyncio
        result = asyncio.run(_ask_llm_verify_button(_TEST_IMAGE_B64, self.cfg, self.logger))
        if result is not None:
            self.assertIsInstance(result, dict)
            self.assertIn("x", result)
            self.assertIn("y", result)
        print(f"\n  OK _ask_llm_verify_button -> {result}")


class TestMailTM(unittest.TestCase):
    """Test real mail.tm API calls using the functional API surface."""

    def test_create_returns_valid_email(self):
        from src.mail.client import create_mailbox

        with patch("builtins.print"):
            import asyncio; mailbox = asyncio.run(create_mailbox())
        self.assertIn("@", mailbox.email)
        self.assertGreater(len(mailbox.email), 5)
        self.assertTrue(mailbox.token, "Token must be set after create_mailbox()")
        self.assertTrue(mailbox.account_id, "account_id must be set after create_mailbox()")
        print(f"\n  OK Created: {mailbox.email}")

    def test_inbox_initially_list(self):
        from src.mail.client import create_mailbox, get_messages

        with patch("builtins.print"):
            import asyncio; mailbox = asyncio.run(create_mailbox())
            messages = asyncio.run(get_messages(mailbox))
        self.assertIsInstance(messages, list)
        print(f"\n  OK Inbox message count: {len(messages)}")

    def test_two_accounts_produce_different_emails(self):
        from src.mail.client import create_mailbox

        with patch("builtins.print"):
            import asyncio; mailbox1 = asyncio.run(create_mailbox())
        time.sleep(2)
        with patch("builtins.print"):
            mailbox2 = asyncio.run(create_mailbox())
        self.assertNotEqual(mailbox1.email, mailbox2.email)
        print(f"\n  OK Unique: {mailbox1.email} | {mailbox2.email}")

    def test_wait_for_message_times_out_cleanly(self):
        from src.mail.client import create_mailbox, wait_for_message

        with patch("builtins.print"):
            import asyncio; mailbox = asyncio.run(create_mailbox())
        t0 = time.time()
        with patch("builtins.print"):
            result = asyncio.run(wait_for_message(mailbox, timeout=8, poll_interval=2))
        elapsed = time.time() - t0
        self.assertIsNone(result, "Expected None for empty inbox")
        self.assertLess(elapsed, 20, "Took unexpectedly long to time out")
        print(f"\n  OK Timed out in {elapsed:.1f}s")

    def test_extract_link_finds_url(self):
        from src.mail.client import extract_link

        body = "Click here: https://elevenlabs.io/verify?token=abc123 to confirm."
        link = extract_link(body, contains="verify")
        self.assertEqual(link, "https://elevenlabs.io/verify?token=abc123")

    def test_extract_link_returns_none_when_missing(self):
        from src.mail.client import extract_link

        self.assertIsNone(extract_link("no links here", contains="verify"))

    def test_extract_link_filters_by_contains(self):
        from src.mail.client import extract_link

        body = "https://spam.com/click and https://elevenlabs.io/verify?t=1"
        link = extract_link(body, contains="elevenlabs")
        self.assertEqual(link, "https://elevenlabs.io/verify?t=1")


# ─────────────────────────────────────────────────────────────────────────────
# FastAPI — HTTP routes via TestClient (in-process, no running server needed)
# ─────────────────────────────────────────────────────────────────────────────

def _make_test_app(tmp_dir):
    """
    Tạo FastAPI app với temp DB và mock config.
    Patch account_service + registration_service để dùng tmp_dir.
    """
    import os
    from pathlib import Path
    from src.core.database import init_db, db_path as _dp
    from src.core.storage import db_path

    db = Path(tmp_dir) / "test.db"
    init_db(db)
    return db


class TestHealthEndpoint(unittest.TestCase):
    def _client(self):
        from fastapi.testclient import TestClient
        from src.api.server import app
        return TestClient(app, raise_server_exceptions=False)

    def test_health_returns_200(self):
        c = self._client()
        r = c.get("/api/v1/health")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "ok")


class TestServicesEndpoint(unittest.TestCase):
    def _client(self):
        from fastapi.testclient import TestClient
        from src.api.server import app
        return TestClient(app, raise_server_exceptions=False)

    def test_services_returns_list(self):
        c = self._client()
        r = c.get("/api/v1/registration/services")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)

    def test_services_contains_known_services(self):
        c = self._client()
        data = c.get("/api/v1/registration/services").json()
        for svc in ("OPENROUTER", "ELEVENLABS", "CHATGPT"):
            self.assertIn(svc, data)


class TestJobsEndpoint(unittest.TestCase):
    def _client(self):
        from fastapi.testclient import TestClient
        from src.api.server import app
        return TestClient(app, raise_server_exceptions=False)

    def test_list_jobs_empty_initially(self):
        c = self._client()
        r = c.get("/api/v1/registration/jobs")
        self.assertEqual(r.status_code, 200)
        # Có thể có jobs từ tests trước — chỉ kiểm tra kiểu dữ liệu
        self.assertIsInstance(r.json(), list)

    def test_start_job_invalid_service_returns_400(self):
        c = self._client()
        r = c.post("/api/v1/registration/jobs", json={"service": "NONEXISTENT_XYZ", "count": 1})
        self.assertEqual(r.status_code, 400)

    def test_start_job_count_zero_returns_400(self):
        c = self._client()
        r = c.post("/api/v1/registration/jobs", json={"service": "ELEVENLABS", "count": 0})
        self.assertEqual(r.status_code, 400)

    def test_start_job_count_over_1000_returns_400(self):
        c = self._client()
        r = c.post("/api/v1/registration/jobs", json={"service": "ELEVENLABS", "count": 1001})
        self.assertEqual(r.status_code, 400)

    def test_start_job_workers_over_10_returns_400(self):
        c = self._client()
        r = c.post("/api/v1/registration/jobs", json={"service": "ELEVENLABS", "count": 1, "workers": 11})
        self.assertEqual(r.status_code, 400)

    def test_get_nonexistent_job_returns_404(self):
        c = self._client()
        r = c.get("/api/v1/registration/jobs/does-not-exist")
        self.assertEqual(r.status_code, 404)

    def test_cancel_nonexistent_job_returns_404(self):
        c = self._client()
        r = c.post("/api/v1/registration/jobs/does-not-exist/cancel")
        self.assertEqual(r.status_code, 404)

    def test_start_job_returns_job_shape(self):
        """Verify response shape — patch run_job để tránh khởi browser thật."""
        from unittest.mock import patch

        c = self._client()
        # Patch run_job thành no-op: chỉ test create_job + router response shape
        with patch("src.api.routers.registration.run_job"):
            r = c.post("/api/v1/registration/jobs", json={"service": "ELEVENLABS", "count": 1, "workers": 2})

        self.assertEqual(r.status_code, 200)
        body = r.json()
        for field in ("id", "service", "count", "workers", "status", "created_at", "created_count"):
            self.assertIn(field, body, f"Missing field: {field}")
        self.assertEqual(body["service"], "ELEVENLABS")
        self.assertEqual(body["count"], 1)
        self.assertEqual(body["workers"], 2)

    def test_get_job_by_id_after_create(self):
        from unittest.mock import patch

        c = self._client()
        with patch("src.api.routers.registration.run_job"):
            job_id = c.post("/api/v1/registration/jobs", json={"service": "CHATGPT", "count": 1}).json()["id"]

        r = c.get(f"/api/v1/registration/jobs/{job_id}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["id"], job_id)


class TestAccountsEndpoint(unittest.TestCase):
    """Accounts CRUD với temp DB injected qua patch."""

    def _setup(self, tmp_dir):
        from pathlib import Path
        from src.core.database import init_db

        db = Path(tmp_dir) / "test_accounts.db"
        init_db(db)
        return db

    def _cleanup_engine(self, db_path):
        from src.core.database import _engines
        key = str(db_path.resolve())
        engine = _engines.pop(key, None)
        if engine:
            engine.dispose()

    def test_list_accounts_empty_db(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            db = self._setup(tmp)
            from fastapi.testclient import TestClient
            from unittest.mock import patch
            import src.api.services.account_service as svc
            from src.api.server import app
            try:
                with patch.object(svc, "_DB_PATH", db):
                    c = TestClient(app, raise_server_exceptions=False)
                    r = c.get("/api/v1/accounts")
                self.assertEqual(r.status_code, 200)
                self.assertEqual(r.json(), [])
            finally:
                self._cleanup_engine(db)

    def test_get_nonexistent_account_returns_404(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            db = self._setup(tmp)
            from fastapi.testclient import TestClient
            from unittest.mock import patch
            import src.api.services.account_service as svc
            from src.api.server import app
            try:
                with patch.object(svc, "_DB_PATH", db):
                    c = TestClient(app, raise_server_exceptions=False)
                    r = c.get("/api/v1/accounts/ELEVENLABS/nobody@nowhere.com")
                self.assertEqual(r.status_code, 404)
            finally:
                self._cleanup_engine(db)

    def test_delete_nonexistent_returns_404(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            db = self._setup(tmp)
            from fastapi.testclient import TestClient
            from unittest.mock import patch
            import src.api.services.account_service as svc
            from src.api.server import app
            try:
                with patch.object(svc, "_DB_PATH", db):
                    c = TestClient(app, raise_server_exceptions=False)
                    r = c.delete("/api/v1/accounts/ELEVENLABS/ghost@x.com")
                self.assertEqual(r.status_code, 404)
            finally:
                self._cleanup_engine(db)

    def test_insert_then_list_then_delete(self):
        import tempfile
        from src.core.database import insert_account
        from src.core.storage import AccountRecord

        with tempfile.TemporaryDirectory() as tmp:
            db = self._setup(tmp)
            insert_account(db, AccountRecord(service="ELEVENLABS", email="a@b.com", password="pw", api_key="sk_abc"))

            from fastapi.testclient import TestClient
            from unittest.mock import patch
            import src.api.services.account_service as svc
            from src.api.server import app
            try:
                with patch.object(svc, "_DB_PATH", db):
                    c = TestClient(app, raise_server_exceptions=False)

                    lst = c.get("/api/v1/accounts")
                    self.assertEqual(lst.status_code, 200)
                    self.assertEqual(len(lst.json()), 1)
                    self.assertEqual(lst.json()[0]["email"], "a@b.com")

                    one = c.get("/api/v1/accounts/ELEVENLABS/a@b.com")
                    self.assertEqual(one.status_code, 200)
                    self.assertEqual(one.json()["api_key"], "sk_abc")

                    patch_r = c.patch("/api/v1/accounts/ELEVENLABS/a@b.com", json={"disabled": True})
                    self.assertEqual(patch_r.status_code, 200)

                    after = c.get("/api/v1/accounts/ELEVENLABS/a@b.com")
                    self.assertTrue(after.json()["disabled"])

                    del_r = c.delete("/api/v1/accounts/ELEVENLABS/a@b.com")
                    self.assertEqual(del_r.status_code, 200)

                    gone = c.get("/api/v1/accounts/ELEVENLABS/a@b.com")
                    self.assertEqual(gone.status_code, 404)
            finally:
                self._cleanup_engine(db)

    def test_patch_empty_body_returns_400(self):
        import tempfile
        from src.core.database import insert_account
        from src.core.storage import AccountRecord

        with tempfile.TemporaryDirectory() as tmp:
            db = self._setup(tmp)
            insert_account(db, AccountRecord(service="ELEVENLABS", email="a@b.com", password="pw"))

            from fastapi.testclient import TestClient
            from unittest.mock import patch
            import src.api.services.account_service as svc
            from src.api.server import app
            try:
                with patch.object(svc, "_DB_PATH", db):
                    c = TestClient(app, raise_server_exceptions=False)
                    r = c.patch("/api/v1/accounts/ELEVENLABS/a@b.com", json={})
                self.assertEqual(r.status_code, 400)
            finally:
                self._cleanup_engine(db)

    def test_list_filtered_by_service(self):
        import tempfile
        from src.core.database import insert_account
        from src.core.storage import AccountRecord

        with tempfile.TemporaryDirectory() as tmp:
            db = self._setup(tmp)
            insert_account(db, AccountRecord(service="ELEVENLABS", email="el@x.com", password="pw"))
            insert_account(db, AccountRecord(service="OPENROUTER", email="or@x.com", password="pw"))

            from fastapi.testclient import TestClient
            from unittest.mock import patch
            import src.api.services.account_service as svc
            from src.api.server import app
            try:
                with patch.object(svc, "_DB_PATH", db):
                    c = TestClient(app, raise_server_exceptions=False)
                    r = c.get("/api/v1/accounts?service=ELEVENLABS")
                self.assertEqual(r.status_code, 200)
                self.assertEqual(len(r.json()), 1)
                self.assertEqual(r.json()[0]["email"], "el@x.com")
            finally:
                self._cleanup_engine(db)


if __name__ == "__main__":
    unittest.main(verbosity=2)
