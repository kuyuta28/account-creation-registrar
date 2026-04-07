import { useEffect, useRef, useState } from "react";
import { open } from "@tauri-apps/plugin-dialog";
import { writeFile } from "@tauri-apps/plugin-fs";
import { ttsApi, type ELModel, type ELVoice, type HistoryItem } from "../api/tts";
import { useLocalStorage } from "../hooks/useLocalStorage";

// ── Constants ─────────────────────────────────────────────────────────────────

const OUTPUT_FORMATS = [
  { value: "mp3_44100_128", label: "MP3 44.1kHz 128kbps" },
  { value: "mp3_44100_192", label: "MP3 44.1kHz 192kbps" },
  { value: "mp3_22050_32", label: "MP3 22kHz 32kbps (nhẹ)" },
  { value: "pcm_44100", label: "PCM 44.1kHz (Pro)" },
];

const LANG_OPTIONS = [
  { value: "", label: "Auto detect" },
  { value: "vi", label: "Tiếng Việt" },
  { value: "en", label: "English" },
  { value: "ja", label: "Japanese" },
  { value: "zh", label: "Chinese" },
  { value: "ko", label: "Korean" },
  { value: "fr", label: "French" },
  { value: "de", label: "German" },
  { value: "es", label: "Spanish" },
  { value: "pt", label: "Portuguese" },
  { value: "th", label: "Thai" },
  { value: "id", label: "Indonesian" },
];

// ── Tiny sub-components ───────────────────────────────────────────────────────

function Slider({
  label, value, min, max, step, onChange,
}: {
  label: string; value: number; min: number; max: number; step: number;
  onChange: (v: number) => void;
}) {
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs text-gray-500">
        <span>{label}</span>
        <span className="font-mono text-gray-700">{value.toFixed(2)}</span>
      </div>
      <input
        type="range" min={min} max={max} step={step}
        value={value}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        className="w-full h-1.5 accent-violet-600 cursor-pointer"
      />
    </div>
  );
}

