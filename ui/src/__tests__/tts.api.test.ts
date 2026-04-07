import { describe, it, expect, beforeEach } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "./mocks/server";

// TTS base URL phải khớp với VITE_TTS_BASE_URL/.env trong test env
const TTS_BASE = "http://127.0.0.1:8800/api";

// ── Mock data ─────────────────────────────────────────────────────────────────

const mockHealth = { status: "ok", available_keys: 3 };

const mockVoice = {
  voice_id: "voice-abc",
  name: "Rachel",
  category: "premade",
  description: "Test voice",
  preview_url: "https://example.com/preview.mp3",
  labels: { accent: "american" },
};

const mockModel = {
  model_id: "eleven_v3",
  name: "Eleven v3",
  description: "Latest model",
  can_do_text_to_speech: true,
  can_do_voice_conversion: false,
  languages: [{ language_id: "en", name: "English" }],
  max_characters_request_subscribed_user: 5000,
};

const mockHistoryItem = {
  history_item_id: "hist-001",
  voice_id: "voice-abc",
  voice_name: "Rachel",
  text: "Hello world",
  date_unix: 1700000000,
  character_count_change_from: 0,
  character_count_change_to: 11,
  content_type: "audio/mpeg",
  state: "created",
};

const mockSubscription = {
  tier: "free",
  character_count: 1234,
  character_limit: 10000,
  status: "active",
  next_character_count_reset_unix: 1709251200,
};

// Lazy import sau khi env đã sẵn sàng
const getTtsApi = async () => (await import("../api/tts")).ttsApi;

// ── health ────────────────────────────────────────────────────────────────────

describe("ttsApi.health", () => {
  beforeEach(() => {
    server.use(
      http.get(`${TTS_BASE}/health`, () => HttpResponse.json(mockHealth))
    );
  });

  it("returns health status", async () => {
    const api = await getTtsApi();
    const result = await api.health();
    expect(result.status).toBe("ok");
    expect(result.available_keys).toBe(3);
  });
});

// ── listVoices ────────────────────────────────────────────────────────────────

describe("ttsApi.listVoices", () => {
  beforeEach(() => {
    server.use(
      http.get(`${TTS_BASE}/voices`, () =>
        HttpResponse.json({ voices: [mockVoice], count: 1 })
      )
    );
  });

  it("returns voices list", async () => {
    const api = await getTtsApi();
    const result = await api.listVoices();
    expect(result.voices).toHaveLength(1);
    expect(result.voices[0].voice_id).toBe("voice-abc");
    expect(result.voices[0].name).toBe("Rachel");
    expect(result.count).toBe(1);
  });

  it("passes voice_type as query param", async () => {
    let capturedUrl = "";
    server.use(
      http.get(`${TTS_BASE}/voices`, ({ request }) => {
        capturedUrl = request.url;
        return HttpResponse.json({ voices: [], count: 0 });
      })
    );
    const api = await getTtsApi();
    await api.listVoices("personal", 50);
    expect(capturedUrl).toContain("voice_type=personal");
    expect(capturedUrl).toContain("page_size=50");
  });
});

// ── listModels ────────────────────────────────────────────────────────────────

describe("ttsApi.listModels", () => {
  beforeEach(() => {
    server.use(
      http.get(`${TTS_BASE}/models`, () =>
        HttpResponse.json({ models: [mockModel], count: 1 })
      )
    );
  });

  it("returns models list", async () => {
    const api = await getTtsApi();
    const result = await api.listModels();
    expect(result.models).toHaveLength(1);
    expect(result.models[0].model_id).toBe("eleven_v3");
  });
});

// ── generate (TTS) ────────────────────────────────────────────────────────────

