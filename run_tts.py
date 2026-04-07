"""
run_tts.py — Start ElevenLabs TTS Proxy server.

Port mặc định: 8800
Override: TTS_HOST / TTS_PORT env vars

Usage:
  python run_tts.py
  TTS_PORT=9000 python run_tts.py
"""
import os
import sys

import uvicorn

if sys.platform == "win32":
    # Giữ ProactorEventLoop trên Windows — cần cho httpx async streaming
    import uvicorn.loops.asyncio as _uvloop
    _uvloop.asyncio_setup = lambda use_subprocess=False: None

if __name__ == "__main__":
    uvicorn.run(
        "src.tts_proxy.server:app",
        host=os.getenv("TTS_HOST", "127.0.0.1"),
        port=int(os.getenv("TTS_PORT", "8800")),
        reload=False,
    )
