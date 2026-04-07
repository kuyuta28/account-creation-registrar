"""
router_timestamps.py — TTS with word-level timing alignment.

Routes:
  POST /api/tts/with-timestamps        — full response JSON (audio_base64 + alignment)
  POST /api/tts/stream-with-timestamps — NDJSON stream
"""
from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from .elevenlabs_client import (
    RateLimitError,
    stream_tts_with_timestamps,
    tts_with_timestamps,
)
from .key_pool import load_available_keys, update_quota_after_request
from .schemas import TTSRequest

_log = logging.getLogger(__name__)

router = APIRouter()


def _pick_keys():
    keys = load_available_keys()
    if not keys:
        raise HTTPException(503, detail="No ElevenLabs keys available")
    return keys


async def _build_kwargs(req: TTSRequest, api_key: str) -> dict:
    return dict(
        api_key=api_key,
        voice_id=req.voice_id,
        text=req.text,
        model_id=req.model_id,
        output_format=req.output_format,
        voice_settings=req.voice_settings.model_dump(),
        language_code=req.language_code,
        seed=req.seed,
        previous_text=req.previous_text,
        next_text=req.next_text,
        previous_request_ids=req.previous_request_ids,
        next_request_ids=req.next_request_ids,
        apply_text_normalization=req.apply_text_normalization,
        apply_language_text_normalization=req.apply_language_text_normalization,
    )


@router.post("/tts/with-timestamps")
async def tts_with_timestamps_endpoint(req: TTSRequest) -> dict:
    """Generate TTS và trả về JSON với audio (base64) + word-level timestamps.

    Response:
    ```json
    {
      "audio_base64": "<base64 mp3>",
      "alignment": {
        "characters": ["H","e","l","l","o"],
        "character_start_times_seconds": [0.0, 0.05, ...],
        "character_end_times_seconds": [0.05, 0.1, ...]
      },
      "normalized_alignment": { ... }
    }
    ```
    Dùng khi cần sync text với audio (subtitle, highlight từng chữ...).
    """
    keys = _pick_keys()
    last_err = ""

    for key_entry in keys:
        try:
            kwargs = await _build_kwargs(req, key_entry.api_key)
            result = await tts_with_timestamps(**kwargs)
        except RateLimitError:
            _log.warning("Key %s rate limited (timestamps)", key_entry.email)
            last_err = "rate_limited"
            continue
        except Exception as exc:  # noqa: BLE001 — HTTP boundary: always re-raises as HTTPException
            _log.error("Key %s error: %s", key_entry.email, exc)
            raise HTTPException(502, detail=str(exc))

        return result

    raise HTTPException(503, detail=f"All keys exhausted: {last_err}")


@router.post("/tts/stream-with-timestamps")
async def stream_tts_with_timestamps_endpoint(req: TTSRequest) -> StreamingResponse:
    """Stream TTS dưới dạng NDJSON — mỗi dòng là 1 JSON chunk với audio + timestamps.

    Dùng khi real-time highlight từng chữ khi đọc đến.
    Content-Type: application/x-ndjson
    """
    keys = _pick_keys()
    last_err = ""

    for key_entry in keys:
        try:
            kwargs = await _build_kwargs(req, key_entry.api_key)
            client, resp = await stream_tts_with_timestamps(**kwargs)
        except RateLimitError:
            _log.warning("Key %s rate limited (stream-timestamps)", key_entry.email)
            last_err = "rate_limited"
            continue
        except Exception as exc:  # noqa: BLE001 — HTTP boundary: always re-raises as HTTPException
            raise HTTPException(502, detail=str(exc))

        char_count = _parse_int_header(resp.headers.get("x-character-count"))
        char_limit = _parse_int_header(resp.headers.get("x-character-limit"))
        email = key_entry.email

        asyncio.create_task(update_quota_after_request(email, char_count, char_limit))

        async def _generate(c=client, r=resp):
            try:
                async for chunk in r.aiter_bytes(chunk_size=4096):
                    yield chunk
            finally:
                await r.aclose()
                await c.aclose()

        return StreamingResponse(
            _generate(),
            media_type="application/x-ndjson",
            headers={
                "X-Used-Account": email,
                "X-Request-Id": resp.headers.get("request-id", ""),
            },
        )

    raise HTTPException(503, detail=f"All keys exhausted: {last_err}")


def _parse_int_header(value) -> int | None:
    try:
        return int(value) if value is not None else None
    except (ValueError, TypeError):
        return None
