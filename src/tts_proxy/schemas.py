"""
schemas.py — Pydantic models cho TTS Proxy API.

Covers: TTS, TTS Timestamps, Speech-to-Speech, Voice CRUD,
        Pronunciation Dictionaries, History, User, Models.
Tham khảo: https://elevenlabs.io/docs/api-reference/
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class VoiceSettings(BaseModel):
    stability: float = 0.5
    similarity_boost: float = 0.75
    style: float = 0.0
    use_speaker_boost: bool = True
    speed: float = 1.0  # Playback speed (0.7–1.2)


class TTSRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    text: str
    voice_id: str
    model_id: str
    output_format: str = "mp3_44100_128"
    voice_settings: VoiceSettings = Field(default_factory=VoiceSettings)

    # Ngôn ngữ (ISO 639-1) — force ngôn ngữ cụ thể, tránh auto-detect sai
    language_code: str | None = None

    # Determinism — same seed + same params → same audio
    seed: int | None = None

    # Context để giữ continuity khi split văn bản dài
    previous_text: str | None = None
    next_text: str | None = None
    previous_request_ids: list[str] = Field(default_factory=list)  # max 3
    next_request_ids: list[str] = Field(default_factory=list)       # max 3

    # Text normalization: 'auto' | 'on' | 'off'
    apply_text_normalization: str = "auto"

    # Japanese language normalization (cảnh báo: tăng latency đáng kể)
    apply_language_text_normalization: bool = False


# ─────────────────────────────────────────────────────────────────────────────
# TTS WebSocket params (query string khi connect)
# ─────────────────────────────────────────────────────────────────────────────

class TTSWebSocketParams(BaseModel):
    """Params truyền qua query string khi connect TTS WebSocket."""
    model_config = ConfigDict(protected_namespaces=())

    model_id: str = "eleven_v3"
    language_code: str | None = None
    output_format: str = "mp3_44100_128"
    enable_logging: bool = True
    enable_ssml_parsing: bool = False
    inactivity_timeout: int = 20
    sync_alignment: bool = False
    auto_mode: bool = False
    apply_text_normalization: Literal["auto", "on", "off"] = "auto"
    seed: int | None = None


# ─────────────────────────────────────────────────────────────────────────────
# Voice CRUD
# ─────────────────────────────────────────────────────────────────────────────

class VoiceSettingsEdit(BaseModel):
    """Edit default settings của 1 voice."""
    stability: float = Field(ge=0.0, le=1.0, default=0.5)
    similarity_boost: float = Field(ge=0.0, le=1.0, default=0.75)
    style: float = Field(ge=0.0, le=1.0, default=0.0)
    use_speaker_boost: bool = True
    speed: float = Field(ge=0.7, le=1.2, default=1.0)


# ─────────────────────────────────────────────────────────────────────────────
# History
# ─────────────────────────────────────────────────────────────────────────────

class HistoryDownloadRequest(BaseModel):
    """Download nhiều history items dưới dạng zip."""
    history_item_ids: list[str] = Field(min_length=1)


# ─────────────────────────────────────────────────────────────────────────────
# Pronunciation Dictionaries
# ─────────────────────────────────────────────────────────────────────────────

class PronunciationRuleAlias(BaseModel):
    """Rule dạng alias: thay thế whole word/phrase bằng alias khác."""
    type: Literal["alias"] = "alias"
    string_to_replace: str
    alias: str


class PronunciationRulePhoneme(BaseModel):
    """Rule dạng phoneme: đọc theo IPA hoặc CMU-Arpabet."""
    type: Literal["phoneme"] = "phoneme"
    string_to_replace: str
    phoneme: str
    alphabet: Literal["ipa", "cmu-arpabet"] = "ipa"


class CreateDictionaryRequest(BaseModel):
    """Tạo pronunciation dictionary từ rules."""
    name: str
    rules: list[PronunciationRuleAlias | PronunciationRulePhoneme]
    description: str | None = None
    workspace_access: Literal["admin", "editor"] | None = None


class AddRulesRequest(BaseModel):
    """Thêm rules vào dictionary (tạo version mới)."""
    rules: list[PronunciationRuleAlias | PronunciationRulePhoneme] = Field(min_length=1)


class RemoveRulesRequest(BaseModel):
    """Xóa rules theo string_to_replace (tạo version mới)."""
    rule_strings: list[str] = Field(min_length=1)

