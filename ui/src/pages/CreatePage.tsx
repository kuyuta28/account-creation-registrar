import { useCallback, useEffect, useRef, useState } from "react";
import { api, Job, wsLogs, _API_ORIGIN } from "../api/client";

// ── Per-service config persistence ───────────────────────────────────
const SVC_CFG_KEY = "acc-creator:svc-cfg";
type SvcCfg = { count: number; workers: number };

const loadSvcCfg = (svc: string): SvcCfg => {
  try {
    const all = JSON.parse(localStorage.getItem(SVC_CFG_KEY) ?? "{}") as Record<string, SvcCfg>;
    return all[svc] ?? { count: 1, workers: 1 };
  } catch (_) { console.warn("loadSvcCfg parse error", _); return { count: 1, workers: 1 }; }
};

const saveSvcCfg = (svc: string, cfg: SvcCfg) => {
  try {
    const all = JSON.parse(localStorage.getItem(SVC_CFG_KEY) ?? "{}") as Record<string, SvcCfg>;
    localStorage.setItem(SVC_CFG_KEY, JSON.stringify({ ...all, [svc]: cfg }));
  } catch (_) { console.warn("saveSvcCfg error", _); }
};

// ── Constants ─────────────────────────────────────────────────────────
const STATUS_STYLE: Record<string, { badge: string; dot: string; bar: string; ring: string }> = {
  pending: { badge: "bg-gray-100 text-gray-500",                               dot: "bg-gray-300",                bar: "bg-gray-300",    ring: "ring-gray-200" },
  running: { badge: "bg-amber-50 text-amber-600 border border-amber-200",      dot: "bg-amber-400 animate-pulse", bar: "bg-amber-400",   ring: "ring-amber-200" },
  done:    { badge: "bg-emerald-50 text-emerald-700 border border-emerald-200", dot: "bg-emerald-500",             bar: "bg-emerald-500", ring: "ring-emerald-200" },
  stopped: { badge: "bg-slate-50 text-slate-600 border border-slate-200",       dot: "bg-slate-400",               bar: "bg-slate-400",   ring: "ring-slate-200" },
  failed:  { badge: "bg-red-50 text-red-600 border border-red-200",            dot: "bg-red-400",                 bar: "bg-red-400",     ring: "ring-red-200"  },
};

interface ActiveJob { job: Job; logs: string[]; expanded: boolean; }

// ── LogPanel ──────────────────────────────────────────────────────────
export function LogPanel({ logs, compact, error }: { logs: string[]; compact?: boolean; error?: string | null }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const endRef       = useRef<HTMLDivElement>(null);
  const [pinned, setPinned] = useState(true);

  useEffect(() => {
    if (pinned) endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs, pinned]);

  const onScroll = () => {
    const el = containerRef.current;
    if (!el) return;
    setPinned(el.scrollHeight - el.scrollTop - el.clientHeight < 40);
  };

  return (
    <div className="relative">
      <div
        ref={containerRef} onScroll={onScroll}
        className={`overflow-y-auto p-3 font-mono text-xs bg-gray-950 text-gray-300 leading-5 ${compact ? "h-36" : "h-52"}`}
      >
        {logs.length === 0
          ? <span className={error ? "text-red-400" : "text-gray-600"}>{error || "Đợi logs..."}</span>
          : logs.map((line, i) => (
            <div key={i} className={`whitespace-pre-wrap ${
              line.includes("❌") || line.includes("ERROR") ? "text-red-400" :
              line.includes("✅") || line.includes("✓")    ? "text-emerald-400" :
              line.includes("⚠️")                          ? "text-amber-400" :
              line.includes("🛑")                          ? "text-orange-400" : ""
            }`}>{line}</div>
          ))
        }
        <div ref={endRef} />
      </div>
      {!pinned && (
        <button
          onClick={() => { setPinned(true); endRef.current?.scrollIntoView({ behavior: "smooth" }); }}
          className="absolute bottom-2 right-3 flex items-center gap-1 bg-gray-700 hover:bg-gray-600 text-gray-200 text-xs px-2 py-1 rounded-full shadow"
        >
          <svg className="w-3 h-3" fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
          </svg>
          cuối
        </button>
      )}
    </div>
  );
}

