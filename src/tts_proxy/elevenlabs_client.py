"""
elevenlabs_client.py — ElevenLabs TTS API client (Text-to-Speech + Timestamps).

Public API:
  stream_tts(...)                    -> tuple[httpx.AsyncClient, httpx.Response]  — audio stream
  tts_with_timestamps(...)           -> dict  — JSON {audio_base64, alignment, normalized_alignment}
  stream_tts_with_timestamps(...)    -> tuple[httpx.AsyncClient, httpx.Response]  — NDJSON stream
  list_voices(api_key)               -> list[dict]  — GET /v2/voices

Errors:
  RateLimitError   — HTTP 429, thử key khác
  (re-exported từ errors.py)
"""
from __future__ import annotations

from typing import Any

import httpx

from ._http import api_stream
from .errors import RateLimitError  # re-export để backward compat

__all__ = [
    "RateLimitError",
    "_build_tts_body",
    "list_voices",
    "stream_tts",
    "stream_tts_with_timestamps",
    "tts_with_timestamps",
]

_TTS_STREAM_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream"
_VOICES_URL = "https://api.elevenlabs.io/v2/voices"


def _build_tts_body(
    text: str,
    model_id: str,
    voice_settings: dict,
    language_code: str | None,
    seed: int | None,
    previous_text: str | None,
    next_text: str | None,
    previous_request_ids: list[str],
    next_request_ids: list[str],
    apply_text_normalization: str,
    apply_language_text_normalization: bool,
) -> dict:
    """Pure: build JSON body cho TTS request."""
    body: dict[str, Any] = {
        "text": text,
        "model_id": model_id,
        "voice_settings": voice_settings,
        "apply_text_normalization": apply_text_normalization,
        "apply_language_text_normalization": apply_language_text_normalization,
    }
    if language_code:
        body["language_code"] = language_code
    if seed is not None:
        body["seed"] = seed
    if previous_text:
        body["previous_text"] = previous_text
    if next_text:
        body["next_text"] = next_text
    if previous_request_ids:
        body["previous_request_ids"] = previous_request_ids[:3]
    if next_request_ids:
        body["next_request_ids"] = next_request_ids[:3]
    return body


async def stream_tts(
    api_key: str,
    voice_id: str,
    text: str,
    model_id: str,
    output_format: str,
    voice_settings: dict,
    language_code: str | None = None,
    seed: int | None = None,
    previous_text: str | None = None,
    next_text: str | None = None,
    previous_request_ids: list[str] | None = None,
    next_request_ids: list[str] | None = None,
    apply_text_normalization: str = "auto",
    apply_language_text_normalization: bool = False,
    timeout: float = 60.0,
) -> tuple[httpx.AsyncClient, httpx.Response]:
    """Mở streaming TTS request tới ElevenLabs.

    Trả về (client, response) — caller PHẢI close sau khi stream xong.
    Response headers có: x-character-count, request-id
    Raise RateLimitError nếu 429, RuntimeError nếu lỗi khác.
    """
    url = _TTS_STREAM_URL.format(voice_id=voice_id)
    body = _build_tts_body(
        text=text,
        model_id=model_id,
        voice_settings=voice_settings,
        language_code=language_code,
        seed=seed,
        previous_text=previous_text,
        next_text=next_text,
        previous_request_ids=previous_request_ids or [],
        next_request_ids=next_request_ids or [],
        apply_text_normalization=apply_text_normalization,
        apply_language_text_normalization=apply_language_text_normalization,
    )

    client = httpx.AsyncClient(timeout=timeout)
    try:
        request = client.build_request(
            "POST",
            url,
            headers={
                "xi-api-key": api_key,
                "Content-Type": "application/json",
                "Accept": "audio/mpeg",
            },
            params={"output_format": output_format},
            json=body,
        )
        resp = await client.send(request, stream=True)
    except Exception:
        await client.aclose()
        raise

    if resp.status_code == 429:
        await resp.aclose()
        await client.aclose()
        raise RateLimitError(f"Rate limited on voice_id={voice_id}")

    if resp.status_code != 200:
        body_bytes = await resp.aread()
        await resp.aclose()
        await client.aclose()
        raise RuntimeError(
            f"ElevenLabs error {resp.status_code}: {body_bytes.decode(errors='replace')[:300]}"
        )

    return client, resp


