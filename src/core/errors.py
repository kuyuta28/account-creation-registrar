"""
src/core/errors.py — App-wide exception hierarchy.

Nguyên tắc:
  - KHÔNG BAO GIỜ dùng `except Exception: pass/continue/return` mà không re-raise
  - Khi cần catch Exception broad → phải có lý do rõ ràng + `raise` hoặc `# noqa: BLE001`
  - Dùng các exception cụ thể ở đây thay vì Exception chung

3 lớp phòng thủ:
  1. Type system: catch đúng type → sai type sẽ propagate tự động
  2. guard.py: probe helpers cho Playwright locator loops
  3. ruff BLE001: lint rule block `except Exception` không có `raise`
"""
from __future__ import annotations


class AppError(Exception):
    """Base cho mọi lỗi app-level. Không catch raw Exception ngoài boundary."""


class RegistrationError(AppError):
    """Lỗi trong flow đăng ký account."""


class MailError(AppError):
    """Lỗi liên quan đến mailbox, email provider."""


class GoogleAuthError(AppError):
    """Lỗi trong Google OAuth / login flow."""


class CaptchaError(AppError):
    """Captcha solve thất bại."""


class BrowserError(AppError):
    """Playwright browser / page error."""


class ConfigError(AppError):
    """Lỗi config / thiếu setting."""


class DatabaseError(AppError):
    """Lỗi database layer."""
