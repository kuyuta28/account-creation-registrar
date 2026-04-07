"""
router_pronunciation.py — Pronunciation Dictionaries CRUD (item 9).

Routes:
  GET    /api/pronunciation                              — list dicts
  GET    /api/pronunciation/{id}                         — get dict details
  POST   /api/pronunciation                              — create từ rules (JSON)
  POST   /api/pronunciation/upload                       — create từ PLS file
  POST   /api/pronunciation/{id}/{vid}/add-rules         — add rules (new version)
  POST   /api/pronunciation/{id}/{vid}/remove-rules      — remove rules (new version)
  DELETE /api/pronunciation/{id}/version/{vid}           — delete version
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile

from .errors import RateLimitError
from .key_pool import load_available_keys
from .pronunciation_client import (
    add_rules,
    create_dict,
    create_dict_pls,
    delete_dict,
    get_dict,
    list_dicts,
    remove_rules,
)
from .schemas import AddRulesRequest, CreateDictionaryRequest, RemoveRulesRequest

_log = logging.getLogger(__name__)

router = APIRouter(prefix="/pronunciation")


def _best_key():
    keys = load_available_keys()
    if not keys:
        raise HTTPException(503, detail="No ElevenLabs keys available")
    return keys[0]


def _handle_errors(exc: Exception) -> None:
    if isinstance(exc, RateLimitError):
        raise HTTPException(429, detail="Rate limited")
    raise HTTPException(502, detail=str(exc))


@router.get("")
async def list_dicts_endpoint(
    page_size: int = Query(default=100, ge=1, le=100),
    cursor: str | None = Query(default=None),
) -> dict:
    """List tất cả pronunciation dictionaries của account.

    Trả về: {"pronunciation_dictionaries": [...], "has_more": bool, "next_cursor": ...}
    """
    key = _best_key()
    try:
        return await list_dicts(key.api_key, page_size=page_size, cursor=cursor)
    except Exception as exc:  # noqa: BLE001 — HTTP boundary: always re-raises as HTTPException
        _handle_errors(exc)


@router.get("/{pronunciation_dictionary_id}")
async def get_dict_endpoint(pronunciation_dictionary_id: str) -> dict:
    """Lấy chi tiết 1 pronunciation dictionary."""
    key = _best_key()
    try:
        return await get_dict(key.api_key, pronunciation_dictionary_id)
    except Exception as exc:  # noqa: BLE001 — HTTP boundary: always re-raises as HTTPException
        _handle_errors(exc)


@router.post("")
async def create_dict_endpoint(req: CreateDictionaryRequest) -> dict:
    """Tạo pronunciation dictionary từ rules (JSON).

    Rules hỗ trợ 2 loại:
    - Alias: `{"type": "alias", "string_to_replace": "AI", "alias": "Artificial Intelligence"}`
    - Phoneme: `{"type": "phoneme", "string_to_replace": "tomato", "phoneme": "təˈmeɪtoʊ", "alphabet": "ipa"}`
    """
    key = _best_key()
    try:
        return await create_dict(
            api_key=key.api_key,
            name=req.name,
            rules=[r.model_dump() for r in req.rules],
            description=req.description,
            workspace_access=req.workspace_access,
        )
    except Exception as exc:  # noqa: BLE001 — HTTP boundary: always re-raises as HTTPException
        _handle_errors(exc)


@router.post("/upload")
async def create_dict_pls_endpoint(
    name: str = Form(...),
    file: UploadFile = File(..., description="PLS file (Pronunciation Lexicon Specification)"),
    description: str | None = Form(default=None),
    workspace_access: str | None = Form(default=None),
) -> dict:
    """Tạo pronunciation dictionary từ PLS file upload."""
    key = _best_key()
    pls_bytes = await file.read()
    try:
        return await create_dict_pls(
            api_key=key.api_key,
            name=name,
            pls_file_bytes=pls_bytes,
            pls_filename=file.filename or "dictionary.pls",
            description=description,
            workspace_access=workspace_access,
        )
    except Exception as exc:  # noqa: BLE001 — HTTP boundary: always re-raises as HTTPException
        _handle_errors(exc)


@router.post("/{pronunciation_dictionary_id}/{version_id}/add-rules")
async def add_rules_endpoint(
    pronunciation_dictionary_id: str,
    version_id: str,
    req: AddRulesRequest,
) -> dict:
    """Thêm rules vào dictionary, tạo version mới. Trả về version mới."""
    key = _best_key()
    try:
        return await add_rules(
            api_key=key.api_key,
            pronunciation_dictionary_id=pronunciation_dictionary_id,
            version_id=version_id,
            rules=[r.model_dump() for r in req.rules],
        )
    except Exception as exc:  # noqa: BLE001 — HTTP boundary: always re-raises as HTTPException
        _handle_errors(exc)


@router.post("/{pronunciation_dictionary_id}/{version_id}/remove-rules")
async def remove_rules_endpoint(
    pronunciation_dictionary_id: str,
    version_id: str,
    req: RemoveRulesRequest,
) -> dict:
    """Xóa rules theo string_to_replace, tạo version mới. Trả về version mới."""
    key = _best_key()
    try:
        return await remove_rules(
            api_key=key.api_key,
            pronunciation_dictionary_id=pronunciation_dictionary_id,
            version_id=version_id,
            rule_strings=req.rule_strings,
        )
    except Exception as exc:  # noqa: BLE001 — HTTP boundary: always re-raises as HTTPException
        _handle_errors(exc)


@router.delete("/{pronunciation_dictionary_id}/version/{version_id}")
async def delete_dict_endpoint(
    pronunciation_dictionary_id: str,
    version_id: str,
) -> dict:
    """Xóa 1 phiên bản của pronunciation dictionary."""
    key = _best_key()
    try:
        return await delete_dict(key.api_key, pronunciation_dictionary_id, version_id)
    except Exception as exc:  # noqa: BLE001 — HTTP boundary: always re-raises as HTTPException
        _handle_errors(exc)
