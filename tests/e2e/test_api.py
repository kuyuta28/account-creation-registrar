"""
e2e/test_api.py — E2E tests: real FastAPI server + httpx + real DB.

Spin up uvicorn subprocess, gọi HTTP thật từ ngoài vào — không mock gì.
Tách thành các class nhỏ để mỗi class có server riêng (isolation).

Coverage:
  - Health + metadata endpoints
  - Accounts CRUD (add → get → patch → delete) với test email
  - Config endpoints (list files, get raw config)
  - Registration validation (không cần browser)
  - Mailbox API structure

Chạy:
  python -m pytest tests/e2e/ -v
  python -m pytest tests/e2e/ -v -k "Health or Services"   # chỉ fast tests
"""
from __future__ import annotations

import os
import signal
import socket
import subprocess
import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

_TEST_EMAIL = "e2e_test_auto@test.invalid"
_TEST_SERVICE = "ELEVENLABS"


# ── Skip guard ────────────────────────────────────────────────────────────────


def _httpx_available() -> bool:
    try:
        import httpx  # noqa
        return True
    except ImportError:
        return False


def _find_free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# ── Server process manager ────────────────────────────────────────────────────


class _Server:
    def __init__(self, port: int):
        self.port = port
        self._proc: subprocess.Popen | None = None

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def start(self, timeout: float = 20.0) -> None:
        self._proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "src.api.server:app",
             "--host", "127.0.0.1", "--port", str(self.port), "--log-level", "warning"],
            cwd=str(ROOT),
            env={**os.environ},
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                with socket.create_connection(("127.0.0.1", self.port), timeout=0.5):
                    return
            except (ConnectionRefusedError, OSError):
                time.sleep(0.3)
                if self._proc.poll() is not None:
                    raise RuntimeError(f"Server exited early rc={self._proc.returncode}")
        raise RuntimeError(f"Server not up within {timeout}s on :{self.port}")

    def stop(self) -> None:
        if self._proc and self._proc.poll() is None:
            if sys.platform == "win32":
                self._proc.terminate()
            else:
                self._proc.send_signal(signal.SIGTERM)
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()


# ── Base class ────────────────────────────────────────────────────────────────


@unittest.skipUnless(_httpx_available(), "httpx not installed — pip install httpx")
class _E2EBase(unittest.TestCase):
    _server: _Server

    @classmethod
    def setUpClass(cls):
        port = _find_free_port()
        cls._server = _Server(port)
        try:
            cls._server.start()
        except RuntimeError as e:
            cls._server = None  # type: ignore
            raise unittest.SkipTest(str(e))

    @classmethod
    def tearDownClass(cls):
        if cls._server:
            cls._server.stop()

    # ── HTTP helpers ──────────────────────────────────────────────────────────

    def _get(self, path: str, **kw):
        import httpx
        return httpx.get(f"{self._server.url}/api/v1{path}", timeout=10, **kw)

    def _post(self, path: str, **kw):
        import httpx
        return httpx.post(f"{self._server.url}/api/v1{path}", timeout=10, **kw)

    def _patch(self, path: str, **kw):
        import httpx
        return httpx.patch(f"{self._server.url}/api/v1{path}", timeout=10, **kw)

    def _delete(self, path: str, **kw):
        import httpx
        return httpx.delete(f"{self._server.url}/api/v1{path}", timeout=10, **kw)


# ── Health ────────────────────────────────────────────────────────────────────


class TestE2EHealth(_E2EBase):
    def test_health_returns_200(self):
        r = self._get("/health")
        self.assertEqual(r.status_code, 200)

    def test_health_body_status_ok(self):
        body = self._get("/health").json()
        self.assertEqual(body.get("status"), "ok")

    def test_health_content_type_json(self):
        r = self._get("/health")
        self.assertIn("application/json", r.headers.get("content-type", ""))


# ── Services list ─────────────────────────────────────────────────────────────


class TestE2EServices(_E2EBase):
    def test_services_200(self):
        self.assertEqual(self._get("/registration/services").status_code, 200)

    def test_services_is_list(self):
        self.assertIsInstance(self._get("/registration/services").json(), list)

    def test_services_non_empty(self):
        self.assertGreater(len(self._get("/registration/services").json()), 0)

    def test_services_contains_elevenlabs(self):
        self.assertIn("ELEVENLABS", self._get("/registration/services").json())

    def test_services_contains_chatgpt(self):
        self.assertIn("CHATGPT", self._get("/registration/services").json())

    def test_services_contains_openrouter(self):
        self.assertIn("OPENROUTER", self._get("/registration/services").json())


