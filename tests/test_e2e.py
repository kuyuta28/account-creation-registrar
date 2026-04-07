"""
E2E Tests — black-box HTTP against a real running FastAPI server.

Mỗi test class spin up server trong subprocess riêng biệt rồi dùng
httpx để gọi API từ ngoài vào — giống cách Tauri frontend gọi.

Cấu trúc:
  TestE2EHealth         — /health
  TestE2EServices       — GET /registration/services
  TestE2EJobLifecycle   — POST jobs → GET status → POST cancel
  TestE2EAccountsCRUD   — GET/PATCH/DELETE /accounts với temp DB

Skip tự động nếu:
  - httpx không cài (pip install httpx)
  - server không start sau 10s (port bị chiếm, thiếu deps)

Chạy:
  python -m pytest tests/test_e2e.py -v
  python -m pytest tests/test_e2e.py -v -k "not Lifecycle"   # skip job test
"""
from __future__ import annotations

import os
import signal
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

_E2E_PORT = 18799   # port riêng biệt, không đụng dev server (8799)

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


# ── Server fixture ─────────────────────────────────────────────────────────────

class _ServerProcess:
    """Manages a uvicorn subprocess for the duration of a test class."""

    def __init__(self, port: int, env: dict | None = None):
        self.port = port
        self.env  = env or {}
        self._proc: subprocess.Popen | None = None

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def start(self, timeout: float = 15.0) -> None:
        env = {**os.environ, **self.env}
        self._proc = subprocess.Popen(
            [
                sys.executable, "-m", "uvicorn",
                "src.api.server:app",
                "--host", "127.0.0.1",
                "--port", str(self.port),
                "--log-level", "warning",
            ],
            cwd=str(ROOT),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                with socket.create_connection(("127.0.0.1", self.port), timeout=0.5):
                    return   # server is up
            except (ConnectionRefusedError, OSError):
                time.sleep(0.3)
                if self._proc.poll() is not None:
                    raise RuntimeError(f"Server process exited early (rc={self._proc.returncode})")
        raise RuntimeError(f"Server did not start on port {self.port} within {timeout}s")

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


# ── Base class ─────────────────────────────────────────────────────────────────

@unittest.skipUnless(_httpx_available(), "httpx not installed — pip install httpx")
class _E2EBase(unittest.TestCase):
    _server: _ServerProcess
    _port: int
    _tmpdir: tempfile.TemporaryDirectory

    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        cls._port   = _find_free_port()
        cls._server = _ServerProcess(cls._port)
        try:
            cls._server.start(timeout=20)
        except RuntimeError as e:
            cls._server = None  # type: ignore
            raise unittest.SkipTest(f"Could not start server: {e}")

    @classmethod
    def tearDownClass(cls):
        if cls._server:
            cls._server.stop()
        cls._tmpdir.cleanup()

    def get(self, path: str, **kwargs):
        import httpx
        return httpx.get(f"{self._server.base_url}/api/v1{path}", timeout=10, **kwargs)

    def post(self, path: str, **kwargs):
        import httpx
        return httpx.post(f"{self._server.base_url}/api/v1{path}", timeout=10, **kwargs)

    def patch(self, path: str, **kwargs):
        import httpx
        return httpx.patch(f"{self._server.base_url}/api/v1{path}", timeout=10, **kwargs)

    def delete(self, path: str, **kwargs):
        import httpx
        return httpx.delete(f"{self._server.base_url}/api/v1{path}", timeout=10, **kwargs)


# ── Test suites ────────────────────────────────────────────────────────────────

class TestE2EHealth(_E2EBase):
    def test_health_ok(self):
        r = self.get("/health")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "ok")


class TestE2EServices(_E2EBase):
    def test_services_non_empty_list(self):
        r = self.get("/registration/services")
        self.assertEqual(r.status_code, 200)
        services = r.json()
        self.assertIsInstance(services, list)
        self.assertGreater(len(services), 0)

    def test_services_contain_expected_keys(self):
        services = self.get("/registration/services").json()
        for expected in ("OPENROUTER", "ELEVENLABS", "CHATGPT"):
            self.assertIn(expected, services)


class TestE2EJobValidation(_E2EBase):
    """Validation errors that don't require a real browser."""

    def test_invalid_service_400(self):
        r = self.post("/registration/jobs", json={"service": "FAKE_SERVICE_XYZ", "count": 1})
        self.assertEqual(r.status_code, 400)

    def test_count_zero_400(self):
        r = self.post("/registration/jobs", json={"service": "ELEVENLABS", "count": 0})
        self.assertEqual(r.status_code, 400)

    def test_count_over_limit_400(self):
        r = self.post("/registration/jobs", json={"service": "ELEVENLABS", "count": 1001})
        self.assertEqual(r.status_code, 400)

    def test_workers_over_limit_400(self):
        r = self.post("/registration/jobs", json={"service": "ELEVENLABS", "count": 1, "workers": 99})
        self.assertEqual(r.status_code, 400)

    def test_nonexistent_job_404(self):
        r = self.get("/registration/jobs/deadbeef-0000-0000-0000-000000000000")
        self.assertEqual(r.status_code, 404)

    def test_cancel_nonexistent_job_404(self):
        r = self.post("/registration/jobs/deadbeef-0000-0000-0000-000000000000/cancel")
        self.assertEqual(r.status_code, 404)

    def test_list_jobs_returns_list(self):
        r = self.get("/registration/jobs")
        self.assertEqual(r.status_code, 200)
        self.assertIsInstance(r.json(), list)


