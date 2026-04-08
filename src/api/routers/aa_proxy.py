"""
aa_proxy.py — Router proxy AA (Artificial Analysis) API qua session cookie.

Endpoints:
  GET  /aa/session              – check session + balance từ AA
  GET  /aa/models               – danh sách image models (local cache)
  GET  /aa/generations          – lịch sử generations của account
  POST /aa/generate             – tạo generation mới (proxy đến AA API)
  GET  /aa/generation/{gen_id}  – poll status + result
"""
from __future__ import annotations

import asyncio
import io
import json
import re
from pathlib import Path
from typing import Any

import httpx
from PIL import Image
from fastapi import APIRouter
from fastapi.responses import Response
from pydantic import BaseModel, Field

from ..exceptions import AppError
from ..schemas import ErrorCode, ok
from ..services.account_service import list_accounts

router = APIRouter(prefix="/aa", tags=["aa-proxy"])

_AA_BASE = "https://artificialanalysis.ai"


def _models_file() -> Path:
    """Lấy path aa_models.json từ config — không hardcode."""
    from ...config.settings import load_config
    return load_config().base_dir / "data" / "aa_models.json"

_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Origin": "https://artificialanalysis.ai",
    "Referer": "https://artificialanalysis.ai/image/image-lab",
}


def _get_session_cookie(session_state: str) -> str:
    """Extract __Secure-better-auth.session_token từ session_state JSON."""
    data = json.loads(session_state)
    for c in data.get("cookies", []):
        if "__Secure-better-auth" in c["name"]:
            return c["value"]
    raise AppError(ErrorCode.SESSION_EXPIRED, "Không tìm thấy session cookie trong session_state", 401)


def _build_cookies(session_state: str) -> dict:
    data = json.loads(session_state)
    return {c["name"]: c["value"] for c in data.get("cookies", [])}


async def _aa_get(path: str, cookies: dict) -> Any:
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{_AA_BASE}{path}",
            cookies=cookies,
            headers=_HEADERS,
            timeout=30,
        )
    if r.status_code == 401:
        raise AppError(ErrorCode.SESSION_EXPIRED, "Session AA hết hạn hoặc không hợp lệ", 401)
    if r.status_code != 200:
        raise AppError(ErrorCode.INTERNAL, f"AA API error {r.status_code}: {r.text[:200]}", 502)
    return r.json()


async def _aa_post(path: str, cookies: dict, body: dict) -> Any:
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{_AA_BASE}{path}",
            cookies=cookies,
            headers=_HEADERS,
            json=body,
            timeout=60,
        )
    if r.status_code == 401:
        raise AppError(ErrorCode.SESSION_EXPIRED, "Session AA hết hạn hoặc không hợp lệ", 401)
    if r.status_code not in (200, 201):
        raise AppError(ErrorCode.INTERNAL, f"AA API error {r.status_code}: {r.text[:300]}", 502)
    return r.json()


def _load_models() -> dict:
    f = _models_file()
    if not f.exists():
        raise AppError(ErrorCode.INTERNAL, "aa_models.json chưa được tạo — chạy scripts/aa_save_models.py", 500)
    return json.loads(f.read_text(encoding="utf-8"))


# ── Schemas ───────────────────────────────────────────────────────────────────

class GenerateBody(BaseModel):
    model_config = {"protected_namespaces": ()}

    email: str = Field(..., description="Email tài khoản AA cần dùng")
    prompt: str = Field(..., min_length=1, max_length=300)
    model_ids: list[str] = Field(..., min_items=1, description="List hostModelId UUIDs")
    generations_per_model: int = Field(default=1, ge=1, le=4)
    width: int = Field(default=1024)
    height: int = Field(default=1024)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/session")
async def get_aa_session(email: str):
    """Kiểm tra session AA và lấy thông tin org/balance."""
    accounts = await list_accounts("ARTIFICIALANALYSIS")
    account = next((a for a in accounts if a.get("email") == email), None)
    if not account:
        raise AppError(ErrorCode.NOT_FOUND, f"Không tìm thấy account {email}", 404)
    if not account.get("session_state"):
        raise AppError(ErrorCode.SESSION_EXPIRED, f"Account {email} chưa có session_state", 401)

    cookies = _build_cookies(account["session_state"])

    session, org = await asyncio.gather(
        _aa_get("/api/auth/get-session", cookies),
        _aa_get("/api/auth/organization/get-full-organization", cookies),
    )

    return ok({
        "email": email,
        "session": session.get("session", {}),
        "user": session.get("user", {}),
        "org": {
            "name": org.get("name"),
            "balance": org.get("balance"),
            "id": org.get("id"),
        },
    })


@router.get("/models")
async def get_aa_models(mode: str | None = "text_to_image"):
    """Danh sách image models từ local cache.
    mode: text_to_image | image_editing | all
    """
    data = _load_models()
    if mode not in ("text_to_image", "image_editing", "all"):
        raise AppError(ErrorCode.VALIDATION, "mode phải là: text_to_image | image_editing | all", 400)
    result = data.get(mode)
    if result is None:
        raise AppError(ErrorCode.NOT_FOUND, f"Không có dữ liệu models cho mode '{mode}'", 404)
    return ok(result)


