"""
unit/test_gmail_variations.py — Tests cho src/core/gmail_variations.py

Bao phủ: _parse_gmail, generate_dot_variations, generate_plus_variations,
generate_variations, normalize_gmail.
"""
from __future__ import annotations

import pytest

from src.core.gmail_variations import (
    GmailVariation,
    _parse_gmail,
    generate_dot_variations,
    generate_plus_variations,
    generate_variations,
    normalize_gmail,
)


# ── _parse_gmail ──────────────────────────────────────────────────────────────


class TestParseGmail:
    def test_basic_gmail(self):
        assert _parse_gmail("abc@gmail.com") == ("abc", "gmail.com")

    def test_strips_dots(self):
        assert _parse_gmail("a.b.c@gmail.com") == ("abc", "gmail.com")

    def test_strips_plus_tag(self):
        assert _parse_gmail("abc+tag@gmail.com") == ("abc", "gmail.com")

    def test_strips_dots_and_tag(self):
        assert _parse_gmail("a.b.c+test@gmail.com") == ("abc", "gmail.com")

    def test_googlemail_domain(self):
        assert _parse_gmail("user@googlemail.com") == ("user", "gmail.com")

    def test_case_insensitive(self):
        assert _parse_gmail("ABC+Tag@Gmail.Com") == ("abc", "gmail.com")

    def test_non_gmail_returns_none(self):
        assert _parse_gmail("user@outlook.com") is None

    def test_empty_returns_none(self):
        assert _parse_gmail("") is None

    def test_invalid_format_returns_none(self):
        assert _parse_gmail("not-an-email") is None


# ── generate_dot_variations ───────────────────────────────────────────────────


class TestGenerateDotVariations:
    def test_single_char(self):
        assert generate_dot_variations("a") == ["a"]

    def test_two_chars(self):
        result = generate_dot_variations("ab")
        assert set(result) == {"ab", "a.b"}

    def test_three_chars(self):
        result = generate_dot_variations("abc")
        assert len(result) == 4  # 2^(3-1) = 4
        assert "abc" in result
        assert "a.b.c" in result

    def test_count_matches_exponential(self):
        """Với username <= max_len: 2^(n-1) biến thể."""
        for n in range(2, 8):
            username = "a" * n
            result = generate_dot_variations(username)
            assert len(result) == 2 ** (n - 1)

    def test_long_username_capped(self):
        """Username dài hơn max_len → chỉ trả sample."""
        result = generate_dot_variations("abcdefghijklmnop", max_username_len=10)
        assert len(result) == 3  # [original, mid-dot, full-dots]

    def test_no_leading_dot(self):
        for v in generate_dot_variations("abc"):
            assert not v.startswith(".")

    def test_no_trailing_dot(self):
        for v in generate_dot_variations("abc"):
            assert not v.endswith(".")

    def test_no_consecutive_dots(self):
        for v in generate_dot_variations("abcd"):
            assert ".." not in v


# ── generate_plus_variations ──────────────────────────────────────────────────


class TestGeneratePlusVariations:
    def test_basic_tags(self):
        result = generate_plus_variations("user", ["1", "2", "test"])
        assert result == ["user+1", "user+2", "user+test"]

    def test_empty_tags_skipped(self):
        result = generate_plus_variations("user", ["1", "", "2"])
        assert result == ["user+1", "user+2"]

    def test_empty_tag_list(self):
        assert generate_plus_variations("user", []) == []


# ── generate_variations ───────────────────────────────────────────────────────


class TestGenerateVariations:
    def test_non_gmail_raises(self):
        with pytest.raises(ValueError, match="Không phải"):
            generate_variations("user@outlook.com")

    def test_returns_gmail_variations(self):
        results = generate_variations("abc@gmail.com")
        assert len(results) > 0
        assert all(isinstance(r, GmailVariation) for r in results)

    def test_excludes_base_email(self):
        results = generate_variations("abc@gmail.com")
        emails = [r.email for r in results]
        assert "abc@gmail.com" not in emails

    def test_plus_variations_present(self):
        results = generate_variations("abc@gmail.com", use_plus=True, use_dot=False, use_googlemail=False)
        assert all(r.technique == "plus" for r in results)
        assert all("+" in r.email for r in results)

    def test_dot_variations_present(self):
        results = generate_variations("abc@gmail.com", use_plus=False, use_dot=True, use_googlemail=False)
        assert all(r.technique == "dot" for r in results)
        assert all("." in r.email.split("@")[0] for r in results)

    def test_googlemail_variations_present(self):
        results = generate_variations("abc@gmail.com", use_plus=False, use_dot=False, use_googlemail=True)
        assert all(r.email.endswith("@googlemail.com") for r in results)

    def test_custom_plus_tags(self):
        results = generate_variations(
            "abc@gmail.com",
            use_plus=True, use_dot=False, use_googlemail=False,
            plus_tags=["x", "y"],
        )
        emails = [r.email for r in results]
        assert "abc+x@gmail.com" in emails
        assert "abc+y@gmail.com" in emails
        assert len(results) == 2

    def test_all_disabled_returns_empty(self):
        results = generate_variations("abc@gmail.com", use_plus=False, use_dot=False, use_googlemail=False)
        assert results == []

    def test_handles_dotted_input(self):
        """Input có dot → parse về base rồi generate."""
        results = generate_variations("a.b.c@gmail.com", use_plus=False, use_dot=True, use_googlemail=False)
        assert len(results) > 0
        # Username gốc là "abc" (3 chars) → 4 dot variants - 1 (base) = 3
        assert len(results) == 3

    def test_handles_plus_tagged_input(self):
        results = generate_variations("abc+old@gmail.com", use_plus=True, use_dot=False, use_googlemail=False)
        assert len(results) > 0
        # Phải parse về "abc" trước khi generate


# ── normalize_gmail ───────────────────────────────────────────────────────────


class TestNormalizeGmail:
    def test_basic(self):
        assert normalize_gmail("abc@gmail.com") == "abc@gmail.com"

    def test_strips_dots(self):
        assert normalize_gmail("a.b.c@gmail.com") == "abc@gmail.com"

    def test_strips_plus_tag(self):
        assert normalize_gmail("abc+tag@gmail.com") == "abc@gmail.com"

    def test_googlemail_to_gmail(self):
        assert normalize_gmail("abc@googlemail.com") == "abc@gmail.com"

    def test_combined(self):
        assert normalize_gmail("a.b.c+test@googlemail.com") == "abc@gmail.com"

    def test_non_gmail_returns_lowered(self):
        assert normalize_gmail("User@Outlook.Com") == "user@outlook.com"

    def test_case_insensitive(self):
        assert normalize_gmail("ABC@Gmail.Com") == "abc@gmail.com"
