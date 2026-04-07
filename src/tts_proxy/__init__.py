"""
tts_proxy — ElevenLabs TTS reverse proxy với round-robin key rotation.

Microservice độc lập, expose một endpoint POST /api/tts.
Đọc API keys từ accounts.db (cùng DB với account-creation server).
Tự động chọn key còn quota nhiều nhất, stream audio thẳng về client.
"""
