"""
_http.py — Shared HTTP helpers cho tất cả ElevenLabs client modules.

Tất cả API calls đều dùng chung:
  - Header xi-api-key
  - Error handling: 429 → RateLimitError, khác → RuntimeError
"""
from __future__ import annotations

from typing import Any

import httpx

from .errors import RateLimitError, UnusualActivityError

_BASE_URL = "https://api.elevenlabs.io"


def _auth_headers(api_key: str) -> dict[str, str]:
    return {"xi-api-key": api_key}


def _raise_for_status(resp: httpx.Response) -> None:
    """Raise RateLimitError (429), UnusualActivityError (401 unusual) hoặc RuntimeError (khác) nếu không phải 2xx."""
    if resp.status_code == 429:
        raise RateLimitError("Rate limited — HTTP 429")
    if resp.status_code == 401:
        body = resp.text
        if "detected_unusual_activity" in body:
            raise UnusualActivityError("Unusual activity detected — account blocked by ElevenLabs")
        raise RuntimeError(f"ElevenLabs error 401: {body[:300]}")
    if not (200 <= resp.status_code < 300):
        raise RuntimeError(
            f"ElevenLabs error {resp.status_code}: {resp.text[:300]}"
        )


async def api_get(
    api_key: str,
    path: str,
    params: dict[str, Any] | None = None,
    timeout: float = 15.0,
) -> Any:
    """GET request, trả về parsed JSON."""
    url = f"{_BASE_URL}{path}"
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.get(url, headers=_auth_headers(api_key), params=params)
    _raise_for_status(resp)
    return resp.json()


async def api_post_json(
    api_key: str,
    path: str,
    body: dict[str, Any],
    timeout: float = 15.0,
) -> Any:
    """POST JSON request, trả về parsed JSON."""
    url = f"{_BASE_URL}{path}"
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(
            url,
            headers={**_auth_headers(api_key), "Content-Type": "application/json"},
            json=body,
        )
    _raise_for_status(resp)
    return resp.json()


async def api_post_form(
    api_key: str,
    path: str,
    data: dict[str, Any],
    files: list[tuple[str, tuple[str, bytes, str]]] | None = None,
    timeout: float = 60.0,
) -> Any:
    """POST multipart/form-data request, trả về parsed JSON."""
    url = f"{_BASE_URL}{path}"
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(
            url,
            headers=_auth_headers(api_key),
            data=data,
            files=files or [],
        )
    _raise_for_status(resp)
    return resp.json()


async def api_delete(
    api_key: str,
    path: str,
    timeout: float = 15.0,
) -> Any:
    """DELETE request, trả về parsed JSON."""
    url = f"{_BASE_URL}{path}"
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.delete(url, headers=_auth_headers(api_key))
    _raise_for_status(resp)
    return resp.json()


async def api_stream(
    api_key: str,
    path: str,
    body: dict[str, Any],
    params: dict[str, Any] | None = None,
    accept: str = "audio/mpeg",
    timeout: float = 60.0,
) -> tuple[httpx.AsyncClient, httpx.Response]:
    """POST streaming request. Caller PHẢI close (client, response) sau khi dùng."""
    url = f"{_BASE_URL}{path}"
    client = httpx.AsyncClient(timeout=timeout)
    try:
        req = client.build_request(
            "POST",
            url,
            headers={
                **_auth_headers(api_key),
                "Content-Type": "application/json",
                "Accept": accept,
            },
            params=params,
            json=body,
        )
        resp = await client.send(req, stream=True)
    except Exception:
        await client.aclose()
        raise

    if resp.status_code == 429:
        await resp.aclose()
        await client.aclose()
        raise RateLimitError("Rate limited — HTTP 429")

    if not (200 <= resp.status_code < 300):
        body_bytes = await resp.aread()
        await resp.aclose()
        await client.aclose()
        raise RuntimeError(
            f"ElevenLabs error {resp.status_code}: {body_bytes.decode(errors='replace')[:300]}"
        )

    return client, resp
