"""
history_client.py — ElevenLabs History API client.

Chức năng:
  list_history()               — GET /v1/history
  get_history_item()           — GET /v1/history/{id}
  delete_history_item()        — DELETE /v1/history/{id}
  stream_history_audio()       — GET /v1/history/{id}/audio (streaming)
  stream_history_download()    — POST /v1/history/download (zip stream)
"""
from __future__ import annotations


import httpx

from ._http import api_delete, api_get, api_stream

_BASE = "/v1/history"


async def list_history(
    api_key: str,
    page_size: int = 100,
    start_after_history_item_id: str | None = None,
    voice_id: str | None = None,
) -> dict:
    """Lấy list history items. Trả về {"history": [...], "has_more": bool}."""
    params: dict = {"page_size": page_size}
    if start_after_history_item_id:
        params["start_after_history_item_id"] = start_after_history_item_id
    if voice_id:
        params["voice_id"] = voice_id
    return await api_get(api_key, _BASE, params=params)


async def get_history_item(api_key: str, history_item_id: str) -> dict:
    """Lấy chi tiết 1 history item (metadata + character count)."""
    return await api_get(api_key, f"{_BASE}/{history_item_id}")


async def delete_history_item(api_key: str, history_item_id: str) -> dict:
    """Xóa 1 history item."""
    return await api_delete(api_key, f"{_BASE}/{history_item_id}")


async def stream_history_audio(
    api_key: str,
    history_item_id: str,
) -> tuple[httpx.AsyncClient, httpx.Response]:
    """Stream audio của 1 history item. Caller PHẢI close (client, response)."""
    # GET request nên dùng api_stream không hợp — dùng httpx trực tiếp
    from ._http import _auth_headers, _raise_for_status, _BASE_URL
    url = f"{_BASE_URL}{_BASE}/{history_item_id}/audio"
    client = httpx.AsyncClient(timeout=30.0)
    try:
        req = client.build_request("GET", url, headers=_auth_headers(api_key))
        resp = await client.send(req, stream=True)
    except Exception:
        await client.aclose()
        raise
    try:
        _raise_for_status(resp)
    except Exception:
        await resp.aclose()
        await client.aclose()
        raise
    return client, resp


async def stream_history_download(
    api_key: str,
    history_item_ids: list[str],
) -> tuple[httpx.AsyncClient, httpx.Response]:
    """Download nhiều history items dưới dạng zip stream. Caller PHẢI close."""
    return await api_stream(
        api_key,
        f"{_BASE}/download",
        body={"history_item_ids": history_item_ids},
        accept="application/zip",
    )