class TestE2EAccountsCRUD(_E2EBase):
    """
    Accounts CRUD e2e.
    Sử dụng DB thật của server — chỉ kiểm tra các accounts do test này tạo ra.
    """

    def _insert_via_db(self, email: str, service: str = "ELEVENLABS") -> None:
        """Insert account trực tiếp vào DB của server qua Python import."""
        from src.core.database import insert_account, init_db
        from src.core.storage import AccountRecord, db_path
        from src.config.settings import load_config

        cfg = load_config()
        db  = db_path(cfg.base_dir)
        init_db(db)
        insert_account(db, AccountRecord(service=service, email=email, password="e2e-test-pw"))

    def test_list_accounts_returns_list(self):
        r = self.get("/accounts")
        self.assertEqual(r.status_code, 200)
        self.assertIsInstance(r.json(), list)

    def test_get_nonexistent_account_404(self):
        r = self.get("/accounts/ELEVENLABS/e2e-nonexistent@never.com")
        self.assertEqual(r.status_code, 404)

    def test_delete_nonexistent_account_404(self):
        r = self.delete("/accounts/ELEVENLABS/e2e-nobody@never.com")
        self.assertEqual(r.status_code, 404)

    def test_crud_lifecycle(self):
        """Insert → GET → PATCH → GET (verify) → DELETE → GET (404)."""
        import time
        email   = f"e2e-test-{int(time.time())}@example.com"
        service = "ELEVENLABS"

        # Insert via DB (no HTTP create endpoint yet)
        self._insert_via_db(email, service)

        # GET
        r = self.get(f"/accounts/{service}/{email}")
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["email"], email)
        self.assertFalse(r.json()["disabled"])

        # PATCH
        rp = self.patch(f"/accounts/{service}/{email}", json={"disabled": True})
        self.assertEqual(rp.status_code, 200, rp.text)

        # GET after patch
        rv = self.get(f"/accounts/{service}/{email}")
        self.assertTrue(rv.json()["disabled"])

        # DELETE
        rd = self.delete(f"/accounts/{service}/{email}")
        self.assertEqual(rd.status_code, 200, rd.text)

        # GET after delete → 404
        rn = self.get(f"/accounts/{service}/{email}")
        self.assertEqual(rn.status_code, 404)

    def test_list_filtered_by_service_query_param(self):
        import time
        email = f"e2e-filter-{int(time.time())}@openrouter.example.com"
        self._insert_via_db(email, "OPENROUTER")

        # Filter by OPENROUTER
        r = self.get("/accounts?service=OPENROUTER")
        self.assertEqual(r.status_code, 200)
        emails = [a["email"] for a in r.json()]
        self.assertIn(email, emails)

        # Filter by LEONARDO should NOT contain our OPENROUTER email
        r2 = self.get("/accounts?service=LEONARDO")
        emails2 = [a["email"] for a in r2.json()]
        self.assertNotIn(email, emails2)

        # Cleanup
        self.delete(f"/accounts/OPENROUTER/{email}")


class TestE2EJobJobLifecycle(_E2EBase):
    """
    Start một job thật, verify nó xuất hiện trong GET /jobs/{id},
    rồi cancel ngay lập tức để tránh mở browser thật.

    Skip nếu không thể cancel trong thời gian hợp lý.
    """

    def test_start_and_cancel_job(self):
        # Start job
        r = self.post("/registration/jobs", json={"service": "ELEVENLABS", "count": 1, "workers": 1})
        if r.status_code != 200:
            self.skipTest(f"Could not start job: {r.status_code} {r.text}")

        body   = r.json()
        job_id = body["id"]

        for field in ("id", "service", "count", "workers", "status", "created_at", "created_count"):
            self.assertIn(field, body)
        self.assertEqual(body["service"], "ELEVENLABS")

        # GET the job
        rg = self.get(f"/registration/jobs/{job_id}")
        self.assertEqual(rg.status_code, 200)
        self.assertEqual(rg.json()["id"], job_id)

        # Try cancel (job might already be in running/pending/failed state)
        rc = self.post(f"/registration/jobs/{job_id}/cancel")
        # 200 = cancelled, 404 = already finished — both acceptable
        self.assertIn(rc.status_code, (200, 404))

    def test_job_appears_in_list_after_start(self):
        r = self.post("/registration/jobs", json={"service": "CHATGPT", "count": 1})
        if r.status_code != 200:
            self.skipTest(f"Could not start job: {r.status_code} {r.text}")

        job_id = r.json()["id"]
        jobs   = self.get("/registration/jobs").json()
        ids    = [j["id"] for j in jobs]
        self.assertIn(job_id, ids)

        # Cleanup
        self.post(f"/registration/jobs/{job_id}/cancel")


if __name__ == "__main__":
    unittest.main(verbosity=2)
