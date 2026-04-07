
import { useEffect, useState, useMemo } from "react";
import { api, MailProvider } from "../api/client";

const PAGE_SIZE = 20;

const PROVIDER_META: Record<string, { color: string; dot: string }> = {
  "mail.tm":           { color: "bg-blue-50 text-blue-700 border-blue-200",       dot: "bg-blue-500" },
  "mailslurp.com":     { color: "bg-violet-50 text-violet-700 border-violet-200", dot: "bg-violet-500" },
  "testmail.app":      { color: "bg-amber-50 text-amber-700 border-amber-200",    dot: "bg-amber-500" },
  "guerrillamail.com": { color: "bg-emerald-50 text-emerald-700 border-emerald-200", dot: "bg-emerald-500" },
  "mailosaur.com":     { color: "bg-rose-50 text-rose-700 border-rose-200",       dot: "bg-rose-500" },
  "gmail.com":         { color: "bg-red-50 text-red-700 border-red-200",          dot: "bg-red-500" },
};

const maskKey = (key: string) =>
  key.length > 12 ? `${key.slice(0, 4)}${"•".repeat(8)}${key.slice(-6)}` : key || "—";

function ProviderBadge({ type }: { type: string }) {
  const meta = PROVIDER_META[type] ?? { color: "bg-gray-50 text-gray-600 border-gray-200", dot: "bg-gray-400" };
  return (
    <span className={`inline-flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1 rounded-full border ${meta.color}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${meta.dot}`} />
      {type}
    </span>
  );
}

