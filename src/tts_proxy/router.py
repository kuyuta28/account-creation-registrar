"""
router.py — FastAPI routes cho TTS Proxy.

Routes:
  GET  /api/health         — liveness check + số key available
  GET  /api/voices         — list voices từ ElevenLabs (dùng key tốt nhất)
  POST /api/tts            — generate + stream audio về client
"""
from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from .elevenlabs_client import RateLimitError, list_voices, stream_tts
from .errors import UnusualActivityError
from .key_pool import disable_key, load_available_keys, mark_key_error, update_quota_after_request
from .schemas import TTSRequest

_log = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    keys = load_available_keys()
    return {"status": "ok", "available_keys": len(keys)}


@router.get("/voices")
async def voices(
    voice_type: str = Query(default="default", description="default | personal | community | workspace | saved"),
    category: str | None = Query(default=None, description="premade | cloned | generated | professional"),
    page_size: int = Query(default=100, ge=1, le=100),
) -> dict:
    """List voices từ ElevenLabs dùng key đầu tiên có sẵn."""
    keys = load_available_keys()
    if not keys:
        raise HTTPException(503, detail="No ElevenLabs keys available")

    for key_entry in keys:
        try:
            result = await list_voices(
                api_key=key_entry.api_key,
                voice_type=voice_type,
                category=category,
                page_size=page_size,
            )
            return {"voices": result, "count": len(result)}
        except RateLimitError:
            continue
        except UnusualActivityError:
            _log.warning("Key %s blocked (unusual activity), disabling", key_entry.email)
            asyncio.create_task(disable_key(key_entry.email))
            continue
        except Exception as exc:  # noqa: BLE001 — HTTP boundary: always re-raises as HTTPException
            raise HTTPException(502, detail=str(exc))

    raise HTTPException(503, detail="All keys rate limited")


@router.post("/tts")
async def tts(req: TTSRequest) -> StreamingResponse:
    """Generate TTS audio, stream về client.

    Response headers:
      X-Used-Account   — email account đã dùng để generate
      X-Request-Id     — ElevenLabs request ID (từ header response)
      X-Character-Count — số characters đã consume (từ header response)
    """
    keys = load_available_keys()
    if not keys:
        raise HTTPException(503, detail="No ElevenLabs keys available")

    voice_settings = req.voice_settings.model_dump()
    last_error = ""

    for key_entry in keys:
        try:
            client, resp = await stream_tts(
                api_key=key_entry.api_key,
                voice_id=req.voice_id,
                text=req.text,
                model_id=req.model_id,
                output_format=req.output_format,
                voice_settings=voice_settings,
                language_code=req.language_code,
                seed=req.seed,
                previous_text=req.previous_text,
                next_text=req.next_text,
                previous_request_ids=req.previous_request_ids,
                next_request_ids=req.next_request_ids,
                apply_text_normalization=req.apply_text_normalization,
                apply_language_text_normalization=req.apply_language_text_normalization,
            )
        except RateLimitError:
            _log.warning("Key %s rate limited, trying next", key_entry.email)
            last_error = "rate_limited"
            continue
        except UnusualActivityError:
            _log.warning("Key %s blocked by ElevenLabs (unusual activity), disabling", key_entry.email)
            asyncio.create_task(disable_key(key_entry.email))
            last_error = "unusual_activity"
            continue
        except Exception as exc:  # noqa: BLE001 — HTTP boundary: always re-raises as HTTPException
            _log.error("Key %s failed: %s", key_entry.email, exc)
            asyncio.create_task(mark_key_error(key_entry.email, str(exc)[:300]))
            raise HTTPException(
                502,
                detail=str(exc),
                headers={"X-Failed-Account": key_entry.email},
            )

        # Đọc quota headers từ ElevenLabs response
        # x-character-count = tổng chars đã dùng tích lũy trong tháng
        # x-character-limit = giới hạn chars tháng này
        char_count = _parse_int_header(resp.headers.get("x-character-count"))
        char_limit = _parse_int_header(resp.headers.get("x-character-limit"))
        request_id = resp.headers.get("request-id", "")

        _log.info(
            "TTS ok via %s (quota=%s%%, chars_used=%s, request_id=%s)",
            key_entry.email,
            "unknown" if key_entry.quota_pct < 0 else key_entry.quota_pct,
            char_count,
            request_id,
        )

        # Fire-and-forget: update quota trong DB từ header thực tế
        email = key_entry.email
        asyncio.create_task(
            update_quota_after_request(email, char_count, char_limit)
        )

        media_type = "audio/mpeg" if req.output_format.startswith("mp3") else "audio/wav"

        async def _generate(c=client, r=resp):
            try:
                async for chunk in r.aiter_bytes(chunk_size=4096):
                    yield chunk
            finally:
                await r.aclose()
                await c.aclose()

        return StreamingResponse(
            _generate(),
            media_type=media_type,
            headers={
                "X-Used-Account": email,
                "X-Request-Id": request_id,
                "X-Character-Count": str(char_count) if char_count is not None else "",
            },
        )

    raise HTTPException(503, detail=f"All keys exhausted: {last_error}")


def _parse_int_header(value: str | None) -> int | None:
    """Parse header string → int, trả None nếu không hợp lệ."""
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None
