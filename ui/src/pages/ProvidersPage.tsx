import { useEffect, useState, useCallback } from "react";
import { api, MailProviderDomain, MailProvider } from "../api/client";

// Display names cho service — optional, fallback về tên gốc khi không có mapping
const SERVICE_LABELS: Record<string, string> = {
  chatgpt:            "ChatGPT",
  elevenlabs:         "ElevenLabs",
  openrouter:         "OpenRouter",
  leonardo:           "Leonardo",
  klingai:            "KlingAI",
  "2slides":          "2Slides",
  testmail:           "Testmail",
  mailosaur:          "Mailosaur",
  artificialanalysis: "ArtAnalysis",
};

const labelFor = (svc: string) =>
  SERVICE_LABELS[svc.toLowerCase()] ?? svc;

const DOMAIN_COLORS: Record<string, string> = {
  "mail.tm":          "bg-blue-100 text-blue-700",
  "mailslurp.com":    "bg-violet-100 text-violet-700",
  "testmail.app":     "bg-amber-100 text-amber-700",
  "guerrillamail.com":"bg-green-100 text-green-700",
  "mailosaur.com":    "bg-rose-100 text-rose-700",
  "gmail.com":        "bg-red-100 text-red-600",
};

const maskKey = (key: string) =>
  key.length > 8 ? `...${key.slice(-8)}` : key || "—";

function TriStateCell({
  checked,
  blocked,
  onClick,
}: {
  checked: boolean;
  blocked: boolean;
  onClick: () => void;
}) {
  if (blocked) {
    return (
      <button
        onClick={onClick}
        title="Không tương thích — click để bỏ"
        className="w-[18px] h-[18px] rounded flex items-center justify-center bg-red-100 border border-red-400 hover:bg-red-200 transition-colors cursor-pointer mx-auto"
      >
        <svg viewBox="0 0 12 12" className="w-2.5 h-2.5 text-red-600 fill-none stroke-current stroke-[2.5]">
          <line x1="2" y1="2" x2="10" y2="10" />
          <line x1="10" y1="2" x2="2" y2="10" />
        </svg>
      </button>
    );
  }
  if (checked) {
    return (
      <button
        onClick={onClick}
        title="Đang dùng — click để chuyển sang blocked"
        className="w-[18px] h-[18px] rounded flex items-center justify-center bg-brand-600 border border-brand-600 hover:bg-brand-700 transition-colors cursor-pointer mx-auto"
      >
        <svg viewBox="0 0 12 12" className="w-2.5 h-2.5 text-white fill-none stroke-current stroke-[2.5]">
          <polyline points="2,6 5,9 10,3" />
        </svg>
      </button>
    );
  }
  return (
    <button
      onClick={onClick}
      title="Chưa dùng — click để bật"
      className="w-[18px] h-[18px] rounded border border-gray-300 bg-white hover:border-brand-400 hover:bg-brand-50 transition-colors cursor-pointer mx-auto"
    />
  );
}