function Badge({ children, color = "gray" }: { children: React.ReactNode; color?: string }) {
  const cls: Record<string, string> = {
    gray: "bg-gray-100 text-gray-600",
    green: "bg-green-50 text-green-700",
    violet: "bg-violet-50 text-violet-700",
    amber: "bg-amber-50 text-amber-700",
  };
  return (
    <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium ${cls[color] ?? cls.gray}`}>
      {children}
    </span>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function TTSPage() {
  // Data
  const [voices, setVoices] = useState<ELVoice[]>([]);
  const [models, setModels] = useState<ELModel[]>([]);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [availableKeys, setAvailableKeys] = useState<number | null>(null);
  const [subscription, setSubscription] = useState<Record<string, unknown> | null>(null);

  // Form state — persisted
  const [text, setText] = useLocalStorage("tts.text", "");
  const [voiceId, setVoiceId] = useLocalStorage("tts.voiceId", "");
  const [modelId, setModelId] = useLocalStorage("tts.modelId", "");
  const [outputFormat, setOutputFormat] = useLocalStorage("tts.outputFormat", "mp3_44100_128");
  const [langCode, setLangCode] = useLocalStorage("tts.langCode", "");
  const [stability, setStability] = useLocalStorage("tts.stability", 0.5);
  const [similarityBoost, setSimilarityBoost] = useLocalStorage("tts.similarityBoost", 0.75);
  const [style, setStyle] = useLocalStorage("tts.style", 0.0);
  const [speakerBoost, setSpeakerBoost] = useLocalStorage("tts.speakerBoost", true);
  const [speed, setSpeed] = useLocalStorage("tts.speed", 1.0);
  const [normMode, setNormMode] = useLocalStorage<"auto" | "on" | "off">("tts.normMode", "auto");
  const [voiceSearch, setVoiceSearch] = useLocalStorage("tts.voiceSearch", "");
  const [voiceTypeFilter, setVoiceTypeFilter] = useLocalStorage("tts.voiceTypeFilter", "default");
  const [voiceCategoryFilter, setVoiceCategoryFilter] = useLocalStorage("tts.voiceCategoryFilter", "");
  const [voiceGenderFilter, setVoiceGenderFilter] = useLocalStorage("tts.voiceGenderFilter", "");
  const [voiceAccentFilter, setVoiceAccentFilter] = useLocalStorage("tts.voiceAccentFilter", "");
  const [autoDownload, setAutoDownload] = useLocalStorage("tts.autoDownload", false);
  const [downloadFolder, setDownloadFolder] = useLocalStorage("tts.downloadFolder", "");

  // Audio player
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [lastMeta, setLastMeta] = useState<{ account: string; requestId: string; chars: string } | null>(null);
  const audioRef = useRef<HTMLAudioElement>(null);

  // Loading / error
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Tabs
  const [tab, setTab] = useState<"generate" | "history" | "voices" | "subscription">("generate");

  // History lazy audio: chỉ load audio khi user click play
  const [historyHasMore, setHistoryHasMore] = useState(false);
  const [historyLastUnix, setHistoryLastUnix] = useState<number | null>(null);
  const [historyLoading, setHistoryLoading] = useState(false);

  // ── Load data ──────────────────────────────────────────────────────────────

  useEffect(() => {
    ttsApi.health().then((h) => setAvailableKeys(h.available_keys)).catch(() => setAvailableKeys(0));
    ttsApi.listModels()
      .then((r) => setModels(r.models.filter((m) => m.can_do_text_to_speech)))
      .catch((e: unknown) => setError((e as Error).message));
  }, []);

  useEffect(() => {
    ttsApi.listVoices(voiceTypeFilter, 100, voiceCategoryFilter || undefined)
      .then((r) => setVoices(r.voices))
      .catch((e: unknown) => setError((e as Error).message));
  }, [voiceTypeFilter, voiceCategoryFilter]);

  useEffect(() => {
    if (models.length > 0 && !modelId) setModelId(models[0].model_id);
  }, [models]);

  useEffect(() => {
    if (voices.length > 0 && !voiceId) setVoiceId(voices[0].voice_id);
  }, [voices]);

  const loadHistory = (replace = true) => {
    setHistoryLoading(true);
    const cursor = replace ? undefined : (historyLastUnix ?? undefined);
    ttsApi.listHistory(20, undefined, cursor)
      .then((r) => {
        setHistory((prev) => replace ? r.history : [...prev, ...r.history]);
        setHistoryHasMore(r.has_more);
        setHistoryLastUnix(r.last_unix ?? null);
      })
      .catch((e: unknown) => setError((e as Error).message))
      .finally(() => setHistoryLoading(false));
  };

  const loadSubscription = () => {
    ttsApi.getUserSubscription()
      .then(setSubscription)
      .catch((e: unknown) => setError((e as Error).message));
  };

  useEffect(() => {
    if (tab === "history") loadHistory();
    if (tab === "subscription") loadSubscription();
  }, [tab]);

  // ── Generate ───────────────────────────────────────────────────────────────

  const generate = async () => {
    if (!text.trim()) return;
    setGenerating(true);
    setError(null);

    // Revoke previous blob URL để tránh leak
    if (audioUrl) URL.revokeObjectURL(audioUrl);
    setAudioUrl(null);

    try {
      const result = await ttsApi.generate({
        text: text.trim(),
        voice_id: voiceId,
        model_id: modelId,
        output_format: outputFormat,
        language_code: langCode || undefined,
        stability,
        similarity_boost: similarityBoost,
        style,
        use_speaker_boost: speakerBoost,
        speed,
        apply_text_normalization: normMode,
      });
      setAudioUrl(result.blobUrl);
      setLastMeta({
        account: result.usedAccount,
        requestId: result.requestId,
        chars: result.characterCount,
      });
      setTimeout(() => audioRef.current?.play(), 50);
      // Delay 2s để ElevenLabs kịp lưu item vào history trước khi fetch
      setTimeout(() => loadHistory(true), 2000);
      // Auto download nếu được bật
      if (autoDownload) {
        if (!downloadFolder) throw new Error("Auto download đang bật nhưng chưa chọn thư mục lưu");
        const ext = outputFormat.startsWith("mp3") ? "mp3" : outputFormat.startsWith("pcm") ? "pcm" : "audio";
        const ts = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
        const filename = `tts-${ts}.${ext}`;
        const savePath = `${downloadFolder}\\${filename}`;
        const buf = await fetch(result.blobUrl).then((r) => r.arrayBuffer());
        await writeFile(savePath, new Uint8Array(buf));
      }
    } catch (e: unknown) {
      setError((e as Error).message);
    } finally {
      setGenerating(false);
    }
  };

  // ── Voice list (filtered) ─────────────────────────────────────────────────

  const filteredVoices = voices.filter((v) => {
    if (voiceSearch && !v.name.toLowerCase().includes(voiceSearch.toLowerCase()) && !v.voice_id.includes(voiceSearch)) return false;
    if (voiceGenderFilter && (v.labels as Record<string, string>)?.gender?.toLowerCase() !== voiceGenderFilter) return false;
    if (voiceAccentFilter && (v.labels as Record<string, string>)?.accent?.toLowerCase() !== voiceAccentFilter.toLowerCase()) return false;
    return true;
  });

  const availableGenders = [...new Set(voices.map((v) => (v.labels as Record<string, string>)?.gender).filter(Boolean))];
  const availableAccents = [...new Set(voices.map((v) => (v.labels as Record<string, string>)?.accent).filter(Boolean))];

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">ElevenLabs TTS</h1>
          <p className="text-sm text-gray-500 mt-0.5">Text-to-Speech Proxy với round-robin key rotation</p>
        </div>
        <div className="flex items-center gap-3">
          {availableKeys !== null && (
            <Badge color={availableKeys > 0 ? "green" : "amber"}>
              {availableKeys > 0 ? `${availableKeys} keys available` : "No keys"}
            </Badge>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-gray-200">
        {(["generate", "voices", "history", "subscription"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors capitalize ${
              tab === t
                ? "border-violet-600 text-violet-700"
                : "border-transparent text-gray-500 hover:text-gray-800"
            }`}
          >
            {t === "generate" ? "Generate" : t === "subscription" ? "Subscription" : t.charAt(0).toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>

      {/* ── TAB: Generate ───────────────────────────────────────────────────── */}
      {tab === "generate" && (
        <div className="grid grid-cols-5 gap-6">
          {/* Left: Text + Controls */}
          <div className="col-span-3 space-y-4">
            {/* Text */}
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">
                Text <span className="text-gray-400">({text.length} ký tự)</span>
              </label>
              <textarea
                rows={6}
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder="Nhập text cần convert sang giọng nói..."
                className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-violet-400 resize-none"
              />
            </div>

            {/* Model + Voice */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Model</label>
                <select
                  value={modelId}
                  onChange={(e) => setModelId(e.target.value)}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-violet-400"
                >
                    {models.map((m) => (
                    <option key={m.model_id} value={m.model_id}>
                      {m.name} ({m.max_characters_request_subscribed_user?.toLocaleString() ?? "?"} chars)
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Voice</label>
                <select
                  value={voiceId}
                  onChange={(e) => setVoiceId(e.target.value)}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-violet-400"
                >
                  {voices.map((v) => (
                    <option key={v.voice_id} value={v.voice_id}>
                      {v.name}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* Format + Language */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Output Format</label>
                <select
                  value={outputFormat}
                  onChange={(e) => setOutputFormat(e.target.value)}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-violet-400"
                >
                  {OUTPUT_FORMATS.map((f) => (
                    <option key={f.value} value={f.value}>{f.label}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Language</label>
                <select
                  value={langCode}
                  onChange={(e) => setLangCode(e.target.value)}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-violet-400"
                >
                  {LANG_OPTIONS.map((l) => (
                    <option key={l.value} value={l.value}>{l.label}</option>
                  ))}
                </select>
              </div>
            </div>

            {/* Text normalization */}
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Text Normalization</label>
              <div className="flex gap-2">
                {(["auto", "on", "off"] as const).map((v) => (
                  <button
                    key={v}
                    onClick={() => setNormMode(v)}
                    className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                      normMode === v
                        ? "bg-violet-600 text-white"
                        : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                    }`}
                  >
                    {v}
                  </button>
                ))}
              </div>
            </div>

            {/* Generate button */}
            <button
              onClick={generate}
              disabled={generating || !text.trim() || availableKeys === 0}
              className="w-full py-2.5 rounded-lg bg-violet-600 hover:bg-violet-700 disabled:bg-violet-300 text-white text-sm font-semibold transition-colors flex items-center justify-center gap-2"
            >
              {generating ? (
                <>
                  <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  Generating...
                </>
              ) : (
                <>
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  Generate Speech
                </>
              )}
            </button>

            {/* Error */}
            {error && (
              <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
                {error}
              </div>
            )}

            {/* Audio player */}
            {audioUrl && (
              <div className="space-y-2">
                <audio
                  ref={audioRef}
                  src={audioUrl}
                  controls
                  className="w-full rounded-lg"
                />
                {lastMeta && (
                  <div className="flex flex-wrap gap-2 text-xs text-gray-500">
                    {lastMeta.account && <span>Account: <span className="text-gray-700 font-mono">{lastMeta.account}</span></span>}
                    {lastMeta.chars && <span>Chars: <span className="text-gray-700">{lastMeta.chars}</span></span>}
                    {lastMeta.requestId && <span className="truncate max-w-[200px]">ID: <span className="text-gray-700 font-mono">{lastMeta.requestId}</span></span>}
                  </div>
                )}
                <a
                  href={audioUrl}
                  download={`tts-${Date.now()}.${outputFormat.startsWith("mp3") ? "mp3" : outputFormat.startsWith("pcm") ? "pcm" : "audio"}`}
                  className="inline-flex items-center gap-1.5 text-xs text-violet-600 hover:underline"
                >
                  <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                  </svg>
                  Tải xuống
                </a>
              </div>
            )}
          </div>

          {/* Right: Voice Settings */}
          <div className="col-span-2 space-y-5">
            <div className="bg-white border border-gray-100 rounded-xl p-5 space-y-4 shadow-sm">
              <h3 className="text-sm font-semibold text-gray-800">Voice Settings</h3>
              <Slider label="Stability" value={stability} min={0} max={1} step={0.01} onChange={setStability} />
              <Slider label="Similarity Boost" value={similarityBoost} min={0} max={1} step={0.01} onChange={setSimilarityBoost} />
              <Slider label="Style" value={style} min={0} max={1} step={0.01} onChange={setStyle} />
              <Slider label="Speed" value={speed} min={0.7} max={1.2} step={0.05} onChange={setSpeed} />
              <div className="flex items-center justify-between">
                <span className="text-xs text-gray-500">Speaker Boost</span>
                <button
                  onClick={() => setSpeakerBoost((v) => !v)}
                  className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${speakerBoost ? "bg-violet-600" : "bg-gray-200"}`}
                >
                  <span className={`inline-block h-3.5 w-3.5 rounded-full bg-white shadow transition-transform ${speakerBoost ? "translate-x-5" : "translate-x-0.5"}`} />
                </button>
              </div>
            </div>

            {/* Auto Download config */}
            <div className="bg-white border border-gray-100 rounded-xl p-4 shadow-sm space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-gray-700">Auto Download</span>
                <button
                  onClick={() => setAutoDownload((v) => !v)}
                  className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${autoDownload ? "bg-violet-600" : "bg-gray-200"}`}
                >
                  <span className={`inline-block h-3.5 w-3.5 rounded-full bg-white shadow transition-transform ${autoDownload ? "translate-x-5" : "translate-x-0.5"}`} />
                </button>
              </div>
              {autoDownload && (
                <div className="flex items-center gap-2">
                  <span className="text-xs text-gray-500 flex-1 truncate font-mono" title={downloadFolder}>
                    {downloadFolder || <span className="text-red-500">Chưa chọn thư mục</span>}
                  </span>
                  <button
                    onClick={async () => {
                      const selected = await open({ directory: true, multiple: false, title: "Chọn thư mục lưu audio" });
                      if (typeof selected === "string" && selected) setDownloadFolder(selected);
                    }}
                    className="text-xs px-2 py-1 rounded-lg border border-gray-200 hover:bg-gray-50 text-gray-600 shrink-0"
                  >
                    Chọn folder
                  </button>
                </div>
              )}
            </div>

            {/* Preview voice */}
            {voiceId && voices.find((v) => v.voice_id === voiceId)?.preview_url && (
              <div className="bg-white border border-gray-100 rounded-xl p-4 shadow-sm">
                <p className="text-xs font-medium text-gray-600 mb-2">Preview Voice Gốc</p>
                <audio
                  src={voices.find((v) => v.voice_id === voiceId)?.preview_url}
                  controls
                  className="w-full"
                />
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── TAB: Voices ───────────────────────────────────────────────────── */}
      {tab === "voices" && (
        <div className="space-y-4">
          <div className="flex gap-2 flex-wrap">
            <input
              type="text"
              placeholder="Tìm voice..."
              value={voiceSearch}
              onChange={(e) => setVoiceSearch(e.target.value)}
              className="flex-1 min-w-[140px] border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-violet-400"
            />
            <select
              value={voiceTypeFilter}
              onChange={(e) => { setVoiceTypeFilter(e.target.value); setVoiceGenderFilter(""); setVoiceAccentFilter(""); }}
              className="border border-gray-200 rounded-lg px-2 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-violet-400"
            >
              {["default", "personal", "community", "workspace", "saved"].map((t) => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
            <select
              value={voiceCategoryFilter}
              onChange={(e) => setVoiceCategoryFilter(e.target.value)}
              className="border border-gray-200 rounded-lg px-2 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-violet-400"
            >
              <option value="">All categories</option>
              {["premade", "cloned", "generated", "professional"].map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
            {availableGenders.length > 0 && (
              <select
                value={voiceGenderFilter}
                onChange={(e) => setVoiceGenderFilter(e.target.value)}
                className="border border-gray-200 rounded-lg px-2 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-violet-400"
              >
                <option value="">All genders</option>
                {availableGenders.map((g) => (
                  <option key={g} value={g}>{g}</option>
                ))}
              </select>
            )}
            {availableAccents.length > 0 && (
              <select
                value={voiceAccentFilter}
                onChange={(e) => setVoiceAccentFilter(e.target.value)}
                className="border border-gray-200 rounded-lg px-2 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-violet-400"
              >
                <option value="">All accents</option>
                {availableAccents.map((a) => (
                  <option key={a} value={a}>{a}</option>
                ))}
              </select>
            )}
          </div>

          <div className="text-xs text-gray-500">{filteredVoices.length} voices</div>

          <div className="grid grid-cols-2 gap-3">
            {filteredVoices.map((v) => (
              <div
                key={v.voice_id}
                className={`bg-white border rounded-xl p-4 cursor-pointer transition-all hover:shadow-md ${
                  voiceId === v.voice_id
                    ? "border-violet-400 ring-1 ring-violet-300"
                    : "border-gray-100"
                }`}
                onClick={() => { setVoiceId(v.voice_id); setTab("generate"); }}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="font-medium text-sm text-gray-800 truncate">{v.name}</p>
                    <p className="text-[10px] text-gray-400 font-mono truncate">{v.voice_id}</p>
                    {v.description && (
                      <p className="text-xs text-gray-500 mt-1 line-clamp-2">{v.description}</p>
                    )}
                  </div>
                  <Badge color="violet">{v.category}</Badge>
                </div>
                {v.labels && Object.keys(v.labels).length > 0 && (
                  <div className="flex flex-wrap gap-1 mt-2">
                    {Object.entries(v.labels).slice(0, 3).map(([k, val]) => (
                      <span key={k} className="text-[10px] bg-gray-50 text-gray-500 px-1.5 py-0.5 rounded">
                        {val}
                      </span>
                    ))}
                  </div>
                )}
                {v.preview_url && (
                  <audio
                    src={v.preview_url}
                    controls
                    className="w-full mt-2 h-8"
                    onClick={(e) => e.stopPropagation()}
                  />
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── TAB: History ─────────────────────────────────────────────────── */}
      {tab === "history" && (
        <div className="space-y-3">
          <div className="flex justify-between items-center">
            <span className="text-sm text-gray-500">{history.length} items</span>
            <button
              onClick={() => loadHistory(true)}
              className="text-xs text-violet-600 hover:underline"
            >
              Refresh
            </button>
          </div>
          {history.length === 0 && (
            <p className="text-sm text-gray-400 text-center py-12">Chưa có history</p>
          )}
          <div className="space-y-2">
            {history.map((item) => (
              <div key={item.history_item_id} className="bg-white border border-gray-100 rounded-xl p-4 shadow-sm">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <p className="text-sm text-gray-700 line-clamp-2">{item.text}</p>
                    <div className="flex gap-3 mt-1.5 text-xs text-gray-400">
                      <span>{item.voice_name}</span>
                      <span className="text-violet-500 font-medium">−{item.character_count_change_to - item.character_count_change_from} chars</span>
                      <span>{new Date(item.date_unix * 1000).toLocaleString("vi-VN")}</span>
                      {item._account_email && <span className="font-mono truncate max-w-[160px]" title={item._account_email}>{item._account_email.split("@")[0]}</span>}
                    </div>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <audio
                      src={ttsApi.streamHistoryAudio(item.history_item_id, item._account_email)}
                      controls
                      preload="none"
                      className="h-8 w-40"
                    />
                    <button
                      onClick={async () => {
                        await ttsApi.deleteHistoryItem(item.history_item_id);
                        setHistory((h) => h.filter((x) => x.history_item_id !== item.history_item_id));
                      }}
                      className="text-red-400 hover:text-red-600 transition-colors"
                      title="Xóa"
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                      </svg>
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
          {historyHasMore && (
            <button
              onClick={() => loadHistory(false)}
              disabled={historyLoading}
              className="w-full py-2 text-sm text-violet-600 hover:underline disabled:opacity-50"
            >
              {historyLoading ? "Đang tải..." : "Load more"}
            </button>
          )}
        </div>
      )}

      {/* ── TAB: Subscription ────────────────────────────────────────────── */}
      {tab === "subscription" && (
        <div className="space-y-4">
          <button onClick={loadSubscription} className="text-xs text-violet-600 hover:underline">Refresh</button>
          {!subscription && (
            <p className="text-sm text-gray-400 text-center py-12">Loading...</p>
          )}
          {subscription && (
            <div className="bg-white border border-gray-100 rounded-xl p-5 shadow-sm space-y-3">
              {Object.entries(subscription).map(([k, v]) => (
                <div key={k} className="flex items-start justify-between gap-4 text-sm py-1 border-b border-gray-50 last:border-0">
                  <span className="text-gray-500 font-mono text-xs shrink-0">{k}</span>
                  <span className="text-gray-800 text-right break-all">
                    {k.includes("reset") && typeof v === "number"
                      ? new Date(v * 1000).toLocaleString("vi-VN")
                      : String(v ?? "—")}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
