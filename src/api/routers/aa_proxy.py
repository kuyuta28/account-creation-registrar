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


def _aa_cfg():
    """Lazily load AA config — tránh circular import."""
    from ...config.settings import load_config
    return load_config().artificialanalysis


def _models_file() -> Path:
    """Lấy path aa_models.json từ config — không hardcode."""
    from ...config.settings import load_config
    return load_config().base_dir / "data" / "aa_models.json"


def _build_headers() -> dict:
    cfg = _aa_cfg()
    return {
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "User-Agent": cfg.user_agent,
        "Origin": cfg.base_url,
        "Referer": cfg.image_lab_url,
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
    cfg = _aa_cfg()
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{cfg.base_url}{path}",
            cookies=cookies,
            headers=_build_headers(),
            timeout=cfg.check_timeout_sec * 2,
        )
    if r.status_code == 401:
        raise AppError(ErrorCode.SESSION_EXPIRED, "Session AA hết hạn hoặc không hợp lệ", 401)
    if r.status_code != 200:
        raise AppError(ErrorCode.INTERNAL, f"AA API error {r.status_code}: {r.text[:200]}", 502)
    return r.json()


async def _aa_post(path: str, cookies: dict, body: dict) -> Any:
    cfg = _aa_cfg()
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{cfg.base_url}{path}",
            cookies=cookies,
            headers=_build_headers(),
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


# In-memory cache: generationConfigId → list of image dicts
_generation_cache: dict[str, list[dict]] = {}


def _parse_sse_generations(sse_text: str) -> tuple[str, list[dict]]:
    """Parse SSE stream from AA /api/playground/generations.

    Returns (generationConfigId, images) where each image is:
    {"id": imageId, "status": "done", "generationIndex": int, "imageUrl": str}
    Raises RuntimeError if no done event found.
    """
    images: list[dict] = []
    config_id: str = ""

    for line in sse_text.splitlines():
        if not line.startswith("data: "):
            continue
        data_str = line[len("data: "):]
        try:
            event = json.loads(data_str)
        except json.JSONDecodeError:
            continue

        event_type = event.get("type")
        if event_type == "result":
            images.append({
                "id": event.get("imageId", ""),
                "status": "done",
                "generationIndex": event.get("generationIndex", len(images)),
                "imageUrl": event.get("imageUrl", ""),
            })
        elif event_type == "done":
            config_id = event.get("generationConfigId", "")
        elif event_type == "error":
            raise RuntimeError(f"AA generation error: {event.get('message', event)}")

    if not config_id:
        raise RuntimeError(f"No done event in AA SSE stream. Events: {sse_text[:300]}")

    return config_id, images


@router.post("/generate")
async def generate_images(body: GenerateBody):
    """Tạo generation mới qua AA API (SSE stream → parsed JSON)."""
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

    # AA returns text/event-stream — collect full SSE text then parse
    cfg = _aa_cfg()
    async with httpx.AsyncClient(follow_redirects=True) as client:
        r = await client.post(
            f"{cfg.base_url}/api/playground/generations",
            cookies=cookies,
            headers=_build_headers(),
            json=payload,
            timeout=120,
        )

    if r.status_code == 401:
        raise AppError(ErrorCode.SESSION_EXPIRED, "Session AA hết hạn hoặc không hợp lệ", 401)
    if r.status_code == 403:
        body_json = {}
        try:
            body_json = r.json()
        except (ValueError, KeyError):
            pass
        raise AppError(ErrorCode.INTERNAL, f"AA 403: {body_json.get('error', r.text[:200])}", 502)
    if r.status_code not in (200, 201):
        raise AppError(ErrorCode.INTERNAL, f"AA API error {r.status_code}: {r.text[:300]}", 502)

    gen_config_id, images = _parse_sse_generations(r.text)
    _generation_cache[gen_config_id] = images

    return ok({"generationId": gen_config_id})


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
    """Trả về images đã được parse từ cache sau khi /generate hoàn tất.

    AA API dùng SSE stream synchronous — images được parse và cache trong /generate.
    Endpoint này chỉ serve từ cache (không gọi lại AA).
    """
    if gen_id not in _generation_cache:
        raise AppError(ErrorCode.NOT_FOUND, f"Generation {gen_id} not found in cache", 404)
    return ok({"images": _generation_cache[gen_id]})


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


# ── Check sessions ────────────────────────────────────────────────────────────

_check_lock = asyncio.Lock()
_check_state: dict[str, Any] = {
    "running": False,
    "cancelled": False,
    "total": 0,
    "checked": 0,
    "valid": 0,
    "expired": 0,
    "errors": 0,
    "results": [],
}


