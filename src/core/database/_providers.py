"""
database/_providers.py — Mail provider + domain tag CRUD.
"""
from __future__ import annotations

import base64
import json as _json
from pathlib import Path
from typing import Any

from sqlalchemy import case, delete, exists, func, select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from ._engine import (
    _Account, _MailProvider, _MailboxServiceBlock, _ProviderDomainTag, _get_engine, _now,
    _to_provider_dict,
)


def upsert_mail_provider(
    db_path: Path,
    provider_type: str,
    api_key: str = "",
    server_id: str = "",
    label: str = "",
) -> int:
    """Insert hoặc update một mail provider. Trả về provider id."""
    now = _now()
    stmt = (
        sqlite_insert(_MailProvider)
        .values(
            provider_type=provider_type,
            api_key=api_key,
            server_id=server_id,
            label=label,
            disabled=False,
            fail_count=0,
            cooldown_until="",
            last_used="",
            created_at=now,
            updated_at=now,
        )
        .on_conflict_do_update(
            index_elements=["provider_type", "api_key", "server_id"],
            set_={"label": label, "updated_at": now, "disabled": False},
        )
    )
    with Session(_get_engine(db_path)) as s:
        s.execute(stmt)
        prov = s.scalars(
            select(_MailProvider).where(
                _MailProvider.provider_type == provider_type,
                _MailProvider.api_key == api_key,
                _MailProvider.server_id == server_id,
            )
        ).first()
        provider_id = prov.id  # type: ignore[union-attr]
        s.commit()
    return provider_id


def get_mail_providers(
    db_path: Path,
    service_tag: str | None = None,
) -> list[dict[str, Any]]:
    if not db_path.exists():
        return []
    svc_tag = service_tag.lower() if service_tag else None
    with Session(_get_engine(db_path)) as s:
        stmt = select(_MailProvider).where(_MailProvider.disabled.is_(False))
        if svc_tag:
            has_tag = exists().where(
                _ProviderDomainTag.provider_type == _MailProvider.provider_type,
                _ProviderDomainTag.tag == svc_tag,
            )
            stmt = stmt.where(has_tag)
        rows = s.scalars(stmt).all()
        result = [_to_provider_dict(r) for r in rows]

        gmail_tagged = (
            not svc_tag
            or (s.scalar(
                select(func.count()).where(
                    _ProviderDomainTag.provider_type == "gmail.com",
                    _ProviderDomainTag.tag == svc_tag,
                )
            ) or 0) > 0
        )
        if gmail_tagged:
            # Subquery: Gmail emails đã có account trong service đích
            # → loại ra khỏi danh sách provider để tránh đăng ký trùng
            already_used_in_service = (
                select(_Account.email)
                .where(_Account.service == svc_tag.upper())
                if svc_tag else None
            )
            stmt_gmail = (
                select(_Account)
                .where(_Account.service == "GMAIL")
                .where(_Account.disabled.is_(False))
                .order_by(_Account.email)
            )
            if already_used_in_service is not None:
                stmt_gmail = stmt_gmail.where(
                    _Account.email.not_in(already_used_in_service)
                )
            # Filter out service-blocked mailboxes
            if svc_tag:
                blocked_emails = (
                    select(_MailboxServiceBlock.email)
                    .where(_MailboxServiceBlock.service == svc_tag.upper())
                )
                stmt_gmail = stmt_gmail.where(
                    _Account.email.not_in(blocked_emails)
                )
            gmail_rows = s.scalars(stmt_gmail).all()
            result.extend({
                "id":             None,
                "provider_type":  "gmail.com",
                "api_key":        row.email,
                "server_id":      "",
                "connection_str": "gmail.com:{email}:{meta}".format(
                    email=row.email,
                    meta=base64.urlsafe_b64encode(
                        _json.dumps(
                            {"s": row.session_state, "p": row.password, "t": row.totp_secret},
                            separators=(",", ":"),
                        ).encode()
                    ).decode(),
                ),
                "label":          row.email,
                "disabled":       False,
                "fail_count":     0,
                "cooldown_until": "",
                "last_used":      "",
                "created_at":     row.created_at,
                "updated_at":     row.updated_at,
            } for row in gmail_rows)

    return result


