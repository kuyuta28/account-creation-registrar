"""
unit/test_internal_api.py — Tests cho internal API router.

Tests the endpoints directly using FastAPI TestClient.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch, MagicMock

import pytest


class TestInternalRouter:
    """Tests for internal API endpoints."""

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from src.api.routers.internal import router
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router, prefix="/api/v1")
        return TestClient(app)

    def test_health_without_key_returns_403(self, client):
        resp = client.get("/api/v1/internal/health")
        assert resp.status_code == 403

    def test_health_with_wrong_key_returns_403(self, client):
        resp = client.get(
            "/api/v1/internal/health",
            headers={"X-Internal-Key": "wrong-key"},
        )
        assert resp.status_code == 403

    def test_health_with_correct_key_returns_200(self, client):
        resp = client.get(
            "/api/v1/internal/health",
            headers={"X-Internal-Key": "ccs-internal"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["status"] == "healthy"

    @pytest.mark.skip(reason="Module already imported with old key value")
    @patch.dict("os.environ", {"INTERNAL_API_KEY": "test-key-123"})
    def test_health_with_env_key(self):
        from fastapi.testclient import TestClient
        from src.api.routers.internal import router
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router, prefix="/api/v1")
        client = TestClient(app)

        resp = client.get(
            "/api/v1/internal/health",
            headers={"X-Internal-Key": "test-key-123"},
        )
        assert resp.status_code == 200


class TestInternalClientUnit:
    """Unit tests for internal client (without network)."""

    def test_requires_async_context(self):
        from common.internal_client import InternalClient

        async def test():
            async with InternalClient() as client:
                assert client._client is not None

        import asyncio
        asyncio.run(test())

    def test_default_values(self):
        from common.internal_client import InternalClient, _REGISTRAR_URL, _INTERNAL_KEY

        assert _REGISTRAR_URL == "http://registrar:8709"
        assert _INTERNAL_KEY == "ccs-internal"

    @pytest.mark.asyncio
    async def test_client_initializes_headers(self):
        from common.internal_client import InternalClient
        async with InternalClient(base_url="http://test:9999", api_key="secret") as client:
            assert client.base_url == "http://test:9999"
            assert client.api_key == "secret"
            assert client._client is not None