async def list_voices(
    api_key: str,
    voice_type: str = "default",
    category: str | None = None,
    page_size: int = 100,
    timeout: float = 15.0,
) -> list[dict]:
    """Lấy danh sách voices từ ElevenLabs.

    voice_type: 'default' | 'personal' | 'community' | 'workspace' | 'saved'
    category: 'premade' | 'cloned' | 'generated' | 'professional'
    """
    params: dict[str, Any] = {
        "voice_type": voice_type,
        "page_size": page_size,
        "include_total_count": False,
    }
    if category:
        params["category"] = category
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.get(
            _VOICES_URL,
            headers={"xi-api-key": api_key},
            params=params,
        )
    if resp.status_code == 429:
        raise RateLimitError("Rate limited on list_voices")
    if resp.status_code != 200:
        raise RuntimeError(
            f"ElevenLabs voices error {resp.status_code}: {resp.text[:200]}"
        )
    return resp.json().get("voices", [])


async def tts_with_timestamps(
    api_key: str,
    voice_id: str,
    text: str,
    model_id: str,
    output_format: str,
    voice_settings: dict,
    language_code: str | None = None,
    seed: int | None = None,
    previous_text: str | None = None,
    next_text: str | None = None,
    previous_request_ids: list[str] | None = None,
    next_request_ids: list[str] | None = None,
    apply_text_normalization: str = "auto",
    apply_language_text_normalization: bool = False,
    timeout: float = 90.0,
) -> dict:
    """Gọi /v1/text-to-speech/{voice_id}/with-timestamps, trả về JSON.

    Response: {
      "audio_base64": "<base64 encoded mp3>",
      "alignment": { "characters": [...], "character_start_times_seconds": [...],
                     "character_end_times_seconds": [...] },
      "normalized_alignment": { ... }
    }
    """
    body = _build_tts_body(
        text=text, model_id=model_id, voice_settings=voice_settings,
        language_code=language_code, seed=seed, previous_text=previous_text,
        next_text=next_text,
        previous_request_ids=previous_request_ids or [],
        next_request_ids=next_request_ids or [],
        apply_text_normalization=apply_text_normalization,
        apply_language_text_normalization=apply_language_text_normalization,
    )
    return await _tts_post_json(
        api_key, f"/v1/text-to-speech/{voice_id}/with-timestamps",
        body, output_format, timeout
    )


async def _tts_post_json(
    api_key: str, path: str, body: dict, output_format: str, timeout: float
) -> dict:
    """POST TTS body, expect JSON response (for with-timestamps endpoints)."""
    import httpx as _httpx
    url = f"https://api.elevenlabs.io{path}"
    async with _httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(
            url,
            headers={"xi-api-key": api_key, "Content-Type": "application/json"},
            params={"output_format": output_format},
            json=body,
        )
    if resp.status_code == 429:
        raise RateLimitError(f"Rate limited on {path}")
    if resp.status_code != 200:
        raise RuntimeError(f"ElevenLabs error {resp.status_code}: {resp.text[:300]}")
    return resp.json()


async def stream_tts_with_timestamps(
    api_key: str,
    voice_id: str,
    text: str,
    model_id: str,
    output_format: str,
    voice_settings: dict,
    language_code: str | None = None,
    seed: int | None = None,
    previous_text: str | None = None,
    next_text: str | None = None,
    previous_request_ids: list[str] | None = None,
    next_request_ids: list[str] | None = None,
    apply_text_normalization: str = "auto",
    apply_language_text_normalization: bool = False,
    timeout: float = 90.0,
) -> tuple[httpx.AsyncClient, httpx.Response]:
    """Stream /v1/text-to-speech/{voice_id}/stream-with-timestamps.

    Response là NDJSON stream — mỗi dòng là 1 JSON object:
    { "audio_base64": "...", "alignment": {...}, "normalized_alignment": {...} }
    Caller PHẢI close (client, response) sau khi đọc xong.
    """
    body = _build_tts_body(
        text=text, model_id=model_id, voice_settings=voice_settings,
        language_code=language_code, seed=seed, previous_text=previous_text,
        next_text=next_text,
        previous_request_ids=previous_request_ids or [],
        next_request_ids=next_request_ids or [],
        apply_text_normalization=apply_text_normalization,
        apply_language_text_normalization=apply_language_text_normalization,
    )
    return await api_stream(
        api_key,
        f"/v1/text-to-speech/{voice_id}/stream-with-timestamps",
        body=body,
        params={"output_format": output_format},
        accept="application/json",
        timeout=timeout,
    )