def get_all_providers_with_tags(db_path: Path) -> list[dict[str, Any]]:
    if not db_path.exists():
        return []
    with Session(_get_engine(db_path)) as s:
        providers = s.scalars(select(_MailProvider)).all()
        if not providers:
            return []
        ptypes = {p.provider_type for p in providers}
        tag_rows = s.execute(
            select(_ProviderDomainTag.provider_type, _ProviderDomainTag.tag).where(
                _ProviderDomainTag.provider_type.in_(ptypes)
            )
        ).all()
        type_tags: dict[str, list[str]] = {pt: [] for pt in ptypes}
        for pt, tag in tag_rows:
            type_tags[pt].append(tag)
        result = []
        for p in providers:
            d = _to_provider_dict(p)
            d["tags"] = sorted(type_tags.get(p.provider_type, []))
            result.append(d)
    return result


def update_provider(db_path: Path, provider_id: int, **fields) -> bool:
    allowed = {"disabled", "label", "fail_count", "cooldown_until"}
    safe = {k: v for k, v in fields.items() if k in allowed}
    if not safe:
        return False
    safe["updated_at"] = _now()
    with Session(_get_engine(db_path)) as s:
        result = s.execute(
            update(_MailProvider).where(_MailProvider.id == provider_id).values(**safe)
        )
        s.commit()
    return result.rowcount > 0


def get_provider_domains(db_path: Path) -> list[dict[str, Any]]:
    if not db_path.exists():
        return []
    with Session(_get_engine(db_path)) as s:
        counts = s.execute(
            select(
                _MailProvider.provider_type,
                func.count().label("total"),
                func.sum(case((_MailProvider.disabled == False, 1), else_=0)).label("active"),  # noqa: E712
            ).group_by(_MailProvider.provider_type)
        ).all()

        tag_rows = s.execute(
            select(_ProviderDomainTag.provider_type, _ProviderDomainTag.tag)
        ).all()
        type_tags: dict[str, list[str]] = {}
        for pt, tag in tag_rows:
            type_tags.setdefault(pt, []).append(tag)

        result = [
            {
                "domain": row.provider_type,
                "tags":   sorted(type_tags.get(row.provider_type, [])),
                "total":  row.total,
                "active": row.active or 0,
            }
            for row in sorted(counts, key=lambda r: r.provider_type)
        ]

        gmail_counts = s.execute(
            select(
                func.count().label("total"),
                func.sum(case((_Account.disabled == False, 1), else_=0)).label("active"),  # noqa: E712
            ).where(_Account.service == "GMAIL")
        ).one()
        if gmail_counts.total:
            result.append({
                "domain": "gmail.com",
                "tags":   sorted(type_tags.get("gmail.com", [])),
                "total":  gmail_counts.total,
                "active": gmail_counts.active or 0,
            })
            result.sort(key=lambda r: r["domain"])

        return result


def set_provider_domain_tags(db_path: Path, provider_domain: str, tags: list[str]) -> int:
    clean = [t.strip().lower() for t in tags if t.strip()]
    with Session(_get_engine(db_path)) as s:
        s.execute(delete(_ProviderDomainTag).where(
            _ProviderDomainTag.provider_type == provider_domain
        ))
        for tag in clean:
            s.execute(
                sqlite_insert(_ProviderDomainTag)
                .values(provider_type=provider_domain, tag=tag)
                .on_conflict_do_nothing()
            )
        s.commit()
    return len(clean)


def cycle_provider_tag(db_path: Path, provider_domain: str, service: str) -> list[str]:
    """Cycle tri-state: (empty) → active → blocked → (empty)."""
    with Session(_get_engine(db_path)) as s:
        current_tags = list(s.scalars(
            select(_ProviderDomainTag.tag).where(
                _ProviderDomainTag.provider_type == provider_domain
            )
        ).all())

        active_key  = service.strip().lower()
        blocked_key = f"{active_key}:blocked"

        if active_key in current_tags:
            s.execute(delete(_ProviderDomainTag).where(
                _ProviderDomainTag.provider_type == provider_domain,
                _ProviderDomainTag.tag == active_key,
            ))
            s.execute(
                sqlite_insert(_ProviderDomainTag)
                .values(provider_type=provider_domain, tag=blocked_key)
                .on_conflict_do_nothing()
            )
            next_tags = [t for t in current_tags if t != active_key] + [blocked_key]
        elif blocked_key in current_tags:
            s.execute(delete(_ProviderDomainTag).where(
                _ProviderDomainTag.provider_type == provider_domain,
                _ProviderDomainTag.tag == blocked_key,
            ))
            next_tags = [t for t in current_tags if t != blocked_key]
        else:
            s.execute(
                sqlite_insert(_ProviderDomainTag)
                .values(provider_type=provider_domain, tag=active_key)
                .on_conflict_do_nothing()
            )
            next_tags = [*current_tags, active_key]

        s.commit()
    return sorted(next_tags)