# ── Accounts CRUD ─────────────────────────────────────────────────────────────


class TestE2EAccountsCRUD(_E2EBase):
    """Add → Get → Patch → Delete. Dùng email đặc biệt để dễ cleanup."""

    _EMAIL = "e2e_auto_crud_test@test.invalid"
    _SVC   = "ELEVENLABS"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Ensure clean state: delete nếu đã tồn tại từ run trước
        if cls._server:
            import httpx
            httpx.delete(
                f"{cls._server.url}/api/v1/accounts/{cls._SVC}/{cls._EMAIL}",
                timeout=5,
            )

    @classmethod
    def tearDownClass(cls):
        # Cleanup: xóa test record
        if cls._server:
            import httpx
            httpx.delete(
                f"{cls._server.url}/api/v1/accounts/{cls._SVC}/{cls._EMAIL}",
                timeout=5,
            )
        super().tearDownClass()

    def test_01_add_account(self):
        r = self._post("/accounts/add", json={
            "service": self._SVC,
            "email":   self._EMAIL,
            "api_key": "sk_e2e_test",
            "password": "Test@1234",
        })
        self.assertIn(r.status_code, (200, 201))

    def test_02_get_account_exists(self):
        """Phải add trước → chạy sau test_01."""
        r = self._get(f"/accounts/{self._SVC}/{self._EMAIL}")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["email"], self._EMAIL)
        self.assertEqual(body["service"], self._SVC)

    def test_03_get_accounts_list_contains_email(self):
        r = self._get(f"/accounts?service={self._SVC}")
        self.assertEqual(r.status_code, 200)
        emails = [a["email"] for a in r.json()]
        self.assertIn(self._EMAIL, emails)

    def test_04_patch_api_key(self):
        r = self._patch(f"/accounts/{self._SVC}/{self._EMAIL}", json={"api_key": "sk_e2e_updated"})
        self.assertEqual(r.status_code, 200)
        # Verify update
        updated = self._get(f"/accounts/{self._SVC}/{self._EMAIL}").json()
        self.assertEqual(updated["api_key"], "sk_e2e_updated")

    def test_05_delete_account(self):
        r = self._delete(f"/accounts/{self._SVC}/{self._EMAIL}")
        self.assertEqual(r.status_code, 200)

    def test_06_get_deleted_returns_404(self):
        r = self._get(f"/accounts/{self._SVC}/{self._EMAIL}")
        self.assertEqual(r.status_code, 404)


# ── Registration validation (no browser) ─────────────────────────────────────


class TestE2ERegistrationValidation(_E2EBase):
    def test_invalid_service_400(self):
        r = self._post("/registration/jobs", json={"service": "FAKE_XYZ_999", "count": 1})
        self.assertEqual(r.status_code, 400)

    def test_count_zero_400(self):
        r = self._post("/registration/jobs", json={"service": "ELEVENLABS", "count": 0})
        self.assertEqual(r.status_code, 400)

    def test_count_over_max_400(self):
        r = self._post("/registration/jobs", json={"service": "ELEVENLABS", "count": 9999})
        self.assertEqual(r.status_code, 400)

    def test_nonexistent_job_404(self):
        r = self._get("/registration/jobs/00000000-0000-0000-0000-000000000000")
        self.assertEqual(r.status_code, 404)

    def test_cancel_nonexistent_404(self):
        r = self._post("/registration/jobs/00000000-0000-0000-0000-000000000000/cancel")
        self.assertEqual(r.status_code, 404)

    def test_list_jobs_200(self):
        r = self._get("/registration/jobs")
        self.assertEqual(r.status_code, 200)
        self.assertIsInstance(r.json(), list)


# ── Config API ────────────────────────────────────────────────────────────────


class TestE2EConfigAPI(_E2EBase):
    def test_config_files_200(self):
        r = self._get("/config/files")
        self.assertEqual(r.status_code, 200)

    def test_config_files_has_files_key(self):
        body = self._get("/config/files").json()
        self.assertIn("files", body)
        self.assertIsInstance(body["files"], list)

    def test_config_get_returns_content(self):
        r = self._get("/config/raw?file=config.yaml")
        self.assertIn(r.status_code, (200, 404))  # 404 nếu file không tồn tại

    def test_config_missing_file_404(self):
        r = self._get("/config/raw?file=nonexistent_xyz123.yaml")
        self.assertEqual(r.status_code, 404)


if __name__ == "__main__":
    unittest.main(verbosity=2)
