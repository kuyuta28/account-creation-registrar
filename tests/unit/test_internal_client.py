"""
unit/test_internal_client.py — Tests cho internal_client.py

Uses mocking to test the client without needing a running server.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch, MagicMock

import pytest


class TestInternalClient:
    def test_client_initializes_with_defaults(self):
        from common.internal_client import InternalClient
        client = InternalClient()
        assert client.base_url == "http://registrar:8709"
        assert client.api_key == "ccs-internal"

    def test_client_accepts_custom_url_and_key(self):
        from common.internal_client import InternalClient
        client = InternalClient(base_url="http://custom:9000", api_key="my-key")
        assert client.base_url == "http://custom:9000"
        assert client.api_key == "my-key"

    @pytest.mark.asyncio
    async def test_context_manager_creates_client(self):
        from common.internal_client import InternalClient
        async with InternalClient() as client:
            assert client._client is not None

    @pytest.mark.asyncio
    async def test_context_manager_uses_documented_timeout(self):
        from common.internal_client import InternalClient
        with patch("httpx.AsyncClient") as async_client:
            async_client.return_value.aclose = AsyncMock()
            async with InternalClient():
                pass
        assert async_client.call_args.kwargs["timeout"] == 30.0

    @pytest.mark.asyncio
    async def test_get_account_returns_data(self):
        from common.internal_client import InternalClient
        async with InternalClient() as client:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"data": {"email": "test@test.com"}}
            client._client.get = AsyncMock(return_value=mock_resp)

            result = await client.get_account("TEST", "test@test.com")
            assert result == {"email": "test@test.com"}

    @pytest.mark.asyncio
    async def test_get_account_returns_none_on_404(self):
        from common.internal_client import InternalClient
        async with InternalClient() as client:
            mock_resp = MagicMock()
            mock_resp.status_code = 404
            client._client.get = AsyncMock(return_value=mock_resp)

            result = await client.get_account("TEST", "not@found.com")
            assert result is None

    @pytest.mark.asyncio
    async def test_upsert_account_returns_created(self):
        from common.internal_client import InternalClient
        async with InternalClient() as client:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"data": {"created": True}}
            client._client.post = AsyncMock(return_value=mock_resp)

            result = await client.upsert_account("TEST", "new@test.com")
            assert result is True

    @pytest.mark.asyncio
    async def test_update_account_returns_true_on_success(self):
        from common.internal_client import InternalClient
        async with InternalClient() as client:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            client._client.patch = AsyncMock(return_value=mock_resp)

            result = await client.update_account("TEST", "test@test.com", password="newpass")
            assert result is True

    @pytest.mark.asyncio
    async def test_update_account_returns_false_on_404(self):
        from common.internal_client import InternalClient
        async with InternalClient() as client:
            mock_resp = MagicMock()
            mock_resp.status_code = 404
            client._client.patch = AsyncMock(return_value=mock_resp)

            result = await client.update_account("TEST", "not@found.com", password="x")
            assert result is False

    @pytest.mark.asyncio
    async def test_list_accounts_unwraps_paginated_contract(self):
        from common.internal_client import InternalClient
        async with InternalClient() as client:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "data": {
                    "accounts": [{"email": "a@test.com"}],
                    "total": 1,
                    "page": 1,
                    "limit": 100,
                    "pages": 1,
                }
            }
            client._client.get = AsyncMock(return_value=mock_resp)

            result = await client.list_accounts("TEST")
            assert result == [{"email": "a@test.com"}]

    @pytest.mark.asyncio
    async def test_list_accounts_accepts_legacy_direct_list(self):
        from common.internal_client import InternalClient
        async with InternalClient() as client:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"data": [{"email": "legacy@test.com"}]}
            client._client.get = AsyncMock(return_value=mock_resp)

            result = await client.list_accounts()
            assert result == [{"email": "legacy@test.com"}]

    @pytest.mark.asyncio
    async def test_health_check_returns_true_when_healthy(self):
        from common.internal_client import InternalClient
        async with InternalClient() as client:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            client._client.get = AsyncMock(return_value=mock_resp)

            result = await client.health_check()
            assert result is True

    @pytest.mark.asyncio
    async def test_health_check_returns_false_on_error(self):
        from common.internal_client import InternalClient
        async with InternalClient() as client:
            import httpx
            client._client.get = AsyncMock(side_effect=httpx.HTTPError("Network error"))

            result = await client.health_check()
            assert result is False

    @pytest.mark.asyncio
    async def test_context_manager_raises_if_not_used(self):
        from common.internal_client import InternalClient
        client = InternalClient()
        with pytest.raises(RuntimeError, match="Use 'async with"):
            await client.get_account("TEST", "test@test.com")
