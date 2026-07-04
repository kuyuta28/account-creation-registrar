"""
unit/test_enums.py — Tests cho common/enums.py

Bao phủ: GooglePageState, JobStatus, CheckStatus, ErrorCode.
Pure enum tests — chỉ kiểm tra values, properties, serialization.
"""
from __future__ import annotations

import pytest

from common.enums import CheckStatus, ErrorCode, GooglePageState, JobStatus


# ── GooglePageState ───────────────────────────────────────────────────────────


class TestGooglePageState:
    def test_all_states_exist(self):
        expected = {
            "LOGIN_EMAIL", "LOGIN_PASSWORD", "ACCOUNT_CHOOSER", "CONSENT",
            "CHALLENGE_TOTP", "CHALLENGE_SELECTION", "CHALLENGE_PHONE",
            "CHALLENGE_PHONE_OTP", "CHALLENGE_UNKNOWN", "AUTH_HANDLER", "DONE",
        }
        assert {s.name for s in GooglePageState} == expected

    def test_values_are_strings(self):
        for state in GooglePageState:
            assert isinstance(state.value, str)

    def test_unique_values(self):
        values = [s.value for s in GooglePageState]
        assert len(values) == len(set(values))


# ── JobStatus ─────────────────────────────────────────────────────────────────


class TestJobStatus:
    def test_is_terminal_for_done(self):
        assert JobStatus.DONE.is_terminal is True

    def test_is_terminal_for_failed(self):
        assert JobStatus.FAILED.is_terminal is True

    def test_is_terminal_for_stopped(self):
        assert JobStatus.STOPPED.is_terminal is True

    def test_is_terminal_for_cancelled(self):
        assert JobStatus.CANCELLED.is_terminal is True

    def test_is_terminal_false_for_pending(self):
        assert JobStatus.PENDING.is_terminal is False

    def test_is_terminal_false_for_running(self):
        assert JobStatus.RUNNING.is_terminal is False

    def test_is_active_for_pending(self):
        assert JobStatus.PENDING.is_active is True

    def test_is_active_for_running(self):
        assert JobStatus.RUNNING.is_active is True

    def test_is_active_false_for_done(self):
        assert JobStatus.DONE.is_active is False

    def test_is_active_false_for_failed(self):
        assert JobStatus.FAILED.is_active is False

    def test_str_equality(self):
        """JobStatus(str, Enum) — so sánh trực tiếp với string."""
        assert JobStatus.PENDING == "pending"
        assert JobStatus.DONE == "done"

    def test_is_terminal_and_is_active_are_mutually_exclusive(self):
        for status in JobStatus:
            assert status.is_terminal != status.is_active

    def test_json_serializable(self):
        import json
        assert json.dumps({"status": JobStatus.RUNNING}) == '{"status": "running"}'


# ── CheckStatus ───────────────────────────────────────────────────────────────


class TestCheckStatus:
    def test_all_statuses(self):
        assert {s.value for s in CheckStatus} == {"valid", "invalid", "error", "expired"}

    def test_str_equality(self):
        assert CheckStatus.VALID == "valid"
        assert CheckStatus.INVALID == "invalid"
        assert CheckStatus.ERROR == "error"


# ── ErrorCode ─────────────────────────────────────────────────────────────────


class TestErrorCode:
    def test_all_codes_are_uppercase(self):
        for code in ErrorCode:
            assert code.value == code.value.upper()

    def test_str_equality(self):
        assert ErrorCode.NOT_FOUND == "NOT_FOUND"
        assert ErrorCode.INTERNAL == "INTERNAL_ERROR"

    def test_contains_expected_codes(self):
        expected = {
            "NOT_FOUND", "CONFLICT", "VALIDATION_ERROR", "INTERNAL_ERROR",
            "UNSUPPORTED_SERVICE", "ALREADY_RUNNING", "SESSION_EXPIRED",
            "NO_ACCOUNTS", "JOB_CANCELLED", "TIMEOUT", "CONFIGURATION_ERROR",
        }
        assert {c.value for c in ErrorCode} == expected
