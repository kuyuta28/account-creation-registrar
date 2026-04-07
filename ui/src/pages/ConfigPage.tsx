import { useEffect, useState } from "react";
import { api } from "../api/client";
import ConfigFormEditor from "../components/ConfigFormEditor";

type Tab = "ui" | "raw";

const FILE_LABELS: Record<string, string> = {
  "config.yaml":     "Core",
  "mail.yaml":       "Mail",
  "captcha.yaml":    "Captcha",
  "elevenlabs.yaml": "ElevenLabs",
  "openrouter.yaml": "OpenRouter",
  "chatgpt.yaml":    "ChatGPT",
  "leonardo.yaml":   "Leonardo",
  "klingai.yaml":    "KlingAI",
  "twoslides.yaml":  "2Slides",
  "testmail.yaml":   "Testmail",
  "artificialanalysis.yaml": "Artificial Analysis",
};

const FILE_ICONS: Record<string, string> = {
  "config.yaml":     "⚙️",
  "mail.yaml":       "✉️",
  "captcha.yaml":    "🔒",
  "elevenlabs.yaml": "🎙️",
  "openrouter.yaml": "🔀",
  "chatgpt.yaml":    "🤖",
  "leonardo.yaml":   "🎨",
  "klingai.yaml":    "🎬",
  "twoslides.yaml":  "📊",
  "testmail.yaml":   "📬",
  "artificialanalysis.yaml": "🧪",
};

