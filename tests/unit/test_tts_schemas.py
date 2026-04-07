"""
unit/test_tts_schemas.py — Tests cho src/tts_proxy/schemas.py

Bao phủ: defaults, validation, field constraints, error cases.
Không cần mock — pure Pydantic validation.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.tts_proxy.schemas import (
    AddRulesRequest,
    CreateDictionaryRequest,
    HistoryDownloadRequest,
    PronunciationRuleAlias,
    PronunciationRulePhoneme,
    RemoveRulesRequest,
    TTSRequest,
    TTSWebSocketParams,
    VoiceSettings,
    VoiceSettingsEdit,
)


# ── VoiceSettings ─────────────────────────────────────────────────────────────

class TestVoiceSettings:
    def test_defaults(self):
        s = VoiceSettings()
        assert s.stability == 0.5
        assert s.similarity_boost == 0.75
        assert s.style == 0.0
        assert s.use_speaker_boost is True
        assert s.speed == 1.0

    def test_custom_values(self):
        s = VoiceSettings(stability=0.8, speed=0.9)
        assert s.stability == 0.8
        assert s.speed == 0.9


# ── TTSRequest ────────────────────────────────────────────────────────────────

class TestTTSRequest:
    def test_minimal_required(self):
        req = TTSRequest(text="Hello world", voice_id="abc123")
        assert req.text == "Hello world"
        assert req.voice_id == "abc123"

    def test_defaults(self):
        req = TTSRequest(text="x")
        assert req.model_id == "eleven_v3"
        assert req.output_format == "mp3_44100_128"
        assert req.apply_text_normalization == "auto"
        assert req.apply_language_text_normalization is False
        assert req.previous_request_ids == []
        assert req.next_request_ids == []
        assert req.language_code is None
        assert req.seed is None

    def test_voice_settings_factory(self):
        """Hai instances phải có voice_settings riêng (không share)."""
        r1 = TTSRequest(text="a")
        r2 = TTSRequest(text="b")
        assert r1.voice_settings is not r2.voice_settings

    def test_with_seed(self):
        req = TTSRequest(text="x", seed=42)
        assert req.seed == 42

    def test_with_language_code(self):
        req = TTSRequest(text="x", language_code="vi")
        assert req.language_code == "vi"

    def test_with_context(self):
        req = TTSRequest(
            text="x",
            previous_text="before",
            next_text="after",
            previous_request_ids=["id-1", "id-2"],
        )
        assert req.previous_text == "before"
        assert len(req.previous_request_ids) == 2


# ── TTSWebSocketParams ────────────────────────────────────────────────────────

class TestTTSWebSocketParams:
    def test_defaults(self):
        p = TTSWebSocketParams()
        assert p.model_id == "eleven_v3"
        assert p.output_format == "mp3_44100_128"
        assert p.enable_logging is True
        assert p.enable_ssml_parsing is False
        assert p.inactivity_timeout == 20
        assert p.sync_alignment is False
        assert p.auto_mode is False
        assert p.apply_text_normalization == "auto"
        assert p.seed is None

    def test_invalid_text_normalization(self):
        with pytest.raises(ValidationError):
            TTSWebSocketParams(apply_text_normalization="wrong")


# ── VoiceSettingsEdit ─────────────────────────────────────────────────────────

class TestVoiceSettingsEdit:
    def test_defaults(self):
        s = VoiceSettingsEdit()
        assert s.stability == 0.5
        assert s.similarity_boost == 0.75
        assert s.style == 0.0
        assert s.use_speaker_boost is True
        assert s.speed == 1.0

    def test_stability_out_of_range_high(self):
        with pytest.raises(ValidationError):
            VoiceSettingsEdit(stability=1.5)

    def test_stability_out_of_range_low(self):
        with pytest.raises(ValidationError):
            VoiceSettingsEdit(stability=-0.1)

    def test_speed_out_of_range_high(self):
        with pytest.raises(ValidationError):
            VoiceSettingsEdit(speed=1.3)

    def test_speed_out_of_range_low(self):
        with pytest.raises(ValidationError):
            VoiceSettingsEdit(speed=0.6)

    def test_speed_boundary_values(self):
        s_low  = VoiceSettingsEdit(speed=0.7)
        s_high = VoiceSettingsEdit(speed=1.2)
        assert s_low.speed == 0.7
        assert s_high.speed == 1.2


# ── HistoryDownloadRequest ────────────────────────────────────────────────────

class TestHistoryDownloadRequest:
    def test_valid(self):
        r = HistoryDownloadRequest(history_item_ids=["id-1", "id-2"])
        assert len(r.history_item_ids) == 2

    def test_empty_list_rejected(self):
        with pytest.raises(ValidationError):
            HistoryDownloadRequest(history_item_ids=[])


# ── PronunciationRuleAlias ────────────────────────────────────────────────────

class TestPronunciationRuleAlias:
    def test_valid(self):
        rule = PronunciationRuleAlias(string_to_replace="GPT", alias="G P T")
        assert rule.type == "alias"
        assert rule.string_to_replace == "GPT"
        assert rule.alias == "G P T"

    def test_type_literal(self):
        """type phải là 'alias'."""
        with pytest.raises(ValidationError):
            PronunciationRuleAlias(type="phoneme", string_to_replace="x", alias="y")


# ── PronunciationRulePhoneme ──────────────────────────────────────────────────

class TestPronunciationRulePhoneme:
    def test_valid_ipa(self):
        rule = PronunciationRulePhoneme(
            string_to_replace="hello", phoneme="həˈloʊ", alphabet="ipa"
        )
        assert rule.type == "phoneme"
        assert rule.alphabet == "ipa"

    def test_default_alphabet_ipa(self):
        rule = PronunciationRulePhoneme(string_to_replace="x", phoneme="x")
        assert rule.alphabet == "ipa"

    def test_cmu_alphabet(self):
        rule = PronunciationRulePhoneme(
            string_to_replace="hello", phoneme="HH AH L OW", alphabet="cmu-arpabet"
        )
        assert rule.alphabet == "cmu-arpabet"

    def test_invalid_alphabet(self):
        with pytest.raises(ValidationError):
            PronunciationRulePhoneme(
                string_to_replace="x", phoneme="x", alphabet="something-else"
            )


# ── CreateDictionaryRequest ───────────────────────────────────────────────────

class TestCreateDictionaryRequest:
    def test_valid_with_alias_rule(self):
        rule = PronunciationRuleAlias(string_to_replace="GPT", alias="G P T")
        req = CreateDictionaryRequest(name="my-dict", rules=[rule])
        assert req.name == "my-dict"
        assert len(req.rules) == 1

    def test_valid_with_mixed_rules(self):
        alias  = PronunciationRuleAlias(string_to_replace="A", alias="B")
        phoneme = PronunciationRulePhoneme(string_to_replace="hello", phoneme="həˈloʊ")
        req = CreateDictionaryRequest(name="mixed", rules=[alias, phoneme])
        assert len(req.rules) == 2

    def test_optional_fields_none_by_default(self):
        req = CreateDictionaryRequest(name="d", rules=[])
        assert req.description is None
        assert req.workspace_access is None

    def test_invalid_workspace_access(self):
        with pytest.raises(ValidationError):
            CreateDictionaryRequest(name="d", rules=[], workspace_access="viewer")


# ── AddRulesRequest ───────────────────────────────────────────────────────────

class TestAddRulesRequest:
    def test_valid(self):
        rule = PronunciationRuleAlias(string_to_replace="x", alias="y")
        req = AddRulesRequest(rules=[rule])
        assert len(req.rules) == 1

    def test_empty_rules_rejected(self):
        with pytest.raises(ValidationError):
            AddRulesRequest(rules=[])


# ── RemoveRulesRequest ────────────────────────────────────────────────────────

class TestRemoveRulesRequest:
    def test_valid(self):
        req = RemoveRulesRequest(rule_strings=["word1", "word2"])
        assert len(req.rule_strings) == 2

    def test_empty_list_rejected(self):
        with pytest.raises(ValidationError):
            RemoveRulesRequest(rule_strings=[])
