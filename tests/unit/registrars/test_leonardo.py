"""
registrars/test_leonardo.py — Tests cho src/services/leonardo_ai/registrar.py

Bao phủ:
  - _random_full_name (pure)
  - _is_dashboard (pure)
  - _extract_verification_code (pure)
"""
from __future__ import annotations


# ── _random_full_name ─────────────────────────────────────────────────────────

class TestRandomFullName:
    def _call(self):
        from src.services.leonardo_ai.registrar import _random_full_name
        return _random_full_name()

    def test_returns_string(self):
        assert isinstance(self._call(), str)

    def test_contains_space(self):
        assert " " in self._call()

    def test_has_first_and_last_name(self):
        name = self._call()
        parts = name.split(" ")
        assert len(parts) == 2

    def test_not_empty(self):
        assert len(self._call()) > 3

    def test_randomness(self):
        # 10 lần, ít nhất 2 kết quả khác nhau
        results = {self._call() for _ in range(10)}
        assert len(results) >= 2


# ── _is_dashboard ─────────────────────────────────────────────────────────────

class TestIsDashboard:
    def _call(self, url, contains="app.leonardo.ai"):
        from src.services.leonardo_ai.registrar import _is_dashboard
        return _is_dashboard(url, contains)

    def test_dashboard_url(self):
        assert self._call("https://app.leonardo.ai/projects") is True

    def test_auth_page_not_dashboard(self):
        assert self._call("https://app.leonardo.ai/auth/login") is False

    def test_login_page_not_dashboard(self):
        assert self._call("https://app.leonardo.ai/login") is False

    def test_wrong_domain(self):
        assert self._call("https://example.com/projects") is False

    def test_empty_url(self):
        assert self._call("") is False

    def test_case_insensitive(self):
        assert self._call("https://APP.LEONARDO.AI/projects") is True

    def test_custom_contains_matching(self):
        assert self._call("https://app.leonardo.ai/dashboard", "leonardo") is True

    def test_custom_contains_not_matching(self):
        assert self._call("https://other-app.com/projects", "leonardo") is False


# ── _extract_verification_code ────────────────────────────────────────────────

class TestExtractVerificationCode:
    def _call(self, message):
        from src.services.leonardo_ai.registrar import _extract_verification_code
        return _extract_verification_code(message)

    def test_extracts_from_subject(self):
        msg = {"subject": "Your code is 123456", "intro": "", "body": ""}
        assert self._call(msg) == "123456"

    def test_extracts_from_intro(self):
        msg = {"subject": "Leonardo verification", "intro": "Enter code: 654321", "body": ""}
        assert self._call(msg) == "654321"

    def test_extracts_from_body(self):
        msg = {"subject": "", "intro": "", "body": "Use this code: 789012 to verify"}
        assert self._call(msg) == "789012"

    def test_subject_has_priority_over_intro(self):
        msg = {"subject": "Code 111111", "intro": "Code 222222", "body": ""}
        # subject checked first
        assert self._call(msg) == "111111"

    def test_no_code_returns_none(self):
        msg = {"subject": "Welcome to Leonardo", "intro": "No codes here", "body": ""}
        assert self._call(msg) is None

    def test_empty_dict_returns_none(self):
        assert self._call({}) is None

    def test_7_digit_code_extracted(self):
        msg = {"subject": "Code 1234567", "intro": "", "body": ""}
        assert self._call(msg) == "1234567"

    def test_8_digit_code_extracted(self):
        msg = {"subject": "Code 12345678", "intro": "", "body": ""}
        assert self._call(msg) == "12345678"

    def test_short_5_digit_not_extracted(self):
        msg = {"subject": "Code 12345", "intro": "", "body": ""}
        assert self._call(msg) is None

    def test_code_in_long_body_text(self):
        msg = {
            "subject": "Verify your Leonardo account",
            "intro": "Thank you for signing up.",
            "body": "Please use the following code to complete your registration: 987654\n\nThis code expires in 10 minutes.",
        }
        assert self._call(msg) == "987654"

    def test_missing_keys_handled(self):
        msg = {"body": "Code: 123456"}
        assert self._call(msg) == "123456"