export default function ProvidersPage() {
  const [rows, setRows] = useState<MailProviderDomain[]>([]);
  const [providers, setProviders] = useState<MailProvider[]>([]);
  const [services, setServices] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [_saving, setSaving] = useState<Record<string, boolean>>({});

  const load = useCallback(() => {
    setLoading(true);
    Promise.all([api.getProviders(), api.getAllProviders(), api.getServices()])
      .then(([domains, all, svcList]) => {
        setRows(domains);
        setProviders(all);
        setServices(svcList);
      })
      .catch((e) => setMsg({ ok: false, text: e.message }))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  const getTags = (domain: string) => rows.find((r) => r.domain === domain)?.tags ?? [];

  const isChecked = (domain: string, svc: string) =>
    getTags(domain).includes(svc.toLowerCase());

  const isBlocked = (domain: string, svc: string) =>
    getTags(domain).includes(`${svc.toLowerCase()}:blocked`);

  const toggle = async (domain: string, svc: string) => {
    setSaving((prev) => ({ ...prev, [domain]: true }));
    try {
      const { tags } = await api.cycleProviderTag(domain, svc.toLowerCase());
      setRows((prev) => prev.map((r) => r.domain === domain ? { ...r, tags } : r));
    } catch (e: any) {
      setMsg({ ok: false, text: e.message });
    } finally {
      setSaving((prev) => ({ ...prev, [domain]: false }));
    }
  };

  const toggleDisabled = async (p: MailProvider) => {
    try {
      await api.updateProvider(p.id, { disabled: !p.disabled });
      // Reload từ BE — không tự mutate local state
      load();
    } catch (e: any) {
      setMsg({ ok: false, text: e.message });
    }
  };

  const activeCount = providers.filter((p) => !p.disabled).length;

  return (
    <div>
      <div className="flex items-center justify-between mb-5">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Mail Providers</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Tick service cần dùng. Auto-save khi tick. Keys round-robin tự động.
          </p>
        </div>
        <div className="flex items-center gap-3">
          {msg && (
            <span className={`text-xs font-semibold ${msg.ok ? "text-emerald-600" : "text-red-500"}`}>
              {msg.ok ? "✓ " : "✕ "}{msg.text}
            </span>
          )}
          <button onClick={load} className="btn-primary py-1.5 text-xs">Refresh</button>
        </div>
      </div>

      {loading ? (
        <div className="text-sm text-gray-400 py-12 text-center">Loading…</div>
      ) : (
        <>
          {/* ── Tag assignment matrix ─────────────────────────── */}
          <div className="card">
            <table className="w-full table-fixed text-sm">
              <thead>
                <tr className="border-b border-gray-200 bg-gray-50/60">
                  <th className="py-3 px-5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide w-40">
                    Service
                  </th>
                  {rows.map((r) => (
                    <th key={r.domain} className="py-3 px-4 text-center">
                      <div className="flex flex-col items-center gap-1.5">
                        <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${DOMAIN_COLORS[r.domain] ?? "bg-gray-100 text-gray-600"}`}>
                          {r.domain}
                        </span>
                        <span className="text-[10px] text-gray-400">
                          {r.active}/{r.total} keys
                          
                        </span>
                      </div>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {services.map((svc) => (
                  <tr key={svc} className="border-b border-gray-100 last:border-0 hover:bg-gray-50/40">
                    <td className="py-3 px-5 text-sm font-medium text-gray-700">
                      {labelFor(svc)}
                    </td>
                    {rows.map((r) => (
                      <td key={r.domain} className="py-3 px-4 text-center">
                        <TriStateCell
                          checked={isChecked(r.domain, svc)}
                          blocked={isBlocked(r.domain, svc)}
                          onClick={() => toggle(r.domain, svc)}
                        />
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* ── Individual provider keys ──────────────────────── */}
          {providers.length > 0 && (
            <div className="mt-8">
              <div className="flex items-center justify-between mb-3">
                <div>
                  <h2 className="text-lg font-semibold text-gray-900">Provider Keys</h2>
                  <p className="text-xs text-gray-500 mt-0.5">
                    {activeCount}/{providers.length} active · Uncheck để disable key
                  </p>
                </div>
              </div>
              <div className="card">
                <table className="w-full table-fixed text-sm">
                  <colgroup>
                    <col className="w-24" />
                    <col className="w-56" />
                    <col className="w-36" />
                    <col />
                    <col className="w-16" />
                    <col className="w-16" />
                  </colgroup>
                  <thead>
                    <tr className="border-b border-gray-200 bg-gray-50/60">
                      <th className="py-3 px-4 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">Type</th>
                      <th className="py-3 px-4 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">Key</th>
                      <th className="py-3 px-4 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">Server ID</th>
                      <th className="py-3 px-4 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">Label</th>
                      <th className="py-3 px-4 text-center text-xs font-semibold text-gray-500 uppercase tracking-wide">Fails</th>
                      <th className="py-3 px-4 text-center text-xs font-semibold text-gray-500 uppercase tracking-wide">Active</th>
                    </tr>
                  </thead>
                  <tbody>
                    {providers.map((p) => (
                      <tr
                        key={p.id}
                        className={`border-b border-gray-100 last:border-0 transition-opacity ${p.disabled ? "opacity-40" : "hover:bg-gray-50/40"}`}
                      >
                        <td className="py-2.5 px-4">
                          <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${DOMAIN_COLORS[p.provider_type] ?? "bg-gray-100 text-gray-600"}`}>
                            {p.provider_type}
                          </span>
                        </td>
                        <td className="py-2.5 px-4 font-mono text-xs text-gray-600 truncate" title={p.api_key}>
                          {maskKey(p.api_key)}
                        </td>
                        <td className="py-2.5 px-4 text-xs text-gray-500 truncate" title={p.server_id ?? ""}>
                          {p.server_id || <span className="text-gray-300">—</span>}
                        </td>
                        <td className="py-2.5 px-4 text-xs text-gray-500 truncate" title={p.label ?? ""}>
                          {p.label || <span className="text-gray-300">—</span>}
                        </td>
                        <td className="py-2.5 px-4 text-center">
                          {p.fail_count > 0 ? (
                            <span className="text-xs font-semibold text-red-500">{p.fail_count}</span>
                          ) : (
                            <span className="text-xs text-gray-300">0</span>
                          )}
                        </td>
                        <td className="py-2.5 px-4 text-center">
                          <input
                            type="checkbox"
                            checked={!p.disabled}
                            onChange={() => toggleDisabled(p)}
                            className="w-4 h-4 rounded accent-brand-600 cursor-pointer"
                          />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
