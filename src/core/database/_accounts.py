"""
database/_accounts.py — Account CRUD operations.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from ._engine import _Account, _get_engine, _now, _to_dict, _record_to_values, _UPDATABLE
from ._services import _ensure_service_exists


def insert_account(db_path: Path, record) -> bool:
    """INSERT — bỏ qua nếu trùng (service, email). Trả True nếu thực sự insert."""
    values = _record_to_values(record)
    stmt = sqlite_insert(_Account).values(**values).prefix_with("OR IGNORE")
    with Session(_get_engine(db_path)) as s:
        _ensure_service_exists(s, values["service"])
        result = s.execute(stmt)
        s.commit()
        return result.rowcount > 0


def upsert_account(db_path: Path, record) -> None:
    """INSERT — nếu trùng (service, email) thì UPDATE các field thay đổi."""
    values = _record_to_values(record)
    stmt = (
        sqlite_insert(_Account)
        .values(**values)
        .on_conflict_do_update(
            index_elements=["service", "email"],
            set_={k: values[k] for k in _UPDATABLE if k in values},
        )
    )
    with Session(_get_engine(db_path)) as s:
        _ensure_service_exists(s, values["service"])
        s.execute(stmt)
        s.commit()


def get_accounts(
    db_path: Path,
    service: str | None = None,
    include_disabled: bool = True,
) -> list[dict[str, Any]]:
    stmt = select(_Account)
    if service is not None:
        stmt = stmt.where(_Account.service == service.upper())
    if not include_disabled:
        stmt = stmt.where(_Account.disabled.is_(False))
    stmt = stmt.order_by(_Account.id)
    with Session(_get_engine(db_path)) as s:
        rows = s.scalars(stmt).all()
    return [_to_dict(r) for r in rows]


def get_account_by_email(
    db_path: Path, service: str, email: str
) -> dict[str, Any] | None:
    stmt = select(_Account).where(
        _Account.service == service.upper(),
        _Account.email == email,
    )
    with Session(_get_engine(db_path)) as s:
        row = s.scalars(stmt).first()
    return _to_dict(row) if row else None


def update_account(db_path: Path, service: str, email: str, **fields) -> bool:
    safe = {k: v for k, v in fields.items() if k in _UPDATABLE}
    if not safe:
        return False
    safe.setdefault("updated_at", _now())
    stmt = (
        update(_Account)
        .where(_Account.service == service.upper(), _Account.email == email)
        .values(**safe)
    )
    with Session(_get_engine(db_path)) as s:
        result = s.execute(stmt)
        s.commit()
        return result.rowcount > 0


def delete_account(db_path: Path, service: str, email: str) -> bool:
    stmt = (
        delete(_Account)
        .where(_Account.service == service.upper(), _Account.email == email)
    )
    with Session(_get_engine(db_path)) as s:
        result = s.execute(stmt)
        s.commit()
        return result.rowcount > 0


def delete_accounts(db_path: Path, service: str, emails: set[str]) -> int:
    if not emails:
        return 0
    stmt = (
        delete(_Account)
        .where(_Account.service == service.upper(), _Account.email.in_(emails))
    )
    with Session(_get_engine(db_path)) as s:
        result = s.execute(stmt)
        s.commit()
        return result.rowcount


def delete_disabled_service_accounts(db_path: Path, service: str) -> int:
    """Xóa tất cả account disabled/invalid/error. service='ALL' → tất cả services."""
    disabled_cond = or_(
        _Account.disabled == True,  # noqa: E712
        _Account.check_status.in_(["invalid", "error"]),
    )
    if service.upper() == "ALL":
        stmt = delete(_Account).where(disabled_cond)
    else:
        stmt = delete(_Account).where(_Account.service == service.upper(), disabled_cond)
    with Session(_get_engine(db_path)) as s:
        result = s.execute(stmt)
        s.commit()
        return result.rowcount


def count_accounts(db_path: Path, service: str) -> int:
    stmt = select(func.count()).where(_Account.service == service.upper())
    with Session(_get_engine(db_path)) as s:
        return s.scalar(stmt) or 0


def get_used_gmail_variations(db_path: Path, source_email: str, service: str | None = None) -> list[dict]:
    canonical = source_email.lower().strip()
    with Session(_get_engine(db_path)) as s:
        stmt = select(_Account).where(
            or_(_Account.email == canonical, _Account.source_email == canonical)
        )
        if service:
            stmt = stmt.where(_Account.service == service.upper())
        rows = s.scalars(stmt).all()
    return [_to_dict(r) for r in rows]


def check_gmail_variations_availability(
    db_path: Path,
    variations: list[str],
    service: str,
) -> dict[str, bool]:
    svc = service.upper()
    lower_vars = [v.lower() for v in variations]
    with Session(_get_engine(db_path)) as s:
        existing = set(s.scalars(
            select(_Account.email).where(
                _Account.service == svc,
                _Account.email.in_(lower_vars),
            )
        ).all())
    return {v: v not in existing for v in lower_vars}


def bulk_insert(db_path: Path, records: list) -> int:
    if not records:
        return 0
    inserted = 0
    with Session(_get_engine(db_path)) as s:
        for record in records:
            result = s.execute(
                sqlite_insert(_Account)
                .values(**_record_to_values(record))
                .prefix_with("OR IGNORE")
            )
            inserted += result.rowcount
        s.commit()
    return inserted


def update_accounts_bulk(
    db_path: Path, service: str, updates: list[dict[str, Any]]
) -> int:
    total = 0
    with Session(_get_engine(db_path)) as s:
        for item in updates:
            email = item.get("email")
            if not email:
                continue
            safe = {k: v for k, v in item.items() if k in _UPDATABLE and k != "email"}
            if not safe:
                continue
            safe.setdefault("updated_at", _now())
            result = s.execute(
                update(_Account)
                .where(_Account.service == service.upper(), _Account.email == email)
                .values(**safe)
            )
            total += result.rowcount
        s.commit()
    return total
