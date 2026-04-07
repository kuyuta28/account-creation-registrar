"""
checkers/base.py — Shared types for all account checkers.

CheckResult is a plain dict extended per-service:
  - always present: "valid" (bool), "reason" (str, empty on success)
  - elevenlabs extras: tier, status, characters_used/limit/remaining, resets_on
  - chatgpt extras:    name, user_id, org_id, role, mfa_enabled, account_id, expired

AccountCheckerProtocol defines the interface (I - Interface Segregation) that
all checker strategy functions must satisfy. Callers depend on this abstraction,
not on concrete checker implementations (D - Dependency Inversion).
"""
from __future__ import annotations

from typing import Any
from typing import Protocol, runtime_checkable

CheckResult = dict[str, Any]


@runtime_checkable
class AccountCheckerProtocol(Protocol):
    """Interface cho checker strategy functions.
    Mỗi checker nhận (account_row, app_config, now_str) và trả về CheckResult.
    """
    async def __call__(
        self,
        account: dict[str, Any],
        cfg: Any,
        now: str,
    ) -> dict[str, Any]: ...
