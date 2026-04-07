/**
 * tts.ts — API client cho ElevenLabs TTS Proxy (port 8800).
 *
 * Tách riêng khỏi client.ts vì TTS proxy chạy ở port khác (8800 vs 8799).
 */

if (!import.meta.env.VITE_TTS_BASE_URL)
  throw new Error("VITE_TTS_BASE_URL không được cấu hình");

const TTS_BASE = `${import.meta.env.VITE_TTS_BASE_URL}/api`;

// ── Types ─────────────────────────────────────────────────────────────────────

export interface TTSHealth {
  status: "ok";
  available_keys: number;
}

export interface ELVoice {
  voice_id: string;
  name: string;
  category: string;
  description?: string;
  preview_url?: string;
  labels?: Record<string, string>;
}

export interface ELModel {
  model_id: string;
  name: string;
  description: string;
  can_do_text_to_speech: boolean;
  can_do_voice_conversion: boolean;
  languages: { language_id: string; name: string }[];
  max_characters_request_subscribed_user: number;
}

export interface HistoryItem {
  history_item_id: string;
  voice_id: string;
  voice_name: string;
  text: string;
  date_unix: number;
  character_count_change_from: number;
  character_count_change_to: number;
  content_type: string;
  state: string;
  settings?: Record<string, unknown>;
  _account_email?: string;
}

export interface TTSGenerateParams {
  text: string;
  voice_id: string;
  model_id: string;
  output_format: string;
  language_code?: string;
  seed?: number;
  stability: number;
  similarity_boost: number;
  style: number;
  use_speaker_boost: boolean;
  speed: number;
  apply_text_normalization: "auto" | "on" | "off";
}

// ── Helpers ───────────────────────────────────────────────────────────────────

const _json = async <T>(r: Response): Promise<T> => {
  if (!r.ok) {
    const text = await r.text().catch(() => `HTTP ${r.status}`);
    throw new Error(`TTS API error ${r.status}: ${text.slice(0, 200)}`);
  }
  return r.json() as Promise<T>;
};

const _get = <T>(path: string) =>
  fetch(`${TTS_BASE}${path}`).then((r) => _json<T>(r));

// ── TTS API ───────────────────────────────────────────────────────────────────

export const ttsApi = {
  health: () => _get<TTSHealth>("/health"),

  listVoices: (voiceType = "default", pageSize = 100, category?: string) => {
    const qs = new URLSearchParams({ voice_type: voiceType, page_size: String(pageSize) });
    if (category) qs.set("category", category);
    return _get<{ voices: ELVoice[]; count: number }>(`/voices?${qs}`);
  },

  listModels: () => _get<{ models: ELModel[]; count: number }>("/models"),

  /** Generate TTS → trả về Blob URL để play ngay. Headers chứa metadata. */
  generate: async (
    params: TTSGenerateParams
  ): Promise<{ blobUrl: string; usedAccount: string; requestId: string; characterCount: string }> => {
    const body = {
      text: params.text,
      voice_id: params.voice_id,
      model_id: params.model_id,
      output_format: params.output_format,
      language_code: params.language_code || undefined,
      seed: params.seed || undefined,
      voice_settings: {
        stability: params.stability,
        similarity_boost: params.similarity_boost,
        style: params.style,
        use_speaker_boost: params.use_speaker_boost,
        speed: params.speed,
      },
      apply_text_normalization: params.apply_text_normalization,
    };

    const r = await fetch(`${TTS_BASE}/tts`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    if (!r.ok) {
      const text = await r.text().catch(() => `HTTP ${r.status}`);
      const failedAccount = r.headers.get("X-Failed-Account");
      const accountInfo = failedAccount ? ` [account: ${failedAccount}]` : "";
      throw new Error(`TTS generate error ${r.status}: ${text.slice(0, 200)}${accountInfo}`);
    }

    const blob = await r.blob();
    return {
      blobUrl: URL.createObjectURL(blob),
      usedAccount: r.headers.get("X-Used-Account") ?? "",
      requestId: r.headers.get("X-Request-Id") ?? "",
      characterCount: r.headers.get("X-Character-Count") ?? "",
    };
  },

  listHistory: (pageSize = 20, voiceId?: string, startAfterUnix?: number) => {
    const qs = new URLSearchParams({ page_size: String(pageSize) });
    if (voiceId) qs.set("voice_id", voiceId);
    if (startAfterUnix != null) qs.set("start_after_unix", String(startAfterUnix));
    return _get<{ history: HistoryItem[]; has_more: boolean; last_unix: number | null }>(
      `/history?${qs}`
    );
  },

  streamHistoryAudio: (historyItemId: string, accountEmail?: string): string => {
    const base = `${TTS_BASE}/history/${historyItemId}/audio`;
    return accountEmail ? `${base}?account=${encodeURIComponent(accountEmail)}` : base;
  },

  deleteHistoryItem: (historyItemId: string) =>
    fetch(`${TTS_BASE}/history/${historyItemId}`, { method: "DELETE" }).then((r) =>
      _json<{ status: string }>(r)
    ),

  getUserSubscription: () => _get<Record<string, unknown>>("/user/subscription"),
};