@router.get("/generations")
async def get_generations(email: str, limit: int = 20, cursor: str | None = None):
    """Lịch sử generations của account."""
    accounts = await list_accounts("ARTIFICIALANALYSIS")
    account = next((a for a in accounts if a.get("email") == email), None)
    if not account:
        raise AppError(ErrorCode.NOT_FOUND, f"Không tìm thấy account {email}", 404)
    if not account.get("session_state"):
        raise AppError(ErrorCode.SESSION_EXPIRED, f"Account {email} chưa có session_state", 401)

    cookies = _build_cookies(account["session_state"])
    path = f"/api/playground/generations?limit={limit}"
    if cursor:
        path += f"&cursor={cursor}"

    result = await _aa_get(path, cookies)
    return ok(result)


@router.post("/generate")
async def generate_images(body: GenerateBody):
    """Tạo generation mới qua AA API."""
    accounts = await list_accounts("ARTIFICIALANALYSIS")
    account = next((a for a in accounts if a.get("email") == body.email), None)
    if not account:
        raise AppError(ErrorCode.NOT_FOUND, f"Không tìm thấy account {body.email}", 404)
    if not account.get("session_state"):
        raise AppError(ErrorCode.SESSION_EXPIRED, f"Account {body.email} chưa có session_state", 401)

    cookies = _build_cookies(account["session_state"])

    payload = {
        "hostModelIds": body.model_ids,
        "prompt": body.prompt,
        "generationsPerModel": body.generations_per_model,
        "dimensions": {
            "width": body.width,
            "height": body.height,
        },
    }

    result = await _aa_post("/api/playground/generations", cookies, payload)
    return ok(result)


@router.get("/image-proxy")
async def image_proxy(url: str):
    """Proxy + convert ảnh từ CDN sang PNG để download (fallback)."""
    async with httpx.AsyncClient() as client:
        r = await client.get(url, timeout=30, follow_redirects=True)
    if r.status_code != 200:
        raise AppError(ErrorCode.INTERNAL, f"Không thể tải file: {r.status_code}", 502)

    raw_content = r.content

    def _convert() -> tuple[bytes, str]:
        img = Image.open(io.BytesIO(raw_content)).convert("RGBA")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        orig_name = url.split("/")[-1].split("?")[0]
        stem = orig_name.rsplit(".", 1)[0] if "." in orig_name else orig_name
        return buf.getvalue(), f"{stem}.png"

    png_bytes, filename = await asyncio.to_thread(_convert)

    return Response(
        content=png_bytes,
        media_type="image/png",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


class DownloadBody(BaseModel):
    email: str
    image_id: str = Field(..., description="AAImage.id UUID")
    filename_hint: str = Field(default="image", description="Tên file gợi ý (không có extension)")


@router.post("/image-download")
async def image_download(body: DownloadBody):
    """Gọi AA download API → lấy signed URL → fetch → convert PNG."""
    accounts = await list_accounts("ARTIFICIALANALYSIS")
    account = next((a for a in accounts if a.get("email") == body.email), None)
    if not account:
        raise AppError(ErrorCode.NOT_FOUND, f"Không tìm thấy account {body.email}", 404)
    if not account.get("session_state"):
        raise AppError(ErrorCode.SESSION_EXPIRED, f"Account {body.email} chưa có session_state", 401)

    cookies = _build_cookies(account["session_state"])

    # Lấy signed R2 URL từ AA API
    result = await _aa_post(
        "/api/playground/images/download",
        cookies,
        {"imageIds": [body.image_id]},
    )
    urls: dict[str, str] = result.get("urls", {})
    signed_url = urls.get(body.image_id)
    if not signed_url:
        raise AppError(ErrorCode.INTERNAL, f"AA không trả về URL cho image {body.image_id}", 500)

    # Fetch file từ R2 (không cần auth)
    async with httpx.AsyncClient() as client:
        r = await client.get(signed_url, timeout=60, follow_redirects=True)
    if r.status_code != 200:
        raise AppError(ErrorCode.INTERNAL, f"Không tải được file từ R2: {r.status_code}", 502)

    # Convert WebP → PNG trong thread pool (CPU-bound, không block event loop)
    raw_content = r.content
    def _convert() -> bytes:
        img = Image.open(io.BytesIO(raw_content)).convert("RGBA")
        out = io.BytesIO()
        img.save(out, format="PNG")
        return out.getvalue()

    png_bytes = await asyncio.to_thread(_convert)

    # Sanitize tên file: loại bỏ tất cả ký tự Windows không hợp lệ
    safe_name = re.sub(r'[\\/:*?"<>|]', "_", body.filename_hint).strip()
    filename = f"{safe_name}.png"

    return Response(
        content=png_bytes,
        media_type="image/png",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/generation/{gen_id}")
async def get_generation(gen_id: str, email: str):
    """Poll status + result của một generation."""
    accounts = await list_accounts("ARTIFICIALANALYSIS")
    account = next((a for a in accounts if a.get("email") == email), None)
    if not account:
        raise AppError(ErrorCode.NOT_FOUND, f"Không tìm thấy account {email}", 404)
    if not account.get("session_state"):
        raise AppError(ErrorCode.SESSION_EXPIRED, f"Account {email} chưa có session_state", 401)

    cookies = _build_cookies(account["session_state"])
    result = await _aa_get(f"/api/playground/generations/{gen_id}", cookies)
    return ok(result)


# ── Re-login ──────────────────────────────────────────────────────────────────

class ReloginBody(BaseModel):
    email: str


@router.post("/relogin")
async def relogin_account(body: ReloginBody):
    """Re-login tài khoản AA qua magic link — cập nhật session_state trong DB."""
    from ...config.settings import load_config
    from ...services.artificialanalysis_ai.registrar import relogin_artificialanalysis

    cfg = load_config()
    logs: list[str] = []
    await relogin_artificialanalysis(body.email, cfg, logs.append)
    return ok({"email": body.email, "logs": logs})