@router.post("/check-sessions")
async def check_all_sessions():
    """Kiểm tra toàn bộ AA accounts xem session còn hạn không (chạy concurrent)."""
    from ..services.checker_service import check_and_persist

    async with _check_lock:
        if _check_state["running"]:
            return ok({**_check_state, "message": "already running"})

    accounts = await list_accounts("ARTIFICIALANALYSIS")
    total = len(accounts)
    if total == 0:
        raise AppError(ErrorCode.NOT_FOUND, "Không có account AA nào", 404)

    async with _check_lock:
        _check_state.update({"running": True, "cancelled": False, "total": total, "checked": 0,
                              "valid": 0, "expired": 0, "errors": 0, "results": []})

    sem = asyncio.Semaphore(15)

    async def _check_one(acc: dict) -> None:
        email = acc["email"]
        async with _check_lock:
            if _check_state["cancelled"]:
                return
        async with sem:
            async with _check_lock:
                if _check_state["cancelled"]:
                    return
            try:
                result = await check_and_persist("ARTIFICIALANALYSIS", email)
                cs = result.get("check_status", "error")
            except (RuntimeError, ValueError, KeyError) as exc:
                cs = "error"
                result = {"check_status": cs, "last_error": str(exc)[:200]}

        async with _check_lock:
            _check_state["checked"] += 1
            if cs == "valid":
                _check_state["valid"] += 1
            elif cs == "expired":
                _check_state["expired"] += 1
            else:
                _check_state["errors"] += 1
            _check_state["results"].append({
                "email": email,
                "check_status": cs,
                "last_error": result.get("last_error", ""),
            })

    async def _worker():
        await asyncio.gather(*[_check_one(acc) for acc in accounts])
        async with _check_lock:
            _check_state["running"] = False

    asyncio.create_task(_worker())
    return ok({"message": "started", "total": total})


@router.get("/check-sessions/status")
async def check_sessions_status():
    """Poll trạng thái batch check sessions."""
    async with _check_lock:
        return ok(dict(_check_state))


@router.post("/check-sessions/cancel")
async def cancel_check_sessions():
    """Dừng batch check sessions."""
    async with _check_lock:
        if not _check_state["running"]:
            return ok({"cancelled": False, "message": "not running"})
        _check_state["cancelled"] = True
        _check_state["running"] = False
    return ok({"cancelled": True})


# ── Batch re-login (testmail only) ────────────────────────────────────────────

_relogin_lock = asyncio.Lock()
_relogin_state: dict[str, Any] = {
    "running": False,
    "cancelled": False,
    "total": 0,
    "done": 0,
    "success": 0,
    "failed": 0,
    "results": [],
}


@router.post("/batch-relogin")
async def batch_relogin():
    """Re-login toàn bộ AA testmail accounts bị expired (tuần tự — Playwright không chạy concurrent)."""
    from ...config.settings import load_config
    from ...services.artificialanalysis_ai.registrar import relogin_artificialanalysis

    async with _relogin_lock:
        if _relogin_state["running"]:
            return ok({**_relogin_state, "message": "already running"})

    accounts = await list_accounts("ARTIFICIALANALYSIS")
    # Chỉ testmail bị expired — không relogin sharebot/maildrop/v.v. vì one-time
    candidates = [
        a for a in accounts
        if a.get("email", "").endswith("@inbox.testmail.app")
        and a.get("check_status") in ("expired", "error", None, "")
        and not a.get("disabled")
    ]
    total = len(candidates)
    if total == 0:
        raise AppError(ErrorCode.NOT_FOUND, "Không có AA testmail account expired nào cần relogin", 404)

    async with _relogin_lock:
        _relogin_state.update({
            "running": True, "cancelled": False,
            "total": total, "done": 0, "success": 0, "failed": 0,
            "results": [],
        })

    cfg = load_config()
    sem = asyncio.Semaphore(5)

    async def _relogin_one(acc: dict) -> None:
        email = acc["email"]
        async with _relogin_lock:
            if _relogin_state["cancelled"]:
                return
        async with sem:
            async with _relogin_lock:
                if _relogin_state["cancelled"]:
                    return
            logs: list[str] = []
            try:
                await relogin_artificialanalysis(email, cfg, logs.append)
                status = "success"
                error = ""
            except (RuntimeError, ValueError, httpx.HTTPError) as exc:
                status = "failed"
                error = str(exc)[:300]
            async with _relogin_lock:
                _relogin_state["done"] += 1
                _relogin_state["success" if status == "success" else "failed"] += 1
                _relogin_state["results"].append({
                    "email": email,
                    "status": status,
                    "error": error,
                })

    async def _worker():
        await asyncio.gather(*[_relogin_one(acc) for acc in candidates])
        async with _relogin_lock:
            _relogin_state["running"] = False

    asyncio.create_task(_worker())
    return ok({"message": "started", "total": total})


