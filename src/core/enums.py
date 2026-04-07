"""
core/enums.py — Tất cả enum tập trung cho toàn bộ codebase.

Import từ đây để tham chiếu nhanh, tránh string literal rải rác.
Dùng StrEnum để giá trị enum là string — serializable, so sánh được với str.
"""
from __future__ import annotations

import enum


# ══════════════════════════════════════════════════════════════════════════════
# Google OAuth Page States
# ══════════════════════════════════════════════════════════════════════════════


class GooglePageState(enum.Enum):
    """Tất cả trạng thái trang Google mà OAuth flow phải handle."""
    LOGIN_EMAIL = "login_email"
    LOGIN_PASSWORD = "login_password"
    ACCOUNT_CHOOSER = "account_chooser"
    CONSENT = "consent"
    CHALLENGE_TOTP = "challenge_totp"
    CHALLENGE_SELECTION = "challenge_selection"
    CHALLENGE_PHONE = "challenge_phone"
    CHALLENGE_PHONE_OTP = "challenge_phone_otp"
    CHALLENGE_UNKNOWN = "challenge_unknown"
    AUTH_HANDLER = "auth_handler"
    DONE = "done"


# ══════════════════════════════════════════════════════════════════════════════
# Job Status — Registration & ImageLab jobs
# ══════════════════════════════════════════════════════════════════════════════


class JobStatus(str, enum.Enum):
    """Trạng thái job — dùng chung cho registration, image lab, v.v."""
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    STOPPED = "stopped"
    CANCELLED = "cancelled"

    @property
    def is_terminal(self) -> bool:
        """True nếu job đã kết thúc (không thể chuyển tiếp)."""
        return self in (JobStatus.DONE, JobStatus.FAILED, JobStatus.STOPPED, JobStatus.CANCELLED)

    @property
    def is_active(self) -> bool:
        """True nếu job đang chạy hoặc chờ."""
        return self in (JobStatus.PENDING, JobStatus.RUNNING)


# ══════════════════════════════════════════════════════════════════════════════
# Check Status — Account/token validation result
# ══════════════════════════════════════════════════════════════════════════════


class CheckStatus(str, enum.Enum):
    """Kết quả kiểm tra tài khoản/token."""
    VALID = "valid"
    INVALID = "invalid"
    ERROR = "error"


# ══════════════════════════════════════════════════════════════════════════════
# API Error Codes
# ══════════════════════════════════════════════════════════════════════════════


class ErrorCode(str, enum.Enum):
    """Mã lỗi API — StrEnum để serialize trực tiếp vào JSON response."""
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    VALIDATION = "VALIDATION_ERROR"
    INTERNAL = "INTERNAL_ERROR"
    UNSUPPORTED = "UNSUPPORTED_SERVICE"
    ALREADY_RUNNING = "ALREADY_RUNNING"
    SESSION_EXPIRED = "SESSION_EXPIRED"
    NO_ACCOUNTS = "NO_ACCOUNTS"
    JOB_CANCELLED = "JOB_CANCELLED"
    TIMEOUT = "TIMEOUT"
