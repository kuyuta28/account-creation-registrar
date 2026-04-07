"""
database/_services.py — Service catalog CRUD + _ensure_service_exists helper.
"""
from __future__ import annotations

from pathlib import Path

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from ._engine import _Service, _get_engine


def _service_has_registrar(service: str) -> bool:
    from ...services.registry import SUPPORTED_SERVICES
    return service.upper() in set(SUPPORTED_SERVICES)


def _ensure_service_exists(session: Session, service: str) -> None:
    normalized = service.upper()
    session.execute(
        sqlite_insert(_Service)
        .values(name=normalized, has_registrar=_service_has_registrar(normalized))
        .on_conflict_do_nothing(index_elements=["name"])
    )


def get_distinct_services(db_path: Path) -> list[str]:
    with Session(_get_engine(db_path)) as s:
        rows = s.execute(
            select(_Service.name).order_by(_Service.name)
        ).scalars().all()
    return list(rows)


def service_exists(db_path: Path, service: str) -> bool:
    with Session(_get_engine(db_path)) as s:
        row = s.scalar(select(_Service.name).where(_Service.name == service.upper()).limit(1))
    return row is not None


def add_service(db_path: Path, name: str, has_registrar: bool = False) -> bool:
    """Thêm service mới. Trả True nếu tạo mới, False nếu đã tồn tại."""
    with Session(_get_engine(db_path)) as s:
        existing = s.scalar(select(_Service.name).where(_Service.name == name.upper()).limit(1))
        if existing:
            return False
        s.add(_Service(name=name.upper(), has_registrar=has_registrar))
        s.commit()
    return True


def delete_service(db_path: Path, name: str) -> bool:
    """Xóa service. Trả True nếu xóa được, False nếu không tìm thấy."""
    with Session(_get_engine(db_path)) as s:
        row = s.scalar(select(_Service).where(_Service.name == name.upper()).limit(1))
        if not row:
            return False
        s.delete(row)
        s.commit()
    return True
