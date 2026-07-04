"""
unit/test_open_browser_service.py - Tests cho src/api/services/open_browser_service.py

Bao phu:
  - Thieu HOST_BROWSER_AGENT_URL -> loi CONFIGURATION
  - Forward thanh cong -> tra ve launched/pid
  - Agent tu choi launch -> loi INTERNAL
  - Agent tra loi HTTP loi -> loi INTERNAL
  - Timeout ket noi -> loi TIMEOUT
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from common.enums import ErrorCode


@pytest.fixture
def _patch_httpx_client():
    """Auto-cleanup patch httpx.AsyncClient sau moi test."""
    mocks = []
    original_httpx = None

    def _make(response_mock=None):
        nonlocal original_httpx
        client_instance = AsyncMock()
        client_cm = AsyncMock()
        client_cm.__aenter__ = AsyncMock(return_value=client_instance)
        client_cm.__aexit__ = AsyncMock(return_value=None)
        if response_mock is not None:
            client_instance.post = AsyncMock(return_value=response_mock)
        client_cls = MagicMock(return_value=client_cm)
        patcher = patch("httpx.AsyncClient", client_cls)
        mocks.append(patcher)
        return patcher.start(), client_instance

    yield _make
    for patcher in mocks:
        patcher.stop()


class TestOpenBrowserWindow:
    def test_raises_configuration_when_agent_url_missing(self):
        from src.api.services.open_browser_service import open_browser_window
        from src.api.exceptions import AppError

        with pytest.raises(AppError) as exc:
            import asyncio
            asyncio.run(open_browser_window("GMAIL", "a@gmail.com", ""))

        assert exc.value.code == ErrorCode.CONFIGURATION
        assert "HOST_BROWSER_AGENT_URL" in exc.value.message
        assert exc.value.status_code == 503

    def test_raises_configuration_when_agent_url_none(self):
        from src.api.services.open_browser_service import open_browser_window
        from src.api.exceptions import AppError

        with pytest.raises(AppError) as exc:
            import asyncio
            asyncio.run(open_browser_window("GMAIL", "a@gmail.com", None))

        assert exc.value.code == ErrorCode.CONFIGURATION

    def test_forwards_request_and_returns_result(self, _patch_httpx_client):
        from src.api.services.open_browser_service import open_browser_window

        response = AsyncMock()
        response.status_code = 200
        response.json = MagicMock(return_value={"launched": True, "pid": 12345})
        response.raise_for_status = MagicMock()
        _patch_httpx_client(response)

        import asyncio
        result = asyncio.run(open_browser_window(
            "GMAIL", "a@gmail.com", "http://127.0.0.1:9999", "https://mail.google.com"
        ))

        assert result == {"launched": True, "pid": 12345}

    def test_raises_internal_when_agent_refuses_launch(self, _patch_httpx_client):
        from src.api.services.open_browser_service import open_browser_window
        from src.api.exceptions import AppError

        response = AsyncMock()
        response.status_code = 200
        response.json = MagicMock(return_value={"launched": False})
        response.raise_for_status = MagicMock()
        response.text = '{"launched": false}'
        _patch_httpx_client(response)

        with pytest.raises(AppError) as exc:
            import asyncio
            asyncio.run(open_browser_window("GMAIL", "a@gmail.com", "http://127.0.0.1:9999"))

        assert exc.value.code == ErrorCode.INTERNAL
        assert exc.value.status_code == 502

    def test_raises_internal_on_http_status_error(self, _patch_httpx_client):
        from src.api.services.open_browser_service import open_browser_window
        from src.api.exceptions import AppError
        import httpx

        response = AsyncMock()
        response.status_code = 500
        response.text = "agent error"
        response.raise_for_status = MagicMock(side_effect=httpx.HTTPStatusError(
            "server error", request=MagicMock(), response=response
        ))
        _patch_httpx_client(response)

        with pytest.raises(AppError) as exc:
            import asyncio
            asyncio.run(open_browser_window("ELEVENLABS", "a@b.com", "http://127.0.0.1:9999"))

        assert exc.value.code == ErrorCode.INTERNAL
        assert exc.value.status_code == 502
        assert "agent error" in exc.value.message

    def test_raises_timeout_on_request_timeout(self, _patch_httpx_client):
        from src.api.services.open_browser_service import open_browser_window
        from src.api.exceptions import AppError
        import httpx

        response = AsyncMock()
        response.raise_for_status = MagicMock(side_effect=httpx.TimeoutException("timed out"))
        _patch_httpx_client(response)

        with pytest.raises(AppError) as exc:
            import asyncio
            asyncio.run(open_browser_window("GMAIL", "a@gmail.com", "http://127.0.0.1:9999"))

        assert exc.value.code == ErrorCode.TIMEOUT
        assert exc.value.status_code == 504
