"""
services/errors.py — Error taxonomy cho registration services.

Phân loại lỗi rõ ràng để dispatcher/caller biết ngay cách xử lý:
  - Fatal: dừng job ngay, retry vô nghĩa (hết mailbox, config sai, ...)
  - Retryable: có thể retry với email/attempt khác (captcha, timeout, ...)
  - Permanent: lỗi cụ thể cho 1 account, skip nhưng job tiếp tục (email bị ban, ...)

Mở rộng: thêm subclass mới khi có loại lỗi mới — dispatcher tự handle đúng
vì nó check isinstance() theo hierarchy, không check string.
"""
from __future__ import annotations


class RegistrationError(Exception):
    """Base error cho tất cả lỗi registration."""


# ── Fatal: dừng job ngay lập tức, retry không có ý nghĩa ──────────────────────

class FatalRegistrationError(RegistrationError):
    """Lỗi không thể recover — dừng toàn bộ job."""


class NoMailboxAvailableError(FatalRegistrationError):
    """Không còn mailbox nào khả dụng cho service này."""


class InvalidConfigError(FatalRegistrationError):
    """Config sai hoặc thiếu — không thể chạy."""


class NoSessionError(FatalRegistrationError):
    """Không có Google session — cần refresh trước."""


# ── Retryable: có thể thử lại với attempt/email khác ──────────────────────────

class RetryableRegistrationError(RegistrationError):
    """Lỗi tạm thời — retry có thể thành công."""


class CaptchaError(RetryableRegistrationError):
    """Captcha/phone verify chặn."""


class PageTimeoutError(RetryableRegistrationError):
    """Page load/transition timeout."""


class OAuthError(RetryableRegistrationError):
    """Google OAuth flow failed (popup, redirect, ...)."""


class EmailVerificationError(RetryableRegistrationError):
    """Không nhận được email xác thực hoặc OTP."""


# ── Permanent: lỗi cụ thể cho 1 account, skip nhưng job tiếp tục ─────────────

class PermanentAccountError(RegistrationError):
    """Lỗi cố định cho account cụ thể — skip, không retry cùng email."""


class AccountAlreadyExistsError(PermanentAccountError):
    """Email đã đăng ký service này rồi."""


class AccountBannedError(PermanentAccountError):
    """Account bị ban/suspended."""
