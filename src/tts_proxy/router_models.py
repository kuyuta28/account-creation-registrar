"""
router_models.py — ElevenLabs Models list (item 12).

Routes:
  GET /api/models  — danh sách tất cả models
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from .errors import RateLimitError
from .key_pool import load_available_keys
from .models_client import list_models

_log = logging.getLogger(__name__)

router = APIRouter()


@router.get("/models")
async def list_models_endpoint() -> dict:
    """Danh sách tất cả AI models của ElevenLabs.

    Mỗi model có:
      model_id, name, description,
      can_do_text_to_speech, can_do_voice_conversion, can_do_text_to_speech_streaming,
      languages: [{"language_id": "en", "name": "English"}, ...],
      max_characters_request_subscribed_user,
      token_cost_factor

    Dùng để:
    - Biết model nào support TTS / STS
    - Biết character limits của từng model
    - Enumerate tất cả language codes supported
    """
    keys = load_available_keys()
    if not keys:
        raise HTTPException(503, detail="No ElevenLabs keys available")

    key = keys[0]
    try:
        models = await list_models(key.api_key)
        return {"models": models, "count": len(models)}
    except RateLimitError:
        raise HTTPException(429, detail="Rate limited")
    except Exception as exc:  # noqa: BLE001 — HTTP boundary: always re-raises as HTTPException
        raise HTTPException(502, detail=str(exc))
