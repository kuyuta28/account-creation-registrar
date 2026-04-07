"""
unit/test_errors.py — Tests cho src/core/errors.py

Bao phủ: Exception hierarchy — tất cả custom exceptions kế thừa AppError,
và AppError kế thừa Exception.
"""
from __future__ import annotations

import pytest

from src.core.errors import (
    AppError,
    BrowserError,
    CaptchaError,
    ConfigError,
    DatabaseError,
    GoogleAuthError,
    MailError,
    RegistrationError,
)


_ALL_ERRORS = [
    RegistrationError,
    MailError,
    GoogleAuthError,
    CaptchaError,
    BrowserError,
    ConfigError,
    DatabaseError,
]


class TestErrorHierarchy:
    def test_app_error_is_exception(self):
        assert issubclass(AppError, Exception)

    @pytest.mark.parametrize("cls", _ALL_ERRORS)
    def test_subclass_of_app_error(self, cls: type):
        assert issubclass(cls, AppError)

    @pytest.mark.parametrize("cls", _ALL_ERRORS)
    def test_catchable_as_app_error(self, cls: type):
        with pytest.raises(AppError):
            raise cls("test message")

    @pytest.mark.parametrize("cls", _ALL_ERRORS)
    def test_message_preserved(self, cls: type):
        err = cls("specific message")
        assert str(err) == "specific message"

    def test_registration_error_not_catchable_as_mail_error(self):
        with pytest.raises(RegistrationError):
            raise RegistrationError("reg")
        # MailError handler should NOT catch RegistrationError
        try:
            raise RegistrationError("reg")
        except MailError:
            pytest.fail("RegistrationError should not be caught by MailError")
        except RegistrationError:
            pass