@router.get("/batch-relogin/status")
async def batch_relogin_status():
    """Poll trạng thái batch re-login."""
    async with _relogin_lock:
        return ok(dict(_relogin_state))


@router.post("/batch-relogin/cancel")
async def batch_relogin_cancel():
    """Dừng batch re-login (sau khi account hiện tại xong)."""
    async with _relogin_lock:
        if not _relogin_state["running"]:
            return ok({"cancelled": False, "message": "not running"})
        _relogin_state["cancelled"] = True
    return ok({"cancelled": True})


# ── Batch accept Image Lab Terms (for existing sessions) ──────────────────────

_terms_lock = asyncio.Lock()
_terms_state: dict[str, Any] = {
    "running": False,
    "cancelled": False,
    "total": 0,
    "done": 0,
    "success": 0,
    "failed": 0,
    "results": [],
}


@router.post("/batch-accept-terms")
async def batch_accept_terms(all: bool = False):
    """Accept Image Lab Terms of Use cho AA accounts có session_state.

    Mặc định chỉ xử lý testmail accounts. Truyền ?all=true để xử lý toàn bộ.
    Gọi trực tiếp POST /api/playground/terms-acceptance — không cần Playwright.
    """
    async with _terms_lock:
        if _terms_state["running"]:
            return ok({**_terms_state, "message": "already running"})

    accounts = await list_accounts("ARTIFICIALANALYSIS")
    candidates = [
        a for a in accounts
        if a.get("session_state")
        and not a.get("disabled")
        and (all or "testmail" in a.get("email", ""))
    ]
    total = len(candidates)
    if total == 0:
        raise AppError(ErrorCode.NOT_FOUND, "Không có AA account nào có session_state", 404)

    async with _terms_lock:
        _terms_state.update({
            "running": True, "cancelled": False,
            "total": total, "done": 0, "success": 0, "failed": 0,
            "results": [],
        })

    aa_cfg = _aa_cfg()
    _AA_TERMS_URL = aa_cfg.terms_acceptance_url
    _TERMS_HEADERS = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Origin": aa_cfg.base_url,
        "Referer": aa_cfg.image_lab_url,
        "User-Agent": aa_cfg.user_agent,
    }
    sem = asyncio.Semaphore(20)

    async def _accept_one(acc: dict, client: httpx.AsyncClient) -> None:
        email = acc["email"]
        async with _terms_lock:
            if _terms_state["cancelled"]:
                return
        async with sem:
            async with _terms_lock:
                if _terms_state["cancelled"]:
                    return
            try:
                cookies = {c["name"]: c["value"] for c in json.loads(acc["session_state"]).get("cookies", [])}
                r = await client.post(
                    _AA_TERMS_URL,
                    cookies=cookies,
                    headers=_TERMS_HEADERS,
                    content=b"{}",
                    timeout=aa_cfg.check_timeout_sec,
                )
                if r.status_code not in (200, 201):
                    raise RuntimeError(f"HTTP {r.status_code}: {r.text[:100]}")
                status = "success"
                error = ""
            except (RuntimeError, ValueError, httpx.HTTPError) as exc:
                status = "failed"
                error = str(exc)[:300]
            async with _terms_lock:
                _terms_state["done"] += 1
                _terms_state["success" if status == "success" else "failed"] += 1
                _terms_state["results"].append({
                    "email": email,
                    "status": status,
                    "error": error,
                })

    async def _worker() -> None:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            await asyncio.gather(*[_accept_one(acc, client) for acc in candidates])
        async with _terms_lock:
            _terms_state["running"] = False

    asyncio.create_task(_worker())
    return ok({"message": "started", "total": total})


@router.get("/batch-accept-terms/status")
async def batch_accept_terms_status():
    """Poll trạng thái batch accept-terms."""
    async with _terms_lock:
        return ok(dict(_terms_state))


@router.post("/batch-accept-terms/cancel")
async def batch_accept_terms_cancel():
    """Dừng batch accept-terms."""
    async with _terms_lock:
        if not _terms_state["running"]:
            return ok({"cancelled": False, "message": "not running"})
        _terms_state["cancelled"] = True
    return ok({"cancelled": True})