// ── JobCard ───────────────────────────────────────────────────────────
function JobCard({
  aj, compact, onStop, onDismiss, onToggle,
}: {
  aj: ActiveJob;
  compact: boolean;
  onStop:    (id: string) => void;
  onDismiss: (id: string) => void;
  onToggle:  (id: string) => void;
}) {
  const { job, logs, expanded } = aj;
  const st    = job.status as keyof typeof STATUS_STYLE;
  const style = STATUS_STYLE[st] ?? STATUS_STYLE.pending;
  const pct   = job.count > 0 ? (job.created_count / job.count) * 100 : 0;
  const isDone = job.status === "done" || job.status === "failed" || job.status === "stopped";

  return (
    <div className={`card overflow-hidden ring-1 ${style.ring}`}>
      {/* Header */}
      <div
        className="px-4 py-3 flex items-center gap-2 cursor-pointer select-none hover:bg-gray-50/60 transition-colors"
        onClick={() => onToggle(job.id)}
      >
        <div className={`w-2 h-2 rounded-full flex-shrink-0 ${style.dot}`} />

        <span className="font-bold text-sm text-gray-800 truncate max-w-[7rem]">{job.service}</span>
        <span className={`badge text-xs px-2 py-0.5 ${style.badge}`}>{job.status}</span>
        {job.workers > 1 && (
          <span className="text-xs text-gray-400 bg-gray-100 px-1.5 py-0.5 rounded-md">
            ⚡{job.workers}w
          </span>
        )}

        {/* Progress */}
        <div className="flex items-center gap-1.5 flex-1 min-w-0">
          <span className="text-xs text-gray-500 whitespace-nowrap tabular-nums">
            <span className="font-semibold text-gray-800">{job.created_count}</span>/{job.count}
          </span>
          {(job.processed_count ?? 0) > job.created_count && (
            <span className="text-xs text-red-400 tabular-nums" title="Failed">
              {(job.processed_count ?? 0) - job.created_count}✗
            </span>
          )}
          <div className="flex-1 bg-gray-100 rounded-full h-1.5">
            <div className={`h-1.5 rounded-full transition-all duration-500 ${style.bar}`} style={{ width: `${pct}%` }} />
          </div>
          <span className="text-xs text-gray-400 tabular-nums w-8 text-right">{Math.round(pct)}%</span>
        </div>

        {job.error && !isDone && (
          <span className="text-xs text-red-400 truncate max-w-[6rem]">{job.error}</span>
        )}

        {/* Action buttons */}
        <div className="flex items-center gap-1 flex-shrink-0" onClick={(e) => e.stopPropagation()}>
          {!isDone && (
            <button
              onClick={() => onStop(job.id)}
              title="Stop"
              className="p-1.5 rounded-lg hover:bg-red-50 text-gray-400 hover:text-red-500 transition-colors"
            >
              <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 24 24">
                <rect x="6" y="6" width="12" height="12" rx="1.5" />
              </svg>
            </button>
          )}
          <button
            onClick={() => {
              if (!isDone) onStop(job.id);
              onDismiss(job.id);
            }}
            title="Delete"
            className="p-1.5 rounded-lg hover:bg-red-50 text-gray-400 hover:text-red-500 transition-colors"
          >
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
          </button>
          <svg
            className={`w-4 h-4 text-gray-400 transition-transform duration-200 ${expanded ? "rotate-180" : ""}`}
            fill="none" stroke="currentColor" viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </div>

      {expanded && (
        <div className="border-t border-gray-100">
          <LogPanel logs={logs} compact={compact} error={isDone && logs.length === 0 ? (job.error || "Không có log") : undefined} />
        </div>
      )}
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────
export default function CreatePage() {
  const [services, setServices] = useState<string[]>([]);
  const [service,  setService]  = useState("");
  const [count,    setCount]    = useState(1);
  const [workers,  setWorkers]  = useState(1);
  const [activeJobs, setActiveJobs] = useState<Record<string, ActiveJob>>({});
  const [history,    setHistory]    = useState<Job[]>([]);
  const [startError, setStartError] = useState<string | null>(null);

  const wsRefs   = useRef<Record<string, WebSocket>>({});
  const pollRefs = useRef<Record<string, ReturnType<typeof setInterval>>>({});

  const refreshHistory = useCallback(() => {
    api.getJobs().then((jobs) => setHistory([...jobs].reverse().slice(0, 50))).catch(console.error);
  }, []);

  const updateJob = useCallback((id: string, updater: (aj: ActiveJob) => ActiveJob) => {
    setActiveJobs((prev) => (prev[id] ? { ...prev, [id]: updater(prev[id]) } : prev));
  }, []);

  const attachToJob = useCallback((j: Job) => {
    setActiveJobs((prev) => ({
      ...prev,
      [j.id]: prev[j.id] ?? { job: j, logs: [], expanded: true },
    }));
    if (wsRefs.current[j.id]) return;

    const ws = wsLogs(j.id);
    wsRefs.current[j.id] = ws;
    ws.onmessage = (e) => updateJob(j.id, (aj) => ({ ...aj, logs: [...aj.logs, e.data] }));
    ws.onerror   = ()  => updateJob(j.id, (aj) => ({ ...aj, logs: [...aj.logs, "[WS error]"] }));

    const timer = setInterval(() => {
      api.getJob(j.id).then((updated) => {
        updateJob(j.id, (aj) => ({ ...aj, job: updated }));
        if (updated.status === "done" || updated.status === "failed" || updated.status === "stopped") {
          clearInterval(pollRefs.current[j.id]);
          delete pollRefs.current[j.id];
          wsRefs.current[j.id]?.close();
          delete wsRefs.current[j.id];
          refreshHistory();
        }
      }).catch((err) => {
        console.error("Job poll error:", err);
      });
    }, 1500);
    pollRefs.current[j.id] = timer;
  }, [updateJob, refreshHistory]);

  // Load services + restore running jobs on mount
  useEffect(() => {
    api.getServices().then((s) => {
      setServices(s);
      if (s.length) {
        const first = s[0];
        setService(first);
        const cfg = loadSvcCfg(first);
        setCount(cfg.count);
        setWorkers(cfg.workers);
      }
    }).catch(console.error);
    api.getJobs().then((jobs) => {
      const sorted = [...jobs].reverse().slice(0, 50);
      setHistory(sorted);
      sorted.filter((j) => j.status === "running" || j.status === "pending").forEach(attachToJob);
    }).catch(console.error);
  }, [attachToJob]);

  // Khi đổi service → load config đã lưu
  const handleServiceChange = (svc: string) => {
    setService(svc);
    const cfg = loadSvcCfg(svc);
    setCount(cfg.count);
    setWorkers(cfg.workers);
  };

  const handleCountChange = (v: number) => {
    setCount(v);
    saveSvcCfg(service, { count: v, workers });
  };

  const handleWorkersChange = (v: number) => {
    setWorkers(v);
    saveSvcCfg(service, { count, workers: v });
  };

  const startJob = async () => {
    setStartError(null);
    saveSvcCfg(service, { count, workers });
    try {
      const res = await fetch(
        `${_API_ORIGIN}/api/v1/registration/jobs`,
        { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ service, count, workers }) }
      );
      const body = await res.json();
      if (!res.ok) { setStartError(body?.error?.message ?? body?.detail ?? `Lỗi ${res.status}`); return; }
      attachToJob(body.data as Job);
    } catch (_) {
      setStartError("Không kết nối được API server");
    }
  };

  const stopJob = (id: string) => {
    api.cancelJob(id).catch((err) => console.error("cancelJob error:", err));
    wsRefs.current[id]?.close();
    clearInterval(pollRefs.current[id]);
    delete pollRefs.current[id];
    updateJob(id, (aj) => ({ ...aj, job: { ...aj.job, status: "stopped", error: "Người dùng dừng job" } }));
  };

  const dismissJob = (id: string) => {
    wsRefs.current[id]?.close();
    setActiveJobs((prev) => { const n = { ...prev }; delete n[id]; return n; });
  };

  const toggleJob = (id: string) =>
    updateJob(id, (aj) => ({ ...aj, expanded: !aj.expanded }));

  const activeList   = Object.values(activeJobs);
  const runningCount = activeList.filter((aj) => ["running", "pending"].includes(aj.job.status)).length;

  const jobStats = {
    total:        history.length,
    done:         history.filter(j => j.status === "done").length,
    failed:       history.filter(j => j.status === "failed").length,
    totalCreated: history.reduce((s, j) => s + j.created_count, 0),
  };

  return (
    <div className="space-y-5">
      {/* ── Header ── */}
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Create Accounts</h1>
          <p className="text-sm text-gray-400 mt-0.5">Tạo tài khoản tự động với Playwright</p>
        </div>
        {runningCount > 0 && (
          <span className="flex items-center gap-1.5 text-sm font-medium text-amber-600 bg-amber-50 border border-amber-200 px-3 py-1.5 rounded-full">
            <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
            {runningCount} đang chạy
          </span>
        )}
      </div>

      {/* ── Stats ── */}
      {jobStats.total > 0 && (
        <div className="grid grid-cols-4 gap-3">
          {([
            { label: "Jobs run",     value: jobStats.total,        color: "text-gray-900" },
            { label: "Succeeded",    value: jobStats.done,         color: "text-emerald-600" },
            { label: "Failed",       value: jobStats.failed,       color: "text-red-500" },
            { label: "Acc. created", value: jobStats.totalCreated, color: "text-violet-600" },
          ] as const).map(({ label, value, color }) => (
            <div key={label} className="card px-4 py-3">
              <p className="text-xs text-gray-400">{label}</p>
              <p className={`text-2xl font-bold mt-0.5 tabular-nums ${color}`}>{value}</p>
            </div>
          ))}
        </div>
      )}

      {/* ── Control panel ── */}
      <div className="card p-4">
        <div className="flex flex-wrap gap-3 items-end">
          {/* Service */}
          <div className="flex-1 min-w-[9rem]">
            <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1.5">Service</label>
            <select value={service} onChange={(e) => handleServiceChange(e.target.value)} className="input w-full">
              {services.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>

          {/* Count */}
          <div className="w-28">
            <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1.5">Số lượng</label>
            <input
              type="number" min={1} max={1000} value={count}
              onChange={(e) => handleCountChange(Math.max(1, Number(e.target.value)))}
              className="input w-full text-center tabular-nums"
            />
          </div>

          {/* Workers */}
          <div className="w-28">
            <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1.5">Workers</label>
            <input
              type="number" min={1} max={10} value={workers}
              onChange={(e) => handleWorkersChange(Math.max(1, Math.min(10, Number(e.target.value))))}
              className="input w-full text-center tabular-nums"
            />
          </div>

          {/* Run button */}
          <button onClick={startJob} disabled={!service} className="btn-primary h-[38px] px-6 flex-shrink-0">
            <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24"><path d="M8 5v14l11-7z" /></svg>
            Run
            {runningCount > 0 && (
              <span className="bg-white/25 text-white text-xs rounded-full w-5 h-5 flex items-center justify-center font-bold">
                {runningCount}
              </span>
            )}
          </button>
        </div>

        {/* Hints */}
        {startError && (
          <p className="mt-3 text-xs text-red-700 bg-red-50 border border-red-200 rounded-lg px-3 py-2 flex items-center gap-2">
            <svg className="w-3.5 h-3.5 shrink-0" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-8-5a.75.75 0 01.75.75v4.5a.75.75 0 01-1.5 0v-4.5A.75.75 0 0110 5zm0 10a1 1 0 100-2 1 1 0 000 2z" clipRule="evenodd" />
            </svg>
            {startError}
          </p>
        )}
        {workers > 1 && !startError && (
          <p className="mt-3 text-xs text-amber-700 bg-amber-50 border border-amber-100 rounded-lg px-3 py-2">
            ⚡ {workers} workers song song — mỗi worker dùng browser riêng biệt
          </p>
        )}
      </div>

      {/* ── Active Jobs ── */}
      {activeList.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Active Jobs</span>
            {runningCount > 0 && (
              <span className="inline-flex items-center justify-center w-5 h-5 bg-amber-100 text-amber-700 rounded-full text-xs font-bold">
                {runningCount}
              </span>
            )}
          </div>

          <div className={
            activeList.length === 1 ? "" :
            activeList.length === 2 ? "grid grid-cols-2 gap-3" :
            "grid grid-cols-2 gap-3"
          }>
            {activeList.map((aj) => (
              <JobCard
                key={aj.job.id}
                aj={aj}
                compact={activeList.length > 1}
                onStop={stopJob}
                onDismiss={dismissJob}
                onToggle={toggleJob}
              />
            ))}
          </div>
        </div>
      )}

      {/* ── Job History ── */}
      {history.length > 0 && (
        <div className="card overflow-hidden">
          <div className="px-4 py-2.5 border-b border-gray-100 bg-gray-50/60">
            <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Job History</span>
          </div>
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-50">
                {["ID", "Service", "Status", "Created", "Workers", "Time"].map((h) => (
                  <th key={h} className="text-left text-xs font-semibold text-gray-400 px-4 py-2">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {history.slice(0, 30).map((h) => {
                const st = h.status as keyof typeof STATUS_STYLE;
                return (
                  <tr key={h.id} className="hover:bg-gray-50/60 transition-colors">
                    <td className="px-4 py-2 font-mono text-xs text-gray-400">{h.id.slice(0, 8)}…</td>
                    <td className="px-4 py-2 text-xs font-medium text-gray-700">{h.service}</td>
                    <td className="px-4 py-2">
                      <span className={`badge text-xs ${STATUS_STYLE[st]?.badge ?? ""}`}>{h.status}</span>
                    </td>
                    <td className="px-4 py-2 text-xs text-gray-600 tabular-nums">{h.created_count}/{h.count}</td>
                    <td className="px-4 py-2 text-xs text-gray-400">{h.workers ?? 1}</td>
                    <td className="px-4 py-2 text-xs text-gray-400">
                      {h.created_at ? new Date(h.created_at).toLocaleTimeString("vi-VN") + " " + new Date(h.created_at).toLocaleDateString("vi-VN") : "—"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
