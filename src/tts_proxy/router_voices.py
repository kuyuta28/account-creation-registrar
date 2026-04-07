"""
router_voices.py — Voice Management CRUD (item 8).

Routes:
  GET    /api/voices/{voice_id}                    — get voice details
  DELETE /api/voices/{voice_id}                    — delete voice
  POST   /api/voices/{voice_id}/settings           — edit voice settings
  POST   /api/voices/add                           — clone voice (upload audio files)
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from .errors import RateLimitError
from .key_pool import load_available_keys
from .schemas import VoiceSettingsEdit
from .voices_client import (
    add_voice,
    delete_voice,
    edit_voice_settings,
    get_voice,
)

_log = logging.getLogger(__name__)

router = APIRouter()


def _best_key():
    keys = load_available_keys()
    if not keys:
        raise HTTPException(503, detail="No ElevenLabs keys available")
    return keys[0]


@router.get("/voices/{voice_id}")
async def get_voice_endpoint(voice_id: str) -> dict:
    """Lấy thông tin chi tiết của 1 voice. Bao gồm settings, labels, samples."""
    key = _best_key()
    try:
        return await get_voice(key.api_key, voice_id)
    except RateLimitError:
        raise HTTPException(429, detail="Rate limited")
    except Exception as exc:  # noqa: BLE001 — HTTP boundary: always re-raises as HTTPException
        raise HTTPException(502, detail=str(exc))


@router.delete("/voices/{voice_id}")
async def delete_voice_endpoint(voice_id: str) -> dict:
    """Xóa voice khỏi library. Chỉ xóa được voice mình đã tạo (personal voices)."""
    key = _best_key()
    try:
        return await delete_voice(key.api_key, voice_id)
    except RateLimitError:
        raise HTTPException(429, detail="Rate limited")
    except Exception as exc:  # noqa: BLE001 — HTTP boundary: always re-raises as HTTPException
        raise HTTPException(502, detail=str(exc))


@router.post("/voices/{voice_id}/settings")
async def edit_voice_settings_endpoint(voice_id: str, settings: VoiceSettingsEdit) -> dict:
    """Edit default settings của voice (stability, similarity_boost, style, speed...)."""
    key = _best_key()
    try:
        return await edit_voice_settings(key.api_key, voice_id, settings.model_dump())
    except RateLimitError:
        raise HTTPException(429, detail="Rate limited")
    except Exception as exc:  # noqa: BLE001 — HTTP boundary: always re-raises as HTTPException
        raise HTTPException(502, detail=str(exc))


@router.post("/voices/add")
async def add_voice_endpoint(
    name: str = Form(..., description="Tên voice mới"),
    files: list[UploadFile] = File(..., description="Audio samples (mp3, wav, m4a...)"),
    description: str | None = Form(default=None),
    labels: str | None = Form(default=None, description='JSON string, vd: \'{"accent": "american"}\''),
    remove_background_noise: bool = Form(default=False),
) -> dict:
    """Clone voice từ audio samples.

    Upload 1 hoặc nhiều audio files (tổng tối đa ~10 phút).
    Trả về: {"voice_id": "<new_voice_id>"}
    """
    key = _best_key()

    file_tuples = []
    for uf in files:
        data = await uf.read()
        content_type = uf.content_type or "audio/mpeg"
        file_tuples.append((uf.filename or "sample.mp3", data, content_type))

    try:
        return await add_voice(
            api_key=key.api_key,
            name=name,
            files=file_tuples,
            description=description,
            labels=labels,
            remove_background_noise=remove_background_noise,
        )
    except RateLimitError:
        raise HTTPException(429, detail="Rate limited")
    except Exception as exc:  # noqa: BLE001 — HTTP boundary: always re-raises as HTTPException
        raise HTTPException(502, detail=str(exc))
