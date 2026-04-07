"""
server.py — FastAPI app entry point cho TTS Proxy.

Microservice riêng, port 8800 (mặc định).
Không share state với account-creation server (port 8799).
Chỉ đọc accounts.db — không ghi (ngoại trừ update quota_pct).

API Groups:
  /api/health                     — liveness check
  /api/tts                        — TTS generate + stream
  /api/tts/with-timestamps        — TTS + word-level alignment
  /api/tts/stream-with-timestamps — TTS stream + word-level alignment
  /api/tts/ws/{voice_id}          — TTS WebSocket proxy
  /api/voices                     — list voices (GET /v2/voices)
  /api/voices/{id}                — get/delete/edit voice (CRUD)
  /api/voices/add                 — clone voice (POST)
  /api/pronunciation              — pronunciation dictionaries CRUD
  /api/history                    — history items CRUD + audio download
  /api/user                       — user info + subscription
  /api/models                     — list AI models
"""
from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .router import router as router_tts
from .router_history import router as router_history
from .router_models import router as router_models
from .router_pronunciation import router as router_pronunciation
from .router_timestamps import router as router_timestamps
from .router_user import router as router_user
from .router_voices import router as router_voices
from .router_websocket import router as router_websocket

_cors_origins = os.getenv("TTS_CORS_ORIGINS", "*").split(",")

app = FastAPI(
    title="ElevenLabs TTS Proxy",
    version="2.0.0",
    description=(
        "Full-featured ElevenLabs API proxy với round-robin key rotation. "
        "Covers: TTS, TTS Timestamps, TTS WebSocket, Voice CRUD, "
        "Pronunciation Dictionaries, History, User/Subscription, Models."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)

# Register all routers — thứ tự quan trọng:
# router_voices phải trước router_tts để /voices/add không bị /voices/{voice_id} match
app.include_router(router_tts, prefix="/api")
app.include_router(router_timestamps, prefix="/api")
app.include_router(router_websocket, prefix="/api")
app.include_router(router_voices, prefix="/api")
app.include_router(router_history, prefix="/api")
app.include_router(router_user, prefix="/api")
app.include_router(router_models, prefix="/api")
app.include_router(router_pronunciation, prefix="/api")