export default function ConfigPage() {
  const [files, setFiles] = useState<string[]>([]);
  const [activeFile, setActiveFile] = useState("config.yaml");
  const [content, setContent] = useState("");
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [showAddKey, setShowAddKey] = useState(false);
  const [newKey, setNewKey] = useState("");
  const [addingKey, setAddingKey] = useState(false);
  const [tab, setTab] = useState<Tab>("ui");

  useEffect(() => {
    api.listConfigFiles().then(({ files: f }) => setFiles(f)).catch(console.error);
  }, []);

  useEffect(() => {
    setLoading(true);
    setMsg(null);
    api
      .getConfigRaw(activeFile)
      .then(({ content: c }) => setContent(c))
      .catch((err) => setMsg({ ok: false, text: String(err) }))
      .finally(() => setLoading(false));
  }, [activeFile]);

  const save = () => {
    setSaving(true);
    setMsg(null);
    api
      .saveConfigRaw(content, activeFile)
      .then(() => setMsg({ ok: true, text: "Đã lưu thành công!" }))
      .catch((err) => setMsg({ ok: false, text: `Lỗi khi lưu: ${err instanceof Error ? err.message : String(err)}` }))
      .finally(() => setSaving(false));
  };

  const addKey = () => {
    const key = newKey.trim();
    if (!key) return;
    setAddingKey(true);
    api
      .addMailSlurpKey(key)
      .then(({ total }) => {
        setMsg({ ok: true, text: `Đã thêm key! Tổng: ${total}` });
        setNewKey("");
        setShowAddKey(false);
        // Reload mail.yaml content
        api.getConfigRaw("mail.yaml").then(({ content: c }) => setContent(c)).catch(console.error);
      })
      .catch((err) => setMsg({ ok: false, text: `Lỗi thêm key: ${err instanceof Error ? err.message : String(err)}` }))
      .finally(() => setAddingKey(false));
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-5">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Config</h1>
          <p className="text-sm text-gray-500 mt-0.5">Chỉnh sửa config/ files</p>
        </div>
      </div>

      <div className="card overflow-hidden" style={{ height: "calc(100vh - 180px)" }}>
        <div className="grid grid-cols-[200px_1fr] h-full">
          {/* Left: file list */}
          <div className="border-r border-gray-100 bg-gray-50/50 flex flex-col overflow-y-auto">
            {(files.length ? files.filter((f) => f in FILE_LABELS) : Object.keys(FILE_LABELS)).map((f) => (
              <button
                key={f}
                onClick={() => setActiveFile(f)}
                className={`flex items-center gap-3 px-4 py-3.5 w-full text-left border-b border-b-gray-100 border-l-[3px] transition-colors ${
                  activeFile === f
                    ? "bg-white border-l-brand-500 text-gray-900"
                    : "border-l-transparent text-gray-500 hover:bg-white/70 hover:text-gray-800"
                }`}
              >
                <span className="text-base leading-none shrink-0">{FILE_ICONS[f] ?? "📄"}</span>
                <div className="min-w-0">
                  <p className="text-sm font-medium">{FILE_LABELS[f] ?? f}</p>
                  <p className="text-[10px] text-gray-400 font-mono">{f}</p>
                </div>
              </button>
            ))}
          </div>

          {/* Right: editor */}
          <div className="flex flex-col">
            {/* Toolbar */}
            <div className="flex items-center justify-between px-4 py-2 border-b border-gray-100 bg-gray-50/40 shrink-0">
              <div className="flex items-center gap-3">
                <span className="text-xs font-mono text-gray-400">{activeFile}</span>

                {/* Tab switcher */}
                <div className="flex items-center bg-gray-100 rounded-md p-0.5">
                  <button
                    onClick={() => setTab("ui")}
                    className={`px-3 py-1 text-xs font-medium rounded transition-colors ${
                      tab === "ui"
                        ? "bg-white text-gray-900 shadow-sm"
                        : "text-gray-500 hover:text-gray-700"
                    }`}
                  >
                    UI
                  </button>
                  <button
                    onClick={() => setTab("raw")}
                    className={`px-3 py-1 text-xs font-medium rounded transition-colors ${
                      tab === "raw"
                        ? "bg-white text-gray-900 shadow-sm"
                        : "text-gray-500 hover:text-gray-700"
                    }`}
                  >
                    Raw
                  </button>
                </div>

                {msg && (
                  <span className={`flex items-center gap-1.5 text-xs font-semibold ${msg.ok ? "text-emerald-600" : "text-red-500"}`}>
                    {msg.ok ? "✓ Saved" : "✕ " + msg.text}
                  </span>
                )}
              </div>
              <div className="flex items-center gap-2">
                {activeFile === "mail.yaml" && (
                  <button
                    onClick={() => setShowAddKey(!showAddKey)}
                    className="btn-primary py-1.5 text-xs gap-1.5 bg-emerald-600 hover:bg-emerald-700"
                  >
                    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                    </svg>
                    Add Key
                  </button>
                )}
                <button onClick={save} disabled={saving || loading} className="btn-primary py-1.5 text-xs gap-1.5">
                  {saving ? (
                    <>
                      <svg className="w-3.5 h-3.5 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                      </svg>
                      Saving…
                    </>
                  ) : (
                    <>
                      <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-3m-1 4l-3 3m0 0l-3-3m3 3V4" />
                      </svg>
                      Save
                    </>
                  )}
                </button>
              </div>
            </div>

            {/* Add MailSlurp Key inline form */}
            {showAddKey && activeFile === "mail.yaml" && (
              <div className="flex items-center gap-2 px-4 py-2 border-b border-gray-100 bg-emerald-50/60 shrink-0">
                <span className="text-xs text-gray-500 whitespace-nowrap">MailSlurp Key:</span>
                <input
                  type="text"
                  value={newKey}
                  onChange={(e) => setNewKey(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && addKey()}
                  placeholder="sk_..."
                  className="flex-1 text-xs font-mono px-2 py-1.5 border border-gray-200 rounded focus:outline-none focus:border-brand-400"
                />
                <button
                  onClick={addKey}
                  disabled={addingKey || !newKey.trim()}
                  className="btn-primary py-1.5 text-xs bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50"
                >
                  {addingKey ? "Adding…" : "Add"}
                </button>
                <button
                  onClick={() => { setShowAddKey(false); setNewKey(""); }}
                  className="text-gray-400 hover:text-gray-600 text-xs px-1"
                >
                  ✕
                </button>
              </div>
            )}

            {/* Content area */}
            {loading ? (
              <div className="flex-1 flex items-center justify-center">
                <svg className="w-6 h-6 animate-spin text-brand-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
              </div>
            ) : tab === "ui" ? (
              <ConfigFormEditor content={content} onChange={setContent} />
            ) : (
              <textarea
                value={content}
                onChange={(e) => setContent(e.target.value)}
                spellCheck={false}
                className="flex-1 min-h-0 bg-white text-gray-800 p-5 font-mono text-xs leading-relaxed focus:outline-none resize-none"
              />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
