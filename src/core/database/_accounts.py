"""
database/_accounts.py — Account CRUD operations (CTI).
"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from ._engine import (
    _Account, _get_engine, _now, _to_dict,
    _base_values, _ext_values,
    _BASE_UPDATABLE, _EXT_UPDATABLE, _EXT_FIELD_ALIAS,
    _EXTENSION_MODELS,
)
from ._services import _ensure_service_exists


# ── Internal helpers ──────────────────────────────────────────────────────────

def _upsert_extension(s: Session, account_id: int, service: str, ext: dict) -> None:
    """Upsert extension row cho một account. Noop nếu service không có extension."""
    model = _EXTENSION_MODELS.get(service)
    if model is None or not ext:
        return
    s.execute(
        sqlite_insert(model)
        .values(account_id=account_id, **ext)
        .on_conflict_do_update(index_elements=["account_id"], set_=ext)
    )


def _load_with_extensions(s: Session, rows: list[_Account]) -> list[dict[str, Any]]:
    """Batch-load extension rows cho danh sách accounts, trả về flat dicts."""
    if not rows:
        return []
    by_service: dict[str, list[_Account]] = defaultdict(list)
    for r in rows:
        by_service[r.service].append(r)

    ext_by_id: dict[int, Any] = {}
    for svc, svc_rows in by_service.items():
        model = _EXTENSION_MODELS.get(svc)
        if model is None:
            continue
        ids = [r.id for r in svc_rows]
        for ext in s.scalars(select(model).where(model.account_id.in_(ids))).all():
            ext_by_id[ext.account_id] = ext

    return [_to_dict(r, ext_by_id.get(r.id)) for r in rows]


def _resolve_ext_fields(service: str, fields: dict) -> tuple[dict, dict]:
    """Tách fields thành (base_fields, ext_fields), translate alias (account_id → org_slug v.v.)."""
    svc = service.upper()
    ext_updatable = _EXT_UPDATABLE.get(svc, frozenset())
    alias = _EXT_FIELD_ALIAS.get(svc, {})

    base: dict = {}
    ext: dict = {}
    for k, v in fields.items():
        if k in _BASE_UPDATABLE:
            base[k] = v
        elif k in ext_updatable:
            actual_key = alias.get(k, k)
            ext[actual_key] = v
    return base, ext


# ── Public CRUD ───────────────────────────────────────────────────────────────

def insert_account(db_path: Path, record) -> bool:
    """INSERT — bỏ qua nếu trùng (service, email). Trả True nếu thực sự insert."""
    base = _base_values(record)
    ext  = _ext_values(record)
    with Session(_get_engine(db_path)) as s:
        _ensure_service_exists(s, base["service"])
        result = s.execute(
            sqlite_insert(_Account).values(**base).prefix_with("OR IGNORE")
        )
        s.flush()
        if result.rowcount == 0:
            s.commit()
            return False
        row = s.scalars(
            select(_Account).where(
                _Account.service == base["service"],
                _Account.email   == base["email"],
            )
        ).first()
        if row and ext is not None:
            _upsert_extension(s, row.id, row.service, ext)
        s.commit()
        return True


def upsert_account(db_path: Path, record) -> None:
    """INSERT — nếu trùng (service, email) thì UPDATE base fields. Luôn upsert extension."""
    base = _base_values(record)
    ext  = _ext_values(record)
    base_updatable = {k: base[k] for k in _BASE_UPDATABLE if k in base}
    with Session(_get_engine(db_path)) as s:
        _ensure_service_exists(s, base["service"])
        s.execute(
            sqlite_insert(_Account)
            .values(**base)
            .on_conflict_do_update(
                index_elements=["service", "email"],
                set_=base_updatable,
            )
        )
        s.flush()
        row = s.scalars(
            select(_Account).where(
                _Account.service == base["service"],
                _Account.email   == base["email"],
            )
        ).first()
        if row and ext is not None:
            _upsert_extension(s, row.id, row.service, ext)
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
        return _load_with_extensions(s, rows)


def get_account_by_email(
    db_path: Path, service: str, email: str
) -> dict[str, Any] | None:
    with Session(_get_engine(db_path)) as s:
        row = s.scalars(
            select(_Account).where(
                _Account.service == service.upper(),
                _Account.email   == email,
            )
        ).first()
        if row is None:
            return None
        results = _load_with_extensions(s, [row])
        return results[0] if results else None


def update_account(db_path: Path, service: str, email: str, **fields) -> bool:
    base_fields, ext_fields = _resolve_ext_fields(service, fields)
    if not base_fields and not ext_fields:
        return False
    base_fields.setdefault("updated_at", _now())
    svc = service.upper()
    with Session(_get_engine(db_path)) as s:
        updated = False
        if base_fields:
            result = s.execute(
                update(_Account)
                .where(_Account.service == svc, _Account.email == email)
                .values(**base_fields)
            )
            updated = result.rowcount > 0
        if ext_fields:
            row = s.scalars(
                select(_Account).where(_Account.service == svc, _Account.email == email)
            ).first()
            if row:
                _upsert_extension(s, row.id, svc, ext_fields)
                updated = True
        s.commit()
    return updated


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
        return _load_with_extensions(s, rows)


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
            base = _base_values(record)
            ext  = _ext_values(record)
            result = s.execute(
                sqlite_insert(_Account).values(**base).prefix_with("OR IGNORE")
            )
            if result.rowcount > 0:
                row = s.scalars(
                    select(_Account).where(
                        _Account.service == base["service"],
                        _Account.email   == base["email"],
                    )
                ).first()
                if row and ext is not None:
                    _upsert_extension(s, row.id, row.service, ext)
                inserted += 1
        s.commit()
    return inserted


def update_accounts_bulk(
    db_path: Path, service: str, updates: list[dict[str, Any]]
) -> int:
    svc = service.upper()
    total = 0
    with Session(_get_engine(db_path)) as s:
        for item in updates:
            email = item.get("email")
            if not email:
                continue
            base_fields, ext_fields = _resolve_ext_fields(svc, {k: v for k, v in item.items() if k != "email"})
            if not base_fields and not ext_fields:
                continue
            base_fields.setdefault("updated_at", _now())
            if base_fields:
                result = s.execute(
                    update(_Account)
                    .where(_Account.service == svc, _Account.email == email)
                    .values(**base_fields)
                )
                total += result.rowcount
            if ext_fields:
                row = s.scalars(
                    select(_Account).where(_Account.service == svc, _Account.email == email)
                ).first()
                if row:
                    _upsert_extension(s, row.id, svc, ext_fields)
                    total += 1
        s.commit()
    return total