describe("ttsApi.generate", () => {
  const validParams = {
    text: "Hello world",
    voice_id: "voice-abc",
    model_id: "eleven_v3",
    output_format: "mp3_44100_128",
    stability: 0.5,
    similarity_boost: 0.75,
    style: 0.0,
    use_speaker_boost: true,
    speed: 1.0,
    apply_text_normalization: "auto" as const,
  };

  beforeEach(() => {
    server.use(
      http.post(`${TTS_BASE}/tts`, () => {
        const audioBytes = new Uint8Array([0xff, 0xfb, 0x90, 0x00]);
        return new HttpResponse(audioBytes.buffer, {
          status: 200,
          headers: {
            "Content-Type": "audio/mpeg",
            "X-Used-Account": "test@example.com",
            "X-Request-Id": "req-123",
            "X-Character-Count": "11",
          },
        });
      })
    );
  });

  it("returns blobUrl string", async () => {
    const api = await getTtsApi();
    const result = await api.generate(validParams);
    expect(typeof result.blobUrl).toBe("string");
  });

  it("returns metadata from response headers", async () => {
    const api = await getTtsApi();
    const result = await api.generate(validParams);
    expect(result.usedAccount).toBe("test@example.com");
    expect(result.requestId).toBe("req-123");
    expect(result.characterCount).toBe("11");
  });

  it("throws on API error", async () => {
    server.use(
      http.post(`${TTS_BASE}/tts`, () =>
        HttpResponse.json({ error: "quota_exceeded" }, { status: 429 })
      )
    );
    const api = await getTtsApi();
    await expect(api.generate(validParams)).rejects.toThrow("429");
  });

  it("sends correct request body", async () => {
    let capturedBody: unknown;
    server.use(
      http.post(`${TTS_BASE}/tts`, async ({ request }) => {
        capturedBody = await request.json();
        const bytes = new Uint8Array([0xff, 0xfb]);
        return new HttpResponse(bytes.buffer, {
          status: 200,
          headers: {
            "Content-Type": "audio/mpeg",
            "X-Used-Account": "",
            "X-Request-Id": "",
            "X-Character-Count": "",
          },
        });
      })
    );
    const api = await getTtsApi();
    await api.generate({ ...validParams, language_code: "en" });

    const body = capturedBody as Record<string, unknown>;
    expect(body.text).toBe("Hello world");
    expect(body.voice_id).toBe("voice-abc");
    expect(body.model_id).toBe("eleven_v3");
    expect((body.voice_settings as Record<string, unknown>).stability).toBe(0.5);
  });
});

// ── listHistory ───────────────────────────────────────────────────────────────

describe("ttsApi.listHistory", () => {
  beforeEach(() => {
    server.use(
      http.get(`${TTS_BASE}/history`, () =>
        HttpResponse.json({
          history: [mockHistoryItem],
          has_more: false,
          last_history_item_id: "hist-001",
        })
      )
    );
  });

  it("returns history list", async () => {
    const api = await getTtsApi();
    const result = await api.listHistory();
    expect(result.history).toHaveLength(1);
    expect(result.history[0].history_item_id).toBe("hist-001");
    expect(result.has_more).toBe(false);
  });

  it("passes page_size query param", async () => {
    let capturedUrl = "";
    server.use(
      http.get(`${TTS_BASE}/history`, ({ request }) => {
        capturedUrl = request.url;
        return HttpResponse.json({ history: [], has_more: false, last_history_item_id: "" });
      })
    );
    const api = await getTtsApi();
    await api.listHistory(25);
    expect(capturedUrl).toContain("page_size=25");
  });

  it("optionally passes voice_id", async () => {
    let capturedUrl = "";
    server.use(
      http.get(`${TTS_BASE}/history`, ({ request }) => {
        capturedUrl = request.url;
        return HttpResponse.json({ history: [], has_more: false, last_history_item_id: "" });
      })
    );
    const api = await getTtsApi();
    await api.listHistory(10, "voice-abc");
    expect(capturedUrl).toContain("voice_id=voice-abc");
  });
});

// ── streamHistoryAudio ────────────────────────────────────────────────────────

describe("ttsApi.streamHistoryAudio", () => {
  it("returns direct URL string (no fetch)", async () => {
    const api = await getTtsApi();
    const url = api.streamHistoryAudio("hist-001");
    expect(url).toBe(`${TTS_BASE}/history/hist-001/audio`);
  });
});

// ── deleteHistoryItem ─────────────────────────────────────────────────────────

describe("ttsApi.deleteHistoryItem", () => {
  it("sends DELETE request", async () => {
    let method = "";
    server.use(
      http.delete(`${TTS_BASE}/history/:id`, ({ request }) => {
        method = request.method;
        return HttpResponse.json({ status: "deleted" });
      })
    );
    const api = await getTtsApi();
    const result = await api.deleteHistoryItem("hist-001");
    expect(method).toBe("DELETE");
    expect(result.status).toBe("deleted");
  });

  it("throws on 404", async () => {
    server.use(
      http.delete(`${TTS_BASE}/history/:id`, () =>
        HttpResponse.json({ error: "not found" }, { status: 404 })
      )
    );
    const api = await getTtsApi();
    await expect(api.deleteHistoryItem("nonexistent")).rejects.toThrow("404");
  });
});

// ── getUserSubscription ───────────────────────────────────────────────────────

describe("ttsApi.getUserSubscription", () => {
  beforeEach(() => {
    server.use(
      http.get(`${TTS_BASE}/user/subscription`, () =>
        HttpResponse.json(mockSubscription)
      )
    );
  });

  it("returns subscription data", async () => {
    const api = await getTtsApi();
    const result = await api.getUserSubscription();
    expect(result.tier).toBe("free");
    expect(result.character_count).toBe(1234);
    expect(result.character_limit).toBe(10000);
  });
});
