"""
registrars/test_chatgpt.py — Tests cho src/services/chatgpt_com/page_actions.py

Bao phủ:
  - is_login_page (pure sync)
  - is_otp_page (pure sync)
  - _looks_like_about_you_text (pure sync)
  - fill_birthday (async, cần AsyncMock)
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch


# ── is_login_page ─────────────────────────────────────────────────────────────

class TestIsLoginPage:
    def _call(self, url, text):
        from src.services.chatgpt_com.page_actions import is_login_page
        return is_login_page(url, text)

    def test_valid_login_page_welcome_back(self):
        assert self._call("https://auth.openai.com/authorize", "Welcome back") is True

    def test_valid_login_page_sign_in(self):
        assert self._call("https://auth.openai.com/login", "Sign in to continue") is True

    def test_valid_login_page_log_in(self):
        assert self._call("https://auth.openai.com/u/login", "Log in to ChatGPT") is True

    def test_not_openai_domain(self):
        assert self._call("https://example.com/login", "Welcome back") is False

    def test_create_account_excluded(self):
        assert self._call("https://auth.openai.com/signup", "Welcome back Create your account") is False

    def test_case_insensitive_text_match(self):
        assert self._call("https://auth.openai.com/x", "WELCOME BACK") is True

    def test_empty_url(self):
        assert self._call("", "Sign in") is False

    def test_empty_text(self):
        assert self._call("https://auth.openai.com/login", "") is False

    def test_openai_domain_but_random_text(self):
        assert self._call("https://auth.openai.com/login", "Hello World") is False


# ── is_otp_page ───────────────────────────────────────────────────────────────

class TestIsOtpPage:
    def _call(self, text):
        from src.services.chatgpt_com.page_actions import is_otp_page
        return is_otp_page(text)

    def test_enter_the_code(self):       assert self._call("Enter the code we sent") is True
    def test_check_your_email(self):     assert self._call("Check your email") is True
    def test_verification_code(self):    assert self._call("Enter verification code") is True
    def test_we_sent_a_code(self):       assert self._call("We sent a code to your email") is True
    def test_confirm_your_email(self):   assert self._call("Confirm your email address") is True
    def test_verify_your_email(self):    assert self._call("Verify your email") is True
    def test_six_digit_keyword(self):    assert self._call("Enter your 6-digit code") is True
    def test_enter_code_simple(self):    assert self._call("Enter code below") is True
    def test_case_insensitive(self):     assert self._call("CHECK YOUR EMAIL please") is True
    def test_unrelated_text_false(self): assert self._call("Welcome to OpenAI") is False
    def test_empty_text_false(self):     assert self._call("") is False


# ── _looks_like_about_you_text ────────────────────────────────────────────────

class TestLooksLikeAboutYouText:
    def _call(self, text):
        from src.services.chatgpt_com.page_actions import _looks_like_about_you_text
        return _looks_like_about_you_text(text)

    def test_confirm_your_age(self):
        assert self._call("Please confirm your age to continue") is True

    def test_how_old_are_you(self):
        assert self._call("How old are you?") is True

    def test_use_date_of_birth(self):
        assert self._call("Use date of birth instead") is True

    def test_full_name_and_birthday(self):
        assert self._call("Full Name\nBirthday\n") is True

    def test_full_name_and_age_newline(self):
        assert self._call("Please enter your full name\nage\nbelow") is True

    def test_full_name_and_age_spaced(self):
        assert self._call("Enter your full name and age today") is True

    def test_unrelated_text_returns_false(self):
        assert self._call("Welcome to OpenAI, please log in") is False

    def test_empty_returns_false(self):
        assert self._call("") is False

    def test_case_insensitive(self):
        assert self._call("CONFIRM YOUR AGE") is True


# ── fill_birthday (async) ─────────────────────────────────────────────────────

class TestFillBirthday:
    def _make_page(self, has_date_input=False, has_selects=False):
        page = MagicMock()  # page.locator() is sync in Playwright

        # locator returned by page.locator(...)
        locator = MagicMock()
        locator.count = AsyncMock(return_value=1 if has_date_input else 0)
        locator.first = MagicMock()
        locator.first.is_visible = AsyncMock(return_value=has_date_input)
        locator.first.fill = AsyncMock()
        locator.first.select_option = AsyncMock()
        page.locator.return_value = locator
        page.keyboard = MagicMock()
        page.keyboard.press = AsyncMock()

        return page

    def test_calls_log_fn_with_birthday(self):
        from src.services.chatgpt_com.page_actions import fill_birthday
        page = self._make_page(has_date_input=False)
        log_fn = MagicMock()
        asyncio.run(fill_birthday(page, log_fn))
        # log_fn phải được gọi với birthday string
        calls = [str(c) for c in log_fn.call_args_list]
        assert any("Birthday" in c or "birthday" in c.lower() for c in calls)

    def test_fill_date_input_when_visible(self):
        from src.services.chatgpt_com.page_actions import fill_birthday
        page = self._make_page(has_date_input=True)
        log_fn = MagicMock()
        asyncio.run(fill_birthday(page, log_fn))
        # Gọi fill trên date input
        page.locator.return_value.first.fill.assert_called_once()

    def test_no_exception_when_no_inputs(self):
        from src.services.chatgpt_com.page_actions import fill_birthday
        page = self._make_page(has_date_input=False)
        log_fn = MagicMock()
        # Không raise exception
        asyncio.run(fill_birthday(page, log_fn))

    def test_is_coroutine(self):
        from src.services.chatgpt_com.page_actions import fill_birthday
        import inspect
        page = AsyncMock()
        coro = fill_birthday(page, MagicMock())
        assert inspect.iscoroutine(coro)
        coro.close()

    def test_birthday_year_in_valid_range(self):
        from src.services.chatgpt_com.page_actions import fill_birthday
        captured_msg = []
        page = self._make_page()
        asyncio.run(fill_birthday(page, captured_msg.append))
        # Tìm message có format như "Birthday: YYYY-MM-DD"
        birthday_msgs = [m for m in captured_msg if any(
            str(y) in m for y in range(1975, 1999)
        )]
        assert len(birthday_msgs) >= 1

    def test_birthday_not_future_date(self):
        from src.services.chatgpt_com.page_actions import fill_birthday
        from datetime import datetime
        captured_msg = []
        page = self._make_page()
        asyncio.run(fill_birthday(page, captured_msg.append))
        for msg in captured_msg:
            # Format: "→ Birthday: YYYY-MM-DD"
            import re
            m = re.search(r"(\d{4}-\d{2}-\d{2})", msg)
            if m:
                date = datetime.strptime(m.group(1), "%Y-%m-%d")
                assert date.year <= 1998
