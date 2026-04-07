"""
password.py — Pure functions for credential generation.
No side effects, no I/O, fully testable in isolation.
"""
from __future__ import annotations

import random
import string


def generate_password(length: int = 14) -> str:
    """
    Generate a password satisfying minimum requirements:
    at least 1 uppercase, 1 lowercase, 1 digit, 1 special char (@).
    """
    chars = string.ascii_letters + string.digits
    required = [
        random.choice(string.ascii_uppercase),
        random.choice(string.ascii_lowercase),
        random.choice(string.digits),
        "@",
    ]
    rest = [random.choice(chars) for _ in range(length - len(required))]
    pool = required + rest
    random.shuffle(pool)
    return "".join(pool)


def generate_username(length: int = 17) -> str:
    """Generate a random lowercase alphanumeric username starting with a letter."""
    first = random.choice(string.ascii_lowercase)
    rest = "".join(
        random.choice(string.ascii_lowercase + string.digits)
        for _ in range(length - 1)
    )
    return first + rest
