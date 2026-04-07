import { useCallback, useEffect, useRef, useState } from "react";
import { aarApi, AAR_CONFIG_SECTIONS, AarConfig } from "../api/aar-client";

// ── ConfigField ───────────────────────────────────────────────────────────────

interface FieldDef {
  key: string;
  label: string;
  secret?: boolean;
  textarea?: boolean;
  hint?: string;
}

function ConfigField({
  def, value, onChange,
}: { def: FieldDef; value: string; onChange: (v: string) => void }) {
  const [show, setShow] = useState(false);
  const inputType = def.secret && !show ? "password" : "text";

  if (def.textarea) {
    return (
      <div className="space-y-1">
        <label className="block text-xs font-medium text-gray-700">{def.label}</label>
        {def.hint && <p className="text-xs text-gray-400">{def.hint}</p>}
        <div className="relative">
          <textarea
            rows={3}
            value={value}
            onChange={(e) => onChange(e.target.value)}
            placeholder={def.key}
            className="w-full text-xs font-mono rounded-lg border border-gray-200 bg-white px-3 py-2 pr-10 focus:outline-none focus:ring-2 focus:ring-indigo-400 resize-none"
            style={def.secret && !show ? { WebkitTextSecurity: "disc" } as React.CSSProperties : {}}
          />
          {def.secret && (
            <button
              type="button"
              onClick={() => setShow((s) => !s)}
              className="absolute top-2 right-2 text-gray-400 hover:text-gray-600 text-xs"
            >
              {show ? "Ẩn" : "Hiện"}
            </button>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-1">
      <label className="block text-xs font-medium text-gray-700">{def.label}</label>
      {def.hint && <p className="text-xs text-gray-400">{def.hint}</p>}
      <div className="relative">
        <input
          type={inputType}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={def.key}
          className="w-full text-sm rounded-lg border border-gray-200 bg-white px-3 py-2 pr-16 focus:outline-none focus:ring-2 focus:ring-indigo-400"
        />
        {def.secret && (
          <button
            type="button"
            onClick={() => setShow((s) => !s)}
            className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-gray-400 hover:text-gray-600 px-1"
          >
            {show ? "Ẩn" : "Hiện"}
          </button>
        )}
      </div>
    </div>
  );
}

// ── AppleMailSection ──────────────────────────────────────────────────────────

function AppleMailSection() {
  const fileRef = useRef<HTMLInputElement>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [pool, setPool]   = useState<{ count: number; emails: string[] } | null>(null);
  const [loadingPool, setLoadingPool] = useState(false);

  const loadPool = useCallback(() => {
    setLoadingPool(true);
    aarApi.getAppleMailPool()
      .then(setPool)
      .catch((e) => setStatus("Lỗi load pool: " + e.message))
      .finally(() => setLoadingPool(false));
  }, []);

  const handleImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setStatus("Đang import...");
    try {
      const result = await aarApi.importAppleMail(file);
      setStatus(`Import OK: ${JSON.stringify(result)}`);
      loadPool();
    } catch (err: unknown) {
      setStatus("Lỗi: " + (err instanceof Error ? err.message : String(err)));
    } finally {
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3">
        <button
          onClick={() => fileRef.current?.click()}
          className="btn btn-xs btn-secondary"
        >
          Import pool JSON
        </button>
        <button
          onClick={loadPool}
          disabled={loadingPool}
          className="btn btn-xs btn-secondary"
        >
          Xem pool
        </button>
        <input ref={fileRef} type="file" accept=".json" hidden onChange={handleImport} />
        {status && <span className="text-xs text-gray-500">{status}</span>}
      </div>
      {pool && (
        <div className="text-xs text-gray-600 bg-gray-50 rounded-lg p-3">
          <span className="font-semibold">{pool.count}</span> mailboxes trong pool
          {pool.emails.length > 0 && (
            <div className="mt-2 max-h-32 overflow-y-auto font-mono space-y-0.5">
              {pool.emails.slice(0, 50).map((e) => <div key={e}>{e}</div>)}
              {pool.emails.length > 50 && <div className="text-gray-400">... và {pool.emails.length - 50} email khác</div>}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function AarConfigPage() {
  const [config, setConfig]   = useState<AarConfig>({});
  const [draft,  setDraft]    = useState<AarConfig>({});
  const [loading, setLoading] = useState(true);
  const [saving,  setSaving]  = useState(false);
  const [toast,   setToast]   = useState<{ msg: string; ok: boolean } | null>(null);
  const [activeSection, setActiveSection] = useState(0);
  const [search, setSearch]   = useState("");

  useEffect(() => {
    aarApi.getConfig()
      .then((cfg) => { setConfig(cfg); setDraft(cfg); })
      .catch((e)  => setToast({ msg: e.message, ok: false }))
      .finally(()  => setLoading(false));
  }, []);

  const setField = useCallback((key: string, value: string) => {
    setDraft((prev) => ({ ...prev, [key]: value }));
  }, []);

  const handleSave = async () => {
    setSaving(true);
    try {
      // Chỉ gửi những key có thay đổi
      const changed: Record<string, string> = {};
      for (const [k, v] of Object.entries(draft)) {
        if (v !== (config[k] ?? "")) changed[k] = v;
      }
      if (Object.keys(changed).length === 0) {
        setToast({ msg: "Không có thay đổi", ok: true });
        return;
      }
      await aarApi.saveConfig(changed);
      setConfig({ ...config, ...changed });
      setToast({ msg: `Đã lưu ${Object.keys(changed).length} field`, ok: true });
    } catch (e: unknown) {
      setToast({ msg: (e instanceof Error ? e.message : String(e)), ok: false });
    } finally {
      setSaving(false);
    }
  };

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 3000);
    return () => clearTimeout(t);
  }, [toast]);

  // Filter sections bằng search
  const filteredSections = search.trim()
    ? AAR_CONFIG_SECTIONS.map((section) => ({
        ...section,
        keys: section.keys.filter(
          (f) =>
            f.key.toLowerCase().includes(search.toLowerCase()) ||
            f.label.toLowerCase().includes(search.toLowerCase())
        ),
      })).filter((s) => s.keys.length > 0)
    : AAR_CONFIG_SECTIONS;

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64 text-gray-400">
        Đang tải config...
      </div>
    );
  }

  const currentSection = filteredSections[activeSection] ?? filteredSections[0];

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-gray-900">AAR Config</h1>
          <p className="text-sm text-gray-500 mt-0.5">Cấu hình any-auto-register (smstome, mail providers, captcha...)</p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => { setDraft(config); setToast({ msg: "Đã reset", ok: true }); }}
            className="btn btn-secondary"
          >
            Reset
          </button>
          <button onClick={handleSave} disabled={saving} className="btn btn-primary">
            {saving ? "Đang lưu..." : "Lưu thay đổi"}
          </button>
        </div>
      </div>

      {/* Toast */}
      {toast && (
        <div className={`mb-4 px-4 py-2 rounded-lg text-sm font-medium ${toast.ok ? "bg-emerald-50 text-emerald-700 border border-emerald-200" : "bg-red-50 text-red-700 border border-red-200"}`}>
          {toast.msg}
        </div>
      )}

      <div className="flex gap-6 flex-1 min-h-0">
        {/* Sidebar sections */}
        <div className="w-48 flex-shrink-0 flex flex-col gap-1">
          <input
            type="text"
            value={search}
            onChange={(e) => { setSearch(e.target.value); setActiveSection(0); }}
            placeholder="Tìm config..."
            className="mb-2 w-full text-xs rounded-lg border border-gray-200 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-400"
          />
          <div className="flex-1 overflow-y-auto space-y-0.5">
            {filteredSections.map((section, i) => (
              <button
                key={section.label}
                onClick={() => setActiveSection(i)}
                className={`w-full text-left text-xs px-3 py-2 rounded-lg transition-colors ${
                  activeSection === i
                    ? "bg-indigo-50 text-indigo-700 font-semibold"
                    : "text-gray-600 hover:bg-gray-50"
                }`}
              >
                {section.label}
              </button>
            ))}
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto">
          {currentSection ? (
            <div className="card p-6">
              <h2 className="text-base font-semibold text-gray-900 mb-4">{currentSection.label}</h2>
              {currentSection.label === "AppleMail" && (
                <div className="mb-4 pb-4 border-b border-gray-100">
                  <h3 className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">Pool Management</h3>
                  <AppleMailSection />
                </div>
              )}
              <div className="grid grid-cols-1 gap-4">
                {currentSection.keys.map((def) => (
                  <ConfigField
                    key={def.key}
                    def={def}
                    value={draft[def.key] ?? ""}
                    onChange={(v) => setField(def.key, v)}
                  />
                ))}
              </div>
            </div>
          ) : (
            <div className="text-gray-400 text-sm">Không tìm thấy config nào</div>
          )}
        </div>
      </div>
    </div>
  );
}
