"""
voices_client.py — ElevenLabs Voice Management API client.

Chức năng:
  get_voice()            — GET /v1/voices/{voice_id}
  delete_voice()         — DELETE /v1/voices/{voice_id}
  edit_voice_settings()  — POST /v1/voices/{voice_id}/settings/edit
  add_voice()            — POST /v1/voices/add (voice cloning, multipart)
"""
from __future__ import annotations


from ._http import api_delete, api_get, api_post_form, api_post_json


async def get_voice(api_key: str, voice_id: str) -> dict:
    """Lấy thông tin chi tiết của 1 voice (settings, labels, samples...)."""
    return await api_get(api_key, f"/v1/voices/{voice_id}")


async def delete_voice(api_key: str, voice_id: str) -> dict:
    """Xóa voice khỏi library của user."""
    return await api_delete(api_key, f"/v1/voices/{voice_id}")


async def edit_voice_settings(api_key: str, voice_id: str, settings: dict) -> dict:
    """Cập nhật settings mặc định của voice (stability, similarity_boost, etc.).

    settings dict cần có các fields:
      stability (float), similarity_boost (float),
      style (float, optional), use_speaker_boost (bool, optional),
      speed (float, optional)
    """
    return await api_post_json(api_key, f"/v1/voices/{voice_id}/settings/edit", settings)


async def add_voice(
    api_key: str,
    name: str,
    files: list[tuple[str, bytes, str]],
    description: str | None = None,
    labels: str | None = None,
    remove_background_noise: bool = False,
) -> dict:
    """Clone voice từ audio files.

    files: list of (filename, audio_bytes, content_type)
      ví dụ: [("sample.mp3", b"...", "audio/mpeg")]
    labels: JSON string, ví dụ: '{"accent": "american"}'
    Trả về: {"voice_id": "..."}
    """
    data: dict = {
        "name": name,
        "remove_background_noise": str(remove_background_noise).lower(),
    }
    if description:
        data["description"] = description
    if labels:
        data["labels"] = labels

    file_tuples = [
        ("files", (fname, data_bytes, ctype))
        for fname, data_bytes, ctype in files
    ]
    return await api_post_form(api_key, "/v1/voices/add", data=data, files=file_tuples)
