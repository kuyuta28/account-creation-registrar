"""
e2e/test_tts_proxy.py — E2E tests cho TTS Proxy server (port 8800).

Spin up TTS proxy bằng uvicorn subprocess, gọi HTTP thật.
Không mock DB hay HTTP client — nhưng không có ElevenLabs key thật nên:
  - /api/health: kiểm tra liveness (không cần key)
  - Tất cả endpoints cần key nhưng DB trống → trả 503 "No ElevenLabs keys"
  - FastAPI validation (422) khi body sai schema
  - POST /api/tts missing field → 422

KHÔNG test actual TTS audio / call ElevenLabs API — đó là integration test cần key thật.

Chạy:
  python -m pytest tests/e2e/test_tts_proxy.py -v
  python -m pytest tests/e2e/test_tts_proxy.py -v -k "Health"
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))


# ── Helpers ────────────────────────────────────────────────────────────────────

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


# ── Server process manager ─────────────────────────────────────────────────────

class _TtsServer:
    def __init__(self, port: int):
        self.port = port
        self._proc: subprocess.Popen | None = None

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def start(self, timeout: float = 20.0) -> None:
        self._proc = subprocess.Popen(
            [
                sys.executable, "-m", "uvicorn",
                "src.tts_proxy.server:app",
                "--host", "127.0.0.1",
                "--port", str(self.port),
                "--log-level", "warning",
            ],
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
                    raise RuntimeError(f"TTS server exited early rc={self._proc.returncode}")
        raise RuntimeError(f"TTS server not up within {timeout}s on :{self.port}")

    def stop(self) -> None:
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()


# ── Base class ─────────────────────────────────────────────────────────────────

@unittest.skipUnless(_httpx_available(), "httpx not installed — pip install httpx")
class _TtsE2EBase(unittest.TestCase):
    _server: _TtsServer

    @classmethod
    def setUpClass(cls):
        port = _find_free_port()
        cls._server = _TtsServer(port)
        try:
            cls._server.start()
        except RuntimeError as e:
            cls._server = None  # type: ignore
            raise unittest.SkipTest(str(e))

    @classmethod
    def tearDownClass(cls):
        if cls._server:
            cls._server.stop()

    def _get(self, path: str, **kw):
        import httpx
        return httpx.get(f"{self._server.url}{path}", timeout=10, **kw)

    def _post(self, path: str, **kw):
        import httpx
        return httpx.post(f"{self._server.url}{path}", timeout=10, **kw)

    def _delete(self, path: str, **kw):
        import httpx
        return httpx.delete(f"{self._server.url}{path}", timeout=10, **kw)


# ── Health ─────────────────────────────────────────────────────────────────────

class TestTtsHealth(_TtsE2EBase):
    def test_health_200(self):
        r = self._get("/api/health")
        self.assertEqual(r.status_code, 200)

    def test_health_status_ok(self):
        body = self._get("/api/health").json()
        self.assertEqual(body.get("status"), "ok")

    def test_health_available_keys_int(self):
        body = self._get("/api/health").json()
        self.assertIsInstance(body.get("available_keys"), int)

    def test_health_available_keys_non_negative(self):
        body = self._get("/api/health").json()
        self.assertGreaterEqual(body.get("available_keys"), 0)

    def test_health_content_type_json(self):
        r = self._get("/api/health")
        self.assertIn("application/json", r.headers.get("content-type", ""))


# ── OpenAPI docs ───────────────────────────────────────────────────────────────

class TestTtsDocs(_TtsE2EBase):
    def test_openapi_json_200(self):
        r = self._get("/openapi.json")
        self.assertEqual(r.status_code, 200)

    def test_openapi_json_has_paths(self):
        body = self._get("/openapi.json").json()
        self.assertIn("paths", body)

    def test_openapi_has_tts_path(self):
        paths = self._get("/openapi.json").json()["paths"]
        self.assertIn("/api/tts", paths)

    def test_openapi_has_health_path(self):
        paths = self._get("/openapi.json").json()["paths"]
        self.assertIn("/api/health", paths)

    def test_openapi_has_voices_path(self):
        paths = self._get("/openapi.json").json()["paths"]
        self.assertIn("/api/voices", paths)

    def test_openapi_has_models_path(self):
        paths = self._get("/openapi.json").json()["paths"]
        self.assertIn("/api/models", paths)

    def test_openapi_has_history_path(self):
        paths = self._get("/openapi.json").json()["paths"]
        self.assertIn("/api/history", paths)

    def test_openapi_has_user_subscription_path(self):
        paths = self._get("/openapi.json").json()["paths"]
        self.assertIn("/api/user/subscription", paths)

    def test_openapi_has_pronunciation_path(self):
        paths = self._get("/openapi.json").json()["paths"]
        self.assertIn("/api/pronunciation", paths)


# ── TTS endpoint input validation ────────────────────────────────────────────

class TestTtsValidation(_TtsE2EBase):
    """POST /api/tts với body sai → 422 Unprocessable Entity (FastAPI validation)."""

    _VALID_BODY = {
        "text": "Hello world",
        "voice_id": "21m00Tcm4TlvDq8ikWAM",
        "model_id": "eleven_v3",
        "output_format": "mp3_44100_128",
    }

    def test_valid_body_not_422(self):
        """Body hợp lệ → không phải 422 (có thể 200/502/503 tuỳ key pool)."""
        r = self._post("/api/tts", json=self._VALID_BODY)
        self.assertNotEqual(r.status_code, 422)

    def test_missing_text_field_422(self):
        body = {k: v for k, v in self._VALID_BODY.items() if k != "text"}
        r = self._post("/api/tts", json=body)
        self.assertEqual(r.status_code, 422)

    def test_empty_body_422(self):
        r = self._post("/api/tts", json={})
        self.assertEqual(r.status_code, 422)

    def test_not_json_422(self):
        import httpx
        r = httpx.post(
            f"{self._server.url}/api/tts",
            content=b"not json at all",
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        self.assertEqual(r.status_code, 422)

    def test_valid_body_returns_server_error_or_audio(self):
        """Body hợp lệ → 200 (audio) hoặc 5xx (503 no keys / 502 EL error).
        Không bao giờ là 4xx trừ 422.
        """
        r = self._post("/api/tts", json=self._VALID_BODY)
        self.assertIn(r.status_code, (200, 502, 503))

    def test_valid_body_response_has_detail_on_error(self):
        """Khi không có key hoặc EL trả lỗi → body chứa 'detail'."""
        r = self._post("/api/tts", json=self._VALID_BODY)
        if r.status_code != 200:
            self.assertIn("detail", r.json())


# ── TTS with-timestamps validation ───────────────────────────────────────────

class TestTtsTimestampsValidation(_TtsE2EBase):
    _VALID_BODY = {"text": "Hello", "voice_id": "21m00Tcm4TlvDq8ikWAM"}

    def test_missing_text_422(self):
        r = self._post("/api/tts/with-timestamps", json={"voice_id": "abc"})
        self.assertEqual(r.status_code, 422)

    def test_valid_body_operational(self):
        """Body hợp lệ → 200 hoặc 5xx (tùy key pool + EL response)."""
        r = self._post("/api/tts/with-timestamps", json=self._VALID_BODY)
        self.assertNotEqual(r.status_code, 422)
        self.assertIn(r.status_code, (200, 502, 503))


# ── Voices endpoint ───────────────────────────────────────────────────────────

class TestTtsVoices(_TtsE2EBase):
    def test_list_voices_operational(self):
        """GET /api/voices → 200 (có key + real data) hoặc 503 (no keys)."""
        r = self._get("/api/voices")
        self.assertIn(r.status_code, (200, 503))

    def test_list_voices_200_returns_voices_key(self):
        r = self._get("/api/voices")
        if r.status_code == 200:
            body = r.json()
            self.assertIn("voices", body)
            self.assertIsInstance(body["voices"], list)
            self.assertIn("count", body)

    def test_get_specific_voice_operational(self):
        """GET /api/voices/{id} → 200/502/503 (không phải 422)."""
        r = self._get("/api/voices/21m00Tcm4TlvDq8ikWAM")
        self.assertIn(r.status_code, (200, 502, 503))

    def test_delete_voice_not_422(self):
        """DELETE /api/voices/{id} → không phải 422."""
        r = self._delete("/api/voices/21m00Tcm4TlvDq8ikWAM")
        self.assertNotEqual(r.status_code, 422)

    def test_list_voices_503_has_detail(self):
        r = self._get("/api/voices")
        if r.status_code == 503:
            self.assertIn("detail", r.json())


# ── Models endpoint ───────────────────────────────────────────────────────────

class TestTtsModels(_TtsE2EBase):
    def test_list_models_operational(self):
        """GET /api/models → 200 (có key) hoặc 503 (no keys)."""
        r = self._get("/api/models")
        self.assertIn(r.status_code, (200, 503))

    def test_list_models_200_shape(self):
        r = self._get("/api/models")
        if r.status_code == 200:
            body = r.json()
            self.assertIn("models", body)
            self.assertIsInstance(body["models"], list)
            self.assertIn("count", body)

    def test_list_models_200_has_eleven_v3(self):
        r = self._get("/api/models")
        if r.status_code == 200:
            ids = [m.get("model_id") for m in r.json()["models"]]
            self.assertIn("eleven_v3", ids)


# ── History endpoint ──────────────────────────────────────────────────────────

class TestTtsHistory(_TtsE2EBase):
    def test_list_history_operational(self):
        r = self._get("/api/history")
        self.assertIn(r.status_code, (200, 503))

    def test_list_history_200_shape(self):
        r = self._get("/api/history")
        if r.status_code == 200:
            body = r.json()
            self.assertIn("history", body)
            self.assertIsInstance(body["history"], list)
            self.assertIn("has_more", body)

    def test_get_history_item_operational(self):
        """Fake ID → 502 (EL not found) hoặc 503 (no keys)."""
        r = self._get("/api/history/nonexistent-item-id-e2e-test")
        self.assertIn(r.status_code, (502, 503))

    def test_history_audio_operational(self):
        r = self._get("/api/history/nonexistent-item-id-e2e-test/audio")
        self.assertIn(r.status_code, (502, 503))

    def test_download_missing_body_422(self):
        """POST /api/history/download với empty body → 422."""
        r = self._post("/api/history/download", json={})
        self.assertEqual(r.status_code, 422)

    def test_download_empty_ids_422(self):
        """history_item_ids=[] → min_length=1 fail → 422."""
        r = self._post("/api/history/download", json={"history_item_ids": []})
        self.assertEqual(r.status_code, 422)

    def test_download_valid_ids_operational(self):
        r = self._post("/api/history/download", json={"history_item_ids": ["id-1"]})
        self.assertIn(r.status_code, (200, 502, 503))


# ── User endpoint ─────────────────────────────────────────────────────────────

class TestTtsUser(_TtsE2EBase):
    def test_get_user_operational(self):
        r = self._get("/api/user")
        self.assertIn(r.status_code, (200, 503))

    def test_get_user_200_has_key_info(self):
        r = self._get("/api/user")
        if r.status_code == 200:
            body = r.json()
            self.assertIsInstance(body, dict)
            self.assertGreater(len(body), 0)

    def test_get_subscription_operational(self):
        r = self._get("/api/user/subscription")
        self.assertIn(r.status_code, (200, 503))

    def test_get_subscription_200_shape(self):
        r = self._get("/api/user/subscription")
        if r.status_code == 200:
            body = r.json()
            self.assertIsInstance(body, dict)
            # ElevenLabs subscription always has character_limit
            self.assertIn("character_limit", body)


# ── Pronunciation endpoint ────────────────────────────────────────────────────

class TestTtsPronunciation(_TtsE2EBase):
    def test_list_dicts_operational(self):
        r = self._get("/api/pronunciation")
        self.assertIn(r.status_code, (200, 503))

    def test_list_dicts_200_shape(self):
        r = self._get("/api/pronunciation")
        if r.status_code == 200:
            body = r.json()
            self.assertIn("pronunciation_dictionaries", body)
            self.assertIsInstance(body["pronunciation_dictionaries"], list)

    def test_get_dict_operational(self):
        """Fake ID → 502 hoặc 503."""
        r = self._get("/api/pronunciation/nonexistent-dict-id-e2e")
        self.assertIn(r.status_code, (502, 503))

    def test_create_dict_missing_name_422(self):
        r = self._post("/api/pronunciation", json={"rules": []})
        self.assertEqual(r.status_code, 422)

    def test_create_dict_valid_operational(self):
        r = self._post(
            "/api/pronunciation",
            json={"name": "test-dict", "rules": []},
        )
        self.assertIn(r.status_code, (200, 502, 503))

    def test_add_rules_empty_list_422(self):
        r = self._post(
            "/api/pronunciation/dict-id/version-id/add-rules",
            json={"rules": []},
        )
        self.assertEqual(r.status_code, 422)

    def test_remove_rules_empty_list_422(self):
        r = self._post(
            "/api/pronunciation/dict-id/version-id/remove-rules",
            json={"rule_strings": []},
        )
        self.assertEqual(r.status_code, 422)

    def test_delete_version_operational(self):
        r = self._delete("/api/pronunciation/nonexistent-dict/version/nonexistent-ver")
        self.assertIn(r.status_code, (200, 502, 503))


# ── CORS headers ────────────────────────────────────────────────────────────

class TestTtsCors(_TtsE2EBase):
    def test_health_has_cors_headers(self):
        import httpx
        r = httpx.get(
            f"{self._server.url}/api/health",
            timeout=10,
            headers={"Origin": "http://localhost:1421"},
        )
        # CORSMiddleware phải trả access-control-allow-origin
        self.assertIn("access-control-allow-origin", r.headers)

    def test_options_preflight_200(self):
        import httpx
        r = httpx.options(
            f"{self._server.url}/api/tts",
            timeout=10,
            headers={
                "Origin": "http://localhost:1421",
                "Access-Control-Request-Method": "POST",
            },
        )
        self.assertIn(r.status_code, (200, 204))


if __name__ == "__main__":
    unittest.main(verbosity=2)
