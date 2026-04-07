"""
router_history.py — ElevenLabs History management (item 10).

Routes:
  GET    /api/history                        — list history items
  GET    /api/history/{id}                   — get 1 item
  DELETE /api/history/{id}                   — delete 1 item
  GET    /api/history/{id}/audio             — stream audio của 1 item
  POST   /api/history/download               — download nhiều items dưới dạng zip
"""
from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from .errors import RateLimitError
from .history_client import (
    delete_history_item,
    get_history_item,
    list_history,
    stream_history_audio,
    stream_history_download,
)
from .key_pool import load_available_keys
from .schemas import HistoryDownloadRequest

_log = logging.getLogger(__name__)

router = APIRouter(prefix="/history")


def _all_keys():
    keys = load_available_keys()
    if not keys:
        raise HTTPException(503, detail="No ElevenLabs keys available")
    return keys


def _handle_errors(exc: Exception) -> None:
    if isinstance(exc, RateLimitError):
        raise HTTPException(429, detail="Rate limited")
    raise HTTPException(502, detail=str(exc))


def _key_by_email(email: str):
    """Tìm KeyEntry theo email, raise 404 nếu không tìm thấy."""
    keys = _all_keys()
    found = next((k for k in keys if k.email == email), None)
    if not found:
        raise HTTPException(404, detail=f"Account {email!r} not found or disabled")
    return found


async def _find_key_for_item(history_item_id: str):
    """Tìm key sở hữu history_item_id bằng cách thử từng key song song."""
    keys = _all_keys()

    async def _try(key_entry):
        try:
            await get_history_item(key_entry.api_key, history_item_id)
            return key_entry
        except Exception:  # noqa: BLE001
            return None

    results = await asyncio.gather(*(_try(k) for k in keys))
    found = next((r for r in results if r is not None), None)
    if not found:
        raise HTTPException(404, detail=f"History item {history_item_id!r} not found in any account")
    return found


@router.get("")
async def list_history_endpoint(
    page_size: int = Query(default=20, ge=1, le=200),
    voice_id: str | None = Query(default=None),
    start_after_unix: int | None = Query(default=None, description="Cursor: chỉ lấy items có date_unix < giá trị này (timestamp của item cuối trang trước)"),
) -> dict:
    """List history items từ TẤT CẢ keys, merge và sort theo thời gian mới nhất.

    Pagination bằng cursor start_after_unix (date_unix của item cuối cùng đã hiển thị).
    Mỗi key fetch page_size*3 items để đảm bảo đủ sau khi filter và merge.
    Trả về: {"history": [...], "has_more": bool, "last_unix": int | null}
    Mỗi item có thêm field "_account_email" để biết thuộc key nào.
    """
    keys = _all_keys()
    # Fetch đủ buffer để sau filter cursor vẫn có đủ page_size items khi merge nhiều keys
    fetch_per_key = page_size * len(keys)

    async def _fetch(key_entry):
        try:
            result = await list_history(
                api_key=key_entry.api_key,
                page_size=fetch_per_key,
                voice_id=voice_id,
            )
            for item in result.get("history", []):
                item["_account_email"] = key_entry.email
            return result.get("history", [])
        except Exception:  # noqa: BLE001
            return []

    all_items_lists = await asyncio.gather(*(_fetch(k) for k in keys))
    merged = [item for sublist in all_items_lists for item in sublist]
    merged.sort(key=lambda x: x.get("date_unix", 0), reverse=True)

    if start_after_unix is not None:
        merged = [i for i in merged if i.get("date_unix", 0) < start_after_unix]

    has_more = len(merged) > page_size
    page = merged[:page_size]

    last_unix = page[-1]["date_unix"] if page else None
    return {"history": page, "has_more": has_more, "last_unix": last_unix}


@router.get("/{history_item_id}")
async def get_history_item_endpoint(history_item_id: str) -> dict:
    """Lấy metadata của 1 history item."""
    key = await _find_key_for_item(history_item_id)
    try:
        return await get_history_item(key.api_key, history_item_id)
    except Exception as exc:  # noqa: BLE001 — HTTP boundary: always re-raises as HTTPException
        _handle_errors(exc)


@router.delete("/{history_item_id}")
async def delete_history_item_endpoint(history_item_id: str) -> dict:
    """Xóa 1 history item."""
    key = await _find_key_for_item(history_item_id)
    try:
        return await delete_history_item(key.api_key, history_item_id)
    except Exception as exc:  # noqa: BLE001 — HTTP boundary: always re-raises as HTTPException
        _handle_errors(exc)


@router.get("/{history_item_id}/audio")
async def stream_history_audio_endpoint(
    history_item_id: str,
    account: str | None = Query(default=None, description="Email của account sở hữu item — skip probe nếu biết"),
) -> StreamingResponse:
    """Stream audio của 1 history item đã lưu."""
    key = _key_by_email(account) if account else await _find_key_for_item(history_item_id)
    try:
        client, resp = await stream_history_audio(key.api_key, history_item_id)
    except RateLimitError:
        raise HTTPException(429, detail="Rate limited")
    except Exception as exc:  # noqa: BLE001 — HTTP boundary: always re-raises as HTTPException
        raise HTTPException(502, detail=str(exc))

    async def _generate(c=client, r=resp):
        try:
            async for chunk in r.aiter_bytes(chunk_size=4096):
                yield chunk
        finally:
            await r.aclose()
            await c.aclose()

    content_type = resp.headers.get("content-type", "audio/mpeg")
    return StreamingResponse(_generate(), media_type=content_type)


@router.post("/download")
async def download_history_zip_endpoint(req: HistoryDownloadRequest) -> StreamingResponse:
    """Download nhiều history items cùng lúc dưới dạng .zip file.

    Body: {"history_item_ids": ["id1", "id2", ...]}
    """
    key = _best_key()
    try:
        client, resp = await stream_history_download(key.api_key, req.history_item_ids)
    except RateLimitError:
        raise HTTPException(429, detail="Rate limited")
    except Exception as exc:  # noqa: BLE001 — HTTP boundary: always re-raises as HTTPException
        raise HTTPException(502, detail=str(exc))

    async def _generate(c=client, r=resp):
        try:
            async for chunk in r.aiter_bytes(chunk_size=8192):
                yield chunk
        finally:
            await r.aclose()
            await c.aclose()

    return StreamingResponse(
        _generate(),
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=history.zip"},
    )
