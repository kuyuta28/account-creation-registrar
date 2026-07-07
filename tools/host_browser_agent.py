"""
host_browser_agent.py — Browser Gateway (chạy trên HOST Windows).

Trạm browser thống nhất cho toàn bộ hệ thống. Container (registrar/aa-proxy/mail-service)
gọi qua HTTP khi cần browser. Gateway mở browser thật trên host (Camoufox / Edge),
chạy task automation in-process, stream log qua WebSocket.

Lý do: browser không chạy trong container (crash camoufox cache, không display).
Local 1-user, loopback only, không auth.

Endpoints:
  GET  /health                       — liveness
  POST /open                         — spawn visible browser với saved session (legacy)
  POST /v1/tasks                     — chạy 1 browser task
      body: {task, engine?, headless?, args?}
      resp: {task_id}                 (task chạy background)
  GET  /v1/tasks/{task_id}           — status
  WS   /v1/tasks/{task_id}/logs      — stream log realtime
  GET  /v1/tasks                     — list tasks

Chạy:  py registrar/tools/host_browser_agent.py
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
import threading
import traceback
import uuid
from pathlib import Path
from typing import Any, Callable

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

REGISTRAR_ROOT = Path(__file__).resolve().parent.parent
# PYTHONPATH = repo root + registrar src, để import src.* + common.*
sys.path.insert(0, str(REGISTRAR_ROOT))
sys.path.insert(0, str(REGISTRAR_ROOT.parent / "common" / "src"))

from src.api.tools.browser_gateway_engines import open_browser, ENGINES  # noqa: E402
from src.api.tools.browser_tasks import get_task, list_tasks  # noqa: E402
from src.config.settings import load_config  # noqa: E402
from common.database._engine import init_async_db  # noqa: E402
from watchdog.events import FileSystemEventHandler  # noqa: E402
from watchdog.observers import Observer  # noqa: E402

app = FastAPI(title="Browser Gateway", version="2.0.0")
_log = logging.getLogger("browser_gateway")

LOG_DIR = REGISTRAR_ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# ── Live config: hot-reload khi config/*.yaml đổi, không restart ────────────
# Event-driven qua watchdog (OS ReadDirectoryChangesW). Reload NGAY khi file
# đổi, không đợi task kế tiếp. Per-task fields (headless, proxy) đọc current_cfg()
# để ăn giá trị mới. Startup-bound (DB, host/port) đọc _BOOT_CFG 1 lần (bind tài
# nguyên). Reload-callback registry cho mở rộng: đăng ký hàm chạy sau mỗi reload
# (vd: resize semaphore, notify, sync sang service khác).
_CONFIG_DIR = REGISTRAR_ROOT / "config"
_cfg_lock = threading.Lock()
_reload_callbacks: list[Callable[[Any], None]] = []


def register_reload_callback(fn: Callable[[Any], None]) -> None:
    """Đăng ký callback chạy sau mỗi config reload thành công. Nhận AppConfig mới."""
    _reload_callbacks.append(fn)


def _do_reload() -> None:
    """Reload config an toàn: giữ config cũ nếu parse lỗi, chạy callbacks."""
    with _cfg_lock:
        try:
            new_cfg = load_config()
        except Exception as exc:  # noqa: BLE001 — config lỗi: giữ config cũ, không sập
            _log.error("Config reload failed, giữ config cũ: %s", exc)
            return
        _cfg_state["cfg"] = new_cfg
        _log.info("Config reloaded (hot) — headless=%s", new_cfg.headless)
        cfg_ref = new_cfg
    # Callbacks chạy ngoài lock để tránh deadlock; lỗi 1 callback không ảnh hưởng callback khác.
    for fn in _reload_callbacks:
        try:
            fn(cfg_ref)
        except Exception as exc:  # noqa: BLE001
            _log.error("Reload callback %s failed: %s", getattr(fn, "__name__", fn), exc)


def current_cfg():
    """Trả AppConfig live (luôn mới nhất do watchdog reload realtime)."""
    with _cfg_lock:
        return _cfg_state["cfg"]


class _ConfigChangeHandler(FileSystemEventHandler):
    """Watchdog handler: reload khi file *.yaml trong config/ đổi/tạo."""

    def __init__(self, debounce: float = 0.3) -> None:
        # Editor đôi khi ghi 2-3 event liên tiếp (write+rename); gộp lại.
        self._debounce = debounce
        self._timer: threading.Timer | None = None

    def _schedule(self) -> None:
        if self._timer:
            self._timer.cancel()
        self._timer = threading.Timer(self._debounce, _do_reload)
        self._timer.daemon = True
        self._timer.start()

    def on_modified(self, event) -> None:  # noqa: D401
        if not event.is_directory and event.src_path.endswith(".yaml"):
            self._schedule()

    def on_created(self, event) -> None:
        if not event.is_directory and event.src_path.endswith(".yaml"):
            self._schedule()


_cfg_state: dict[str, Any] = {"cfg": load_config()}

# Khởi tạo DB 1 lần (bind connection pool).
_BOOT_CFG = _cfg_state["cfg"]
if _BOOT_CFG.database.database_url:
    init_async_db(_BOOT_CFG.database.database_url)

MAX_CONCURRENT = _BOOT_CFG.max_concurrent
_semaphore = asyncio.Semaphore(MAX_CONCURRENT)

# Watcher daemon: theo dõi config/ realtime, reload ngay khi yaml đổi.
_observer = Observer()
_observer.daemon = True
_observer.schedule(_ConfigChangeHandler(), str(_CONFIG_DIR), recursive=False)
_observer.start()

# task_id -> TaskRecord
_tasks: dict[str, dict[str, Any]] = {}


class TaskRequest(BaseModel):
    task: str
    engine: str | None = None
    headless: bool | None = None
    args: dict[str, Any] = {}


class OpenRequest(BaseModel):
    service: str
    email: str
    url: str | None = None


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s %(name)s %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(LOG_DIR / "host_browser_agent.log", encoding="utf-8"),
        ],
    )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/v1/tasks")
async def api_list_tasks() -> dict[str, Any]:
    return {"tasks": list_tasks(), "engines": list(ENGINES)}


@app.post("/v1/tasks")
async def api_create_task(req: TaskRequest) -> dict[str, Any]:
    entry = get_task(req.task)
    if entry is None:
        raise HTTPException(400, f"Unknown task {req.task!r}. Available: {list_tasks()}")

    handler, default_engine = entry
    engine = req.engine or default_engine
    cfg = current_cfg()
    headless = cfg.headless if req.headless is None else req.headless

    task_id = str(uuid.uuid4())
    rec: dict[str, Any] = {
        "task_id": task_id,
        "task": req.task,
        "engine": engine,
        "headless": headless,
        "status": "queued",
        "result": None,
        "error": None,
        "subscribers": set(),
    }
    _tasks[task_id] = rec

    asyncio.create_task(_run_task(task_id, handler, engine, headless, req.args))
    return {"task_id": task_id}


async def _run_task(task_id, handler, engine, headless, args) -> None:
    rec = _tasks[task_id]
    log_q: asyncio.Queue[str | None] = asyncio.Queue()

    def log_fn(msg: str) -> None:
        rec["subscribers"]  # touch
        log_q.put_nowait(msg)
        _log.info("[task=%s] %s", task_id[:8], msg)

    # Broadcast task: đẩy log tới tất cả WS subscriber
    async def _pump():
        while True:
            msg = await log_q.get()
            if msg is None:
                break
            dead = []
            for ws in list(rec["subscribers"]):
                try:
                    await ws.send_text(msg)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                rec["subscribers"].discard(ws)

    pump = asyncio.create_task(_pump())

    async with _semaphore:
        rec["status"] = "running"
        log_fn(f"▶ Bắt đầu task={rec['task']} engine={engine} headless={headless}")
        try:
            async with open_browser(engine, headless=headless, proxy=current_cfg().proxy) as browser:
                result = await handler(browser=browser, args=args, log_fn=log_fn)
            rec["result"] = result
            rec["status"] = "done"
            log_fn("✓ Task hoàn tất")
        except Exception as exc:
            rec["error"] = f"{type(exc).__name__}: {exc}"
            rec["status"] = "failed"
            log_fn(f"✗ Task lỗi: {rec['error']}")
            _log.error("Task %s failed:\n%s", task_id[:8], traceback.format_exc())
        finally:
            await log_q.put(None)
            await pump

    # Thông báo completion tới subscriber còn lại
    for ws in list(rec["subscribers"]):
        try:
            await ws.send_text(f"__END__ {rec['status']}")
        except Exception:
            pass


@app.get("/v1/tasks/{task_id}")
async def api_task_status(task_id: str) -> dict[str, Any]:
    rec = _tasks.get(task_id)
    if not rec:
        raise HTTPException(404, "not found")
    return {
        "task_id": task_id,
        "task": rec["task"],
        "engine": rec["engine"],
        "status": rec["status"],
        "result": rec["result"],
        "error": rec["error"],
    }


@app.websocket("/v1/tasks/{task_id}/logs")
async def api_task_logs(ws: WebSocket, task_id: str) -> None:
    rec = _tasks.get(task_id)
    if not rec:
        await ws.close(code=4004)
        return
    await ws.accept()
    rec["subscribers"].add(ws)
    try:
        # Nếu task đã kết thúc, gửi trạng thái cuối rồi đóng
        if rec["status"] in ("done", "failed"):
            await ws.send_text(f"__END__ {rec['status']}")
        # Giữ WS mở cho đến khi client đóng hoặc task kết thúc
        while rec["status"] not in ("done", "failed"):
            await asyncio.sleep(0.5)
        await ws.send_text(f"__END__ {rec['status']}")
    except WebSocketDisconnect:
        pass
    finally:
        rec["subscribers"].discard(ws)


# ── Legacy /open: spawn visible browser với saved session ──────────────────

@app.post("/open")
async def open_browser_legacy(req: OpenRequest) -> dict[str, Any]:
    """Spawn visible browser (subprocess open_browser_session.py). Backward compat."""
    import subprocess
    script = REGISTRAR_ROOT / "src" / "api" / "tools" / "open_browser_session.py"
    cmd = [sys.executable, str(script), req.service, req.email]
    if req.url:
        cmd.append(req.url)
    env = {**__import__("os").environ, "PYTHONPATH": str(REGISTRAR_ROOT)}
    try:
        proc = subprocess.Popen(cmd, env=env, cwd=str(REGISTRAR_ROOT))
        _log.info("Legacy /open spawned pid=%s for %s/%s", proc.pid, req.service, req.email)
        return {"launched": True, "pid": proc.pid}
    except Exception as exc:
        _log.error("Legacy /open failed: %s", exc)
        return {"launched": False, "pid": None, "error": str(exc)}


if __name__ == "__main__":
    import uvicorn
    _setup_logging()
    _log.info(
        "Browser Gateway starting on %s:%d (max_concurrent=%d)",
        _BOOT_CFG.api.gateway_host, _BOOT_CFG.api.gateway_port, MAX_CONCURRENT,
    )
    uvicorn.run(app, host=_BOOT_CFG.api.gateway_host, port=_BOOT_CFG.api.gateway_port)