function ActiveToggle({ active, onChange }: { active: boolean; onChange: () => void }) {
  return (
    <button
      onClick={onChange}
      className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 transition-colors duration-200 focus:outline-none ${
        active ? "bg-brand-600 border-brand-600" : "bg-gray-200 border-gray-200"
      }`}
    >
      <span
        className={`pointer-events-none inline-block h-4 w-4 rounded-full bg-white shadow transform transition-transform duration-200 ${
          active ? "translate-x-4" : "translate-x-0"
        }`}
      />
    </button>
  );
}

export default function ProviderKeyTable() {
  const [providers, setProviders] = useState<MailProvider[]>([]);
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [search, setSearch] = useState("");
  const [type, setType] = useState<string>("");
  const [statusFilter, setStatusFilter] = useState<"all" | "active" | "disabled">("all");
  const [page, setPage] = useState(1);

  const load = () => {
    setLoading(true);
    api.getAllProviders()
      .then(setProviders)
      .catch((e) => setMsg({ ok: false, text: e.message }))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const types = useMemo(() => Array.from(new Set(providers.map((p) => p.provider_type))).sort(), [providers]);

  const filtered = useMemo(() => {
    let arr = providers;
    if (type) arr = arr.filter((p) => p.provider_type === type);
    if (statusFilter === "active") arr = arr.filter((p) => !p.disabled);
    if (statusFilter === "disabled") arr = arr.filter((p) => p.disabled);
    if (search.trim()) {
      const q = search.trim().toLowerCase();
      arr = arr.filter((p) =>
        p.api_key.toLowerCase().includes(q) ||
        (p.label?.toLowerCase().includes(q) ?? false) ||
        (p.server_id?.toLowerCase().includes(q) ?? false) ||
        p.provider_type.toLowerCase().includes(q)
      );
    }
    return arr;
  }, [providers, type, statusFilter, search]);

  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const safePage = Math.min(page, pageCount);
  const paged = filtered.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE);
  const activeCount = useMemo(() => providers.filter((p) => !p.disabled).length, [providers]);

  const handleToggle = async (p: MailProvider) => {
    try {
      await api.updateProvider(p.id, { disabled: !p.disabled });
      setProviders((prev) => prev.map((x) => x.id === p.id ? { ...x, disabled: !x.disabled } : x));
    } catch (e: any) {
      setMsg({ ok: false, text: e.message });
    }
  };

  return (
    <div className="flex flex-col gap-4">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold text-gray-900">Provider Keys</h2>
          <p className="text-xs text-gray-500 mt-0.5">
            <span className="text-brand-600 font-semibold">{activeCount}/{providers.length}</span> active · Uncheck để disable key
          </p>
        </div>
        <button onClick={load} className="btn-secondary py-1.5 text-xs self-start sm:self-auto">
          <svg className="w-3.5 h-3.5" viewBox="0 0 20 20" fill="currentColor">
            <path fillRule="evenodd" d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z" clipRule="evenodd" />
          </svg>
          Refresh
        </button>
      </div>

      {/* Filters bar */}
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative flex-1 min-w-[200px] max-w-xs">
          <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 pointer-events-none" viewBox="0 0 20 20" fill="currentColor">
            <path fillRule="evenodd" d="M8 4a4 4 0 100 8 4 4 0 000-8zM2 8a6 6 0 1110.89 3.476l4.817 4.817a1 1 0 01-1.414 1.414l-4.816-4.816A6 6 0 012 8z" clipRule="evenodd" />
          </svg>
          <input
            className="input w-full pl-9 py-1.5 text-sm"
            placeholder="Tìm key, label, server ID..."
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1); }}
          />
          {search && (
            <button
              onClick={() => { setSearch(""); setPage(1); }}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
            >
              <svg className="w-3.5 h-3.5" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
              </svg>
            </button>
          )}
        </div>

        <select
          className="input py-1.5 text-sm w-44"
          value={type}
          onChange={(e) => { setType(e.target.value); setPage(1); }}
        >
          <option value="">Tất cả loại</option>
          {types.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>

        <div className="flex items-center gap-1 bg-gray-100 rounded-lg p-0.5">
          {(["all", "active", "disabled"] as const).map((s) => (
            <button
              key={s}
              onClick={() => { setStatusFilter(s); setPage(1); }}
              className={`px-3 py-1 text-xs font-medium rounded-md transition-all ${
                statusFilter === s ? "bg-white text-gray-900 shadow-sm" : "text-gray-500 hover:text-gray-700"
              }`}
            >
              {s === "all" ? "Tất cả" : s === "active" ? "Active" : "Disabled"}
            </button>
          ))}
        </div>

        <span className="text-xs text-gray-400 ml-auto">{filtered.length} kết quả</span>
      </div>

      {msg && (
        <div className={`flex items-center gap-2 text-xs font-semibold px-3 py-2 rounded-lg ${msg.ok ? "bg-emerald-50 text-emerald-700" : "bg-red-50 text-red-600"}`}>
          {msg.ok ? "✓" : "✕"} {msg.text}
        </div>
      )}

      {/* Table */}
      <div className="card overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center py-16 gap-2 text-sm text-gray-400">
            <svg className="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            Đang tải…
          </div>
        ) : paged.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 gap-2">
            <svg className="w-8 h-8 text-gray-300" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M8 4a4 4 0 100 8 4 4 0 000-8zM2 8a6 6 0 1110.89 3.476l4.817 4.817a1 1 0 01-1.414 1.414l-4.816-4.816A6 6 0 012 8z" clipRule="evenodd" />
            </svg>
            <p className="text-sm text-gray-400">Không có key nào phù hợp</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] text-sm">
              <thead>
                <tr className="border-b border-gray-100 bg-gray-50/80">
                  <th className="py-3 px-4 text-left text-[11px] font-semibold text-gray-400 uppercase tracking-wider w-40">Type</th>
                  <th className="py-3 px-4 text-left text-[11px] font-semibold text-gray-400 uppercase tracking-wider w-52">API Key</th>
                  <th className="py-3 px-4 text-left text-[11px] font-semibold text-gray-400 uppercase tracking-wider w-40">Server ID</th>
                  <th className="py-3 px-4 text-left text-[11px] font-semibold text-gray-400 uppercase tracking-wider">Label</th>
                  <th className="py-3 px-4 text-center text-[11px] font-semibold text-gray-400 uppercase tracking-wider w-16">Fails</th>
                  <th className="py-3 px-4 text-center text-[11px] font-semibold text-gray-400 uppercase tracking-wider w-20">Active</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {paged.map((p) => (
                  <tr
                    key={p.id}
                    className={`transition-colors ${p.disabled ? "opacity-40 bg-gray-50/50" : "hover:bg-blue-50/30"}`}
                  >
                    <td className="py-3 px-4">
                      <ProviderBadge type={p.provider_type} />
                    </td>
                    <td className="py-3 px-4">
                      <span className="font-mono text-xs text-gray-600 bg-gray-50 px-2 py-1 rounded-md border border-gray-100 select-all" title={p.api_key}>
                        {maskKey(p.api_key)}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-xs text-gray-500 max-w-[160px]">
                      <span className="truncate block" title={p.server_id ?? ""}>
                        {p.server_id || <span className="text-gray-300">—</span>}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-xs text-gray-500 max-w-[160px]">
                      <span className="truncate block" title={p.label ?? ""}>
                        {p.label || <span className="text-gray-300">—</span>}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-center">
                      {p.fail_count > 0 ? (
                        <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-red-100 text-red-600 text-[11px] font-bold">
                          {p.fail_count}
                        </span>
                      ) : (
                        <span className="text-xs text-gray-300">—</span>
                      )}
                    </td>
                    <td className="py-3 px-4 text-center">
                      <ActiveToggle active={!p.disabled} onChange={() => handleToggle(p)} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Pagination */}
      {pageCount > 1 && (
        <div className="flex items-center justify-between">
          <span className="text-xs text-gray-400">
            Trang {safePage}/{pageCount} · {filtered.length} keys
          </span>
          <div className="flex items-center gap-1">
            <button className="btn-secondary px-2.5 py-1.5 text-xs disabled:opacity-40" disabled={safePage === 1} onClick={() => setPage(1)}>«</button>
            <button className="btn-secondary px-2.5 py-1.5 text-xs disabled:opacity-40" disabled={safePage === 1} onClick={() => setPage(safePage - 1)}>‹</button>
            {Array.from({ length: pageCount }, (_, i) => i + 1)
              .filter((p) => Math.abs(p - safePage) <= 2 || p === 1 || p === pageCount)
              .reduce<(number | "...")[]>((acc, p, i, arr) => {
                if (i > 0 && (p as number) - (arr[i - 1] as number) > 1) acc.push("...");
                acc.push(p);
                return acc;
              }, [])
              .map((item, i) =>
                item === "..." ? (
                  <span key={`e-${i}`} className="px-1.5 text-xs text-gray-400">…</span>
                ) : (
                  <button
                    key={item}
                    onClick={() => setPage(item as number)}
                    className={`min-w-[28px] px-2 py-1.5 text-xs rounded-lg transition-all ${
                      safePage === item ? "bg-brand-600 text-white font-semibold shadow-sm" : "btn-secondary"
                    }`}
                  >
                    {item}
                  </button>
                )
              )}
            <button className="btn-secondary px-2.5 py-1.5 text-xs disabled:opacity-40" disabled={safePage === pageCount} onClick={() => setPage(safePage + 1)}>›</button>
            <button className="btn-secondary px-2.5 py-1.5 text-xs disabled:opacity-40" disabled={safePage === pageCount} onClick={() => setPage(pageCount)}>»</button>
          </div>
        </div>
      )}
    </div>
  );
}
