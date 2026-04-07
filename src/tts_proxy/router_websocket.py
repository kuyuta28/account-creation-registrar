"""
router_websocket.py — TTS WebSocket proxy (item 7).

Routes:
  WS /api/tts/ws/{voice_id}  — transparent proxy tới ElevenLabs WebSocket

Client connect vào proxy này bằng WebSocket. Proxy sẽ tự lấy API key tốt nhất
từ pool và forward tất cả messages hai chiều tới ElevenLabs.

Client KHÔNG cần biết API key — mọi thứ được xử lý bên trong proxy.

Query params (optional, truyền khi connect):
  model_id, language_code, output_format, enable_logging, enable_ssml_parsing,
  inactivity_timeout, sync_alignment, auto_mode, apply_text_normalization, seed

ElevenLabs WebSocket message format:
  Initialize: {"text": " ", "voice_settings": {"stability": 0.5, ...}}
  Send text:  {"text": "Hello World "}
  Close:      {"text": ""}
  Response:   {"audio": "<base64>", "alignment": {...}, "normalizedAlignment": {...}}
  Final:      {"isFinal": true}
"""
from __future__ import annotations

import asyncio
import logging
from urllib.parse import urlencode

import websockets
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from .key_pool import load_available_keys

_log = logging.getLogger(__name__)

_EL_WS_BASE = "wss://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream-input"

router = APIRouter()


def _build_el_ws_url(
    voice_id: str,
    api_key: str,
    model_id: str,
    language_code: str | None,
    output_format: str,
    enable_logging: bool,
    enable_ssml_parsing: bool,
    inactivity_timeout: int,
    sync_alignment: bool,
    auto_mode: bool,
    apply_text_normalization: str,
    seed: int | None,
) -> str:
    """Build ElevenLabs WebSocket URL với đầy đủ query params."""
    params: dict = {
        "xi-api-key": api_key,
        "model_id": model_id,
        "output_format": output_format,
        "enable_logging": str(enable_logging).lower(),
        "enable_ssml_parsing": str(enable_ssml_parsing).lower(),
        "inactivity_timeout": inactivity_timeout,
        "sync_alignment": str(sync_alignment).lower(),
        "auto_mode": str(auto_mode).lower(),
        "apply_text_normalization": apply_text_normalization,
    }
    if language_code:
        params["language_code"] = language_code
    if seed is not None:
        params["seed"] = seed
    base = _EL_WS_BASE.format(voice_id=voice_id)
    return f"{base}?{urlencode(params)}"


@router.websocket("/tts/ws/{voice_id}")
async def tts_websocket_proxy(
    voice_id: str,
    websocket: WebSocket,
    model_id: str = Query(default="eleven_v3"),
    language_code: str | None = Query(default=None),
    output_format: str = Query(default="mp3_44100_128"),
    enable_logging: bool = Query(default=True),
    enable_ssml_parsing: bool = Query(default=False),
    inactivity_timeout: int = Query(default=20, ge=1, le=180),
    sync_alignment: bool = Query(default=False),
    auto_mode: bool = Query(default=False),
    apply_text_normalization: str = Query(default="auto"),
    seed: int | None = Query(default=None),
) -> None:
    """WebSocket proxy: kết nối client ↔ ElevenLabs TTS WebSocket.

    Client kết nối vào đây và gửi/nhận messages đúng format của ElevenLabs
    mà không cần biết API key. Proxy inject key từ pool.

    Nếu không có key nào available → đóng với code 1011.
    """
    keys = load_available_keys()
    if not keys:
        await websocket.close(code=1011, reason="No ElevenLabs keys available")
        return

    await websocket.accept()
    key_entry = keys[0]

    el_url = _build_el_ws_url(
        voice_id=voice_id,
        api_key=key_entry.api_key,
        model_id=model_id,
        language_code=language_code,
        output_format=output_format,
        enable_logging=enable_logging,
        enable_ssml_parsing=enable_ssml_parsing,
        inactivity_timeout=inactivity_timeout,
        sync_alignment=sync_alignment,
        auto_mode=auto_mode,
        apply_text_normalization=apply_text_normalization,
        seed=seed,
    )

    _log.info("WS proxy: voice=%s model=%s key=%s", voice_id, model_id, key_entry.email)

    try:
        async with websockets.connect(el_url) as el_ws:
            await _proxy_bidirectional(websocket, el_ws, key_entry.email)
    except websockets.exceptions.InvalidHandshake as exc:
        _log.error("ElevenLabs WS handshake failed (key=%s): %s", key_entry.email, exc)
        await websocket.close(code=1011, reason="ElevenLabs connection failed")
    except WebSocketDisconnect:
        _log.debug("Client disconnected from WS proxy (voice=%s)", voice_id)
    except Exception as exc:  # noqa: BLE001 - WS proxy connection: log and continue
        _log.error("WS proxy error: %s", exc)
        try:
            await websocket.close(code=1011, reason="Internal proxy error")
        except Exception:  # noqa: BLE001 — best-effort optional UI action
            pass


async def _proxy_bidirectional(
    client_ws: WebSocket,
    el_ws,
    key_email: str,
) -> None:
    """Forward messages both ways giữa client và ElevenLabs WS.

    Dùng asyncio.gather để chạy 2 coroutine concurrent:
      - client → ElevenLabs
      - ElevenLabs → client

    Khi 1 side ngắt, cancel side còn lại.
    """
    stop_event = asyncio.Event()

    async def client_to_el() -> None:
        try:
            while not stop_event.is_set():
                try:
                    async with asyncio.timeout(1.0):
                        data = await client_ws.receive_text()
                    await el_ws.send(data)
                except TimeoutError:
                    continue
        except WebSocketDisconnect:
            _log.debug("Client disconnected (key=%s)", key_email)
        except Exception as exc:  # noqa: BLE001 — WS forwarding: connection drops expected
            _log.debug("client→el error: %s", exc)
        finally:
            stop_event.set()

    async def el_to_client() -> None:
        try:
            async for msg in el_ws:
                if stop_event.is_set():
                    break
                if isinstance(msg, bytes):
                    await client_ws.send_bytes(msg)
                else:
                    await client_ws.send_text(msg)
        except Exception as exc:  # noqa: BLE001 — WS forwarding: connection drops expected
            _log.debug("el→client error: %s", exc)
        finally:
            stop_event.set()

    await asyncio.gather(client_to_el(), el_to_client(), return_exceptions=True)
