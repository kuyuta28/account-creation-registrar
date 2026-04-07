"""
models_client.py — ElevenLabs Models API client.

Chức năng:
  list_models()  — GET /v1/models
"""
from __future__ import annotations

from ._http import api_get


async def list_models(api_key: str) -> list[dict]:
    """Lấy danh sách tất cả AI models của ElevenLabs.

    Mỗi model có:
      model_id, name, description, can_do_text_to_speech, can_do_voice_conversion,
      can_do_text_to_speech_streaming, languages (list), max_characters_request_free_user,
      max_characters_request_subscribed_user, ...
    """
    result = await api_get(api_key, "/v1/models")
    # API trả về list trực tiếp, không wrap
    if isinstance(result, list):
        return result
    return result.get("models", [])
