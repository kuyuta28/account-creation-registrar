"""
unit/test_password.py — Tests cho src/core/password.py

Pure functions, không cần mock.
AAA pattern: Arrange → Act → Assert
"""
from __future__ import annotations

import string

import pytest

from src.core.password import generate_password, generate_username


class TestGeneratePassword:
    """generate_password() — random credential generation."""

    def test_default_length_14(self):
        assert len(generate_password()) == 14

    def test_custom_length(self):
        assert len(generate_password(20)) == 20

    def test_min_length_4(self):
        assert len(generate_password(4)) == 4

    def test_always_has_uppercase(self):
        for _ in range(50):
            assert any(c.isupper() for c in generate_password(14))

    def test_always_has_lowercase(self):
        for _ in range(50):
            assert any(c.islower() for c in generate_password(14))

    def test_always_has_digit(self):
        for _ in range(50):
            assert any(c.isdigit() for c in generate_password(14))

    def test_always_has_at_sign(self):
        for _ in range(50):
            assert "@" in generate_password(14)

    def test_unique_results(self):
        passwords = {generate_password(14) for _ in range(30)}
        assert len(passwords) > 5

    def test_uses_ascii_letters_and_digits(self):
        valid = set(string.ascii_letters + string.digits + "@")
        for _ in range(20):
            pw = generate_password(14)
            assert all(c in valid for c in pw), f"Invalid char in: {pw}"


class TestGenerateUsername:
    """generate_username() — lowercase alphanumeric random username."""

    def test_default_length_17(self):
        assert len(generate_username()) == 17

    def test_custom_length(self):
        assert len(generate_username(10)) == 10

    def test_starts_with_letter(self):
        for _ in range(50):
            assert generate_username(17)[0].isalpha()

    def test_all_lowercase(self):
        for _ in range(50):
            result = generate_username(17)
            assert result == result.lower()

    def test_only_alphanumeric(self):
        valid = set(string.ascii_lowercase + string.digits)
        for _ in range(30):
            assert all(c in valid for c in generate_username(17))

    def test_unique_results(self):
        usernames = {generate_username(17) for _ in range(30)}
        assert len(usernames) > 5
