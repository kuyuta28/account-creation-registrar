import { useCallback, useEffect, useRef, useState } from "react";
import { aarApi, AarPlatform, AarTask, AarTaskLog, AarTaskLogsResponse } from "../api/aar-client";
import { LogPanel } from "./CreatePage";

// ── Constants ─────────────────────────────────────────────────────────────────

const STATUS_STYLE: Record<string, { badge: string; dot: string; bar: string; ring: string }> = {
  pending: { badge: "bg-gray-100 text-gray-500",                               dot: "bg-gray-300",                bar: "bg-gray-300",    ring: "ring-gray-200" },
  running: { badge: "bg-amber-50 text-amber-600 border border-amber-200",      dot: "bg-amber-400 animate-pulse", bar: "bg-amber-400",   ring: "ring-amber-200" },
  done:    { badge: "bg-emerald-50 text-emerald-700 border border-emerald-200", dot: "bg-emerald-500",             bar: "bg-emerald-500", ring: "ring-emerald-200" },
  stopped: { badge: "bg-slate-50 text-slate-600 border border-slate-200",       dot: "bg-slate-400",               bar: "bg-slate-400",   ring: "ring-slate-200"  },
  failed:  { badge: "bg-red-50 text-red-600 border border-red-200",            dot: "bg-red-400",                 bar: "bg-red-400",     ring: "ring-red-200"   },
};

const MAIL_PROVIDERS = [
  "luckmail", "duckmail", "freemail", "moemail", "skymail", "cloudmail",
  "maliapi", "applemail", "gptmail", "opentrashmail", "cfworker",
];

const CAPTCHA_SOLVERS = ["yescaptcha", "twocaptcha", "local_solver"];
const EXECUTORS       = ["protocol", "browser"];

// ── TaskCard ──────────────────────────────────────────────────────────────────

interface ActiveTask { task: AarTask; logs: string[]; expanded: boolean; }

function TaskCard({ at, onStop, onSkip, onDismiss, onToggle }: {
  at: ActiveTask;
  onStop:    (id: string) => void;
  onSkip:    (id: string) => void;
  onDismiss: (id: string) => void;
  onToggle:  (id: string) => void;
}) {
  const { task, logs, expanded } = at;
  const st    = task.status as keyof typeof STATUS_STYLE;
  const style = STATUS_STYLE[st] ?? STATUS_STYLE.pending;
  const pct   = task.total > 0 ? ((task.success + task.skipped + task.errors.length) / task.total) * 100 : 0;
  const isDone = ["done", "failed", "stopped"].includes(task.status);

  return (
    <div className={`card overflow-hidden ring-1 ${style.ring}`}>
      <div
        className="px-4 py-3 flex items-center gap-2 cursor-pointer select-none hover:bg-gray-50/60 transition-colors"
        onClick={() => onToggle(task.task_id)}
      >
        <div className={`w-2 h-2 rounded-full flex-shrink-0 ${style.dot}`} />
        <span className="font-bold text-sm text-gray-800 truncate max-w-[7rem] capitalize">{task.platform}</span>
        <span className={`badge text-xs px-2 py-0.5 ${style.badge}`}>{task.status}</span>

        <div className="flex items-center gap-1.5 flex-1 min-w-0">
          <span className="text-xs text-gray-500 whitespace-nowrap tabular-nums">
            <span className="font-semibold text-emerald-600">{task.success}</span>
            {task.skipped > 0 && <span className="text-gray-400">/{task.skipped}skip</span>}
            {task.errors.length > 0 && <span className="text-red-400">/{task.errors.length}err</span>}
            /{task.total}
          </span>
          <div className="flex-1 bg-gray-100 rounded-full h-1.5">
            <div className={`h-1.5 rounded-full transition-all duration-500 ${style.bar}`} style={{ width: `${pct}%` }} />
          </div>
          <span className="text-xs text-gray-400 tabular-nums w-8 text-right">{Math.round(pct)}%</span>
        </div>

        {task.cashier_urls && task.cashier_urls.length > 0 && (
          <span className="text-xs bg-amber-50 text-amber-600 px-1.5 py-0.5 rounded border border-amber-200">
            💳 {task.cashier_urls.length}
          </span>
        )}

        <div className="flex items-center gap-1 flex-shrink-0" onClick={(e) => e.stopPropagation()}>
          {!isDone && (
            <>
              <button
                onClick={() => onSkip(task.task_id)}
                title="Skip current"
                className="p-1.5 rounded-lg hover:bg-amber-50 text-gray-400 hover:text-amber-600 transition-colors text-xs"
              >
                ⏭
              </button>
              <button
                onClick={() => onStop(task.task_id)}
                title="Stop"
                className="p-1.5 rounded-lg hover:bg-red-50 text-gray-400 hover:text-red-500 transition-colors"
              >
                <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 24 24">
                  <rect x="6" y="6" width="12" height="12" rx="1.5" />
                </svg>
              </button>
            </>
          )}
          <button
            onClick={() => { if (!isDone) onStop(task.task_id); onDismiss(task.task_id); }}
            title="Dismiss"
            className="p-1.5 rounded-lg hover:bg-red-50 text-gray-400 hover:text-red-500 transition-colors"
          >
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
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

      {/* Cashier URLs */}
      {expanded && task.cashier_urls && task.cashier_urls.length > 0 && (
        <div className="px-4 py-2 bg-amber-50 border-t border-amber-100 text-xs space-y-1">
          <div className="font-semibold text-amber-700">💳 Payment links:</div>
          {task.cashier_urls.map((url, i) => (
            <a key={i} href={url} target="_blank" rel="noreferrer" className="block text-blue-600 hover:underline truncate font-mono">
              {url}
            </a>
          ))}
        </div>
      )}

      {expanded && (
        <div className="border-t border-gray-100">
          <LogPanel logs={logs} />
        </div>
      )}
    </div>
  );
}

// ── HistoryTable ──────────────────────────────────────────────────────────────

function HistoryTable({ logs, onDelete }: { logs: AarTaskLog[]; onDelete: (ids: number[]) => void }) {
  const [selected, setSelected] = useState<Set<number>>(new Set());

  const toggle = (id: number, v: boolean) => {
    setSelected((prev) => { const n = new Set(prev); v ? n.add(id) : n.delete(id); return n; });
  };
  const allChecked = logs.length > 0 && logs.every((l) => selected.has(l.id));

  return (
    <div className="card overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
        <span className="text-sm font-semibold text-gray-700">Lịch sử đăng ký</span>
        {selected.size > 0 && (
          <button
            onClick={() => { onDelete(Array.from(selected)); setSelected(new Set()); }}
            className="text-xs text-red-500 hover:text-red-700"
          >
            Xóa {selected.size} mục
          </button>
        )}
      </div>
      <div className="overflow-auto max-h-64">
        <table className="w-full">
          <thead className="sticky top-0 bg-white border-b border-gray-100">
            <tr>
              <th className="px-4 py-2 w-8">
                <input type="checkbox" checked={allChecked} onChange={(e) => setSelected(e.target.checked ? new Set(logs.map((l) => l.id)) : new Set())} className="rounded" />
              </th>
              <th className="px-4 py-2 text-left text-xs font-semibold text-gray-500 uppercase">Platform</th>
              <th className="px-4 py-2 text-left text-xs font-semibold text-gray-500 uppercase">Email</th>
              <th className="px-4 py-2 text-left text-xs font-semibold text-gray-500 uppercase">Status</th>
              <th className="px-4 py-2 text-left text-xs font-semibold text-gray-500 uppercase">Error</th>
              <th className="px-4 py-2 text-left text-xs font-semibold text-gray-500 uppercase">Thời gian</th>
            </tr>
          </thead>
          <tbody>
            {logs.length === 0 ? (
              <tr><td colSpan={6} className="px-4 py-8 text-center text-gray-400 text-sm">Chưa có lịch sử</td></tr>
            ) : logs.map((log) => (
              <tr key={log.id} className="border-b border-gray-50 hover:bg-gray-50/50">
                <td className="px-4 py-2">
                  <input type="checkbox" checked={selected.has(log.id)} onChange={(e) => toggle(log.id, e.target.checked)} className="rounded" />
                </td>
                <td className="px-4 py-2 text-xs text-gray-600 capitalize">{log.platform}</td>
                <td className="px-4 py-2 text-xs font-mono text-gray-600 max-w-[12rem] truncate">{log.email || "–"}</td>
                <td className="px-4 py-2">
                  <span className={`badge text-xs px-2 py-0.5 ${
                    log.status === "success" ? "bg-emerald-50 text-emerald-700 border border-emerald-200" :
                    log.status === "skipped" ? "bg-amber-50 text-amber-600 border border-amber-200" :
                    "bg-red-50 text-red-600 border border-red-200"
                  }`}>{log.status}</span>
                </td>
                <td className="px-4 py-2 text-xs text-red-400 max-w-[12rem] truncate">{log.error || "–"}</td>
                <td className="px-4 py-2 text-xs text-gray-400">
                  {log.created_at ? new Date(log.created_at).toLocaleString() : "–"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function AarCreatePage() {
  const [platforms, setPlatforms] = useState<AarPlatform[]>([]);
  const [platform,  setPlatform]  = useState("");
  const [count,     setCount]     = useState(1);
  const [concurrency, setConcurrency] = useState(1);
  const [proxy,     setProxy]     = useState("");
  const [executorType,  setExecutorType]  = useState("protocol");
  const [captchaSolver, setCaptchaSolver] = useState("yescaptcha");
  const [mailProvider,  setMailProvider]  = useState("");
  const [delaySeconds,  setDelaySeconds]  = useState(0);
  const [startError, setStartError] = useState<string | null>(null);

  const [activeTasks, setActiveTasks]   = useState<Record<string, ActiveTask>>({});
  const [history,     setHistory]       = useState<AarTaskLog[]>([]);
  const [historyTotal, setHistoryTotal] = useState(0);

  const sseRefs = useRef<Record<string, EventSource>>({});
  const pollRefs = useRef<Record<string, ReturnType<typeof setInterval>>>({});

  // ── Load platforms & history ────────────────────────────────────────────────

  useEffect(() => {
    aarApi.getPlatforms()
      .then((p) => { setPlatforms(p); if (p.length > 0) setPlatform(p[0].name); })
      .catch(console.error);
    loadHistory();

    // Load existing running tasks
    aarApi.listTasks().then((tasks) => {
      for (const task of tasks) {
        if (!["done", "failed", "stopped"].includes(task.status)) {
          attachToTask(task);
        }
      }
    }).catch(console.error);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const loadHistory = useCallback(() => {
    aarApi.getTaskLogs({ page_size: 100 })
      .then((r: AarTaskLogsResponse) => { setHistory(r.items); setHistoryTotal(r.total); })
      .catch(console.error);
  }, []);

  // ── Attach SSE + polling to a task ─────────────────────────────────────────

  const updateTask = useCallback((id: string, updater: (at: ActiveTask) => ActiveTask) => {
    setActiveTasks((prev) => (prev[id] ? { ...prev, [id]: updater(prev[id]) } : prev));
  }, []);

  const attachToTask = useCallback((t: AarTask) => {
    setActiveTasks((prev) => ({
      ...prev,
      [t.task_id]: prev[t.task_id] ?? { task: t, logs: [], expanded: true },
    }));

    // SSE log stream
    if (sseRefs.current[t.task_id]) sseRefs.current[t.task_id].close();
    const sse = aarApi.sseTaskLogs(t.task_id);
    sseRefs.current[t.task_id] = sse;
    sse.onmessage = (ev) => {
      const data = JSON.parse(ev.data);
      if (data.line) {
        updateTask(t.task_id, (at) => ({ ...at, logs: [...at.logs, data.line] }));
      }
      if (data.done) {
        sse.close();
        delete sseRefs.current[t.task_id];
        loadHistory();
      }
    };
    sse.onerror = () => { sse.close(); delete sseRefs.current[t.task_id]; };

    // Poll task status
    if (pollRefs.current[t.task_id]) clearInterval(pollRefs.current[t.task_id]);
    const poll = setInterval(async () => {
      try {
        const updated = await aarApi.getTask(t.task_id);
        updateTask(t.task_id, (at) => ({ ...at, task: updated }));
        if (["done", "failed", "stopped"].includes(updated.status)) {
          clearInterval(poll);
          delete pollRefs.current[t.task_id];
          loadHistory();
        }
      } catch (_) {
        clearInterval(poll);
        delete pollRefs.current[t.task_id];
      }
    }, 2000);
    pollRefs.current[t.task_id] = poll;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [updateTask, loadHistory]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      Object.values(sseRefs.current).forEach((s) => s.close());
      Object.values(pollRefs.current).forEach(clearInterval);
    };
  }, []);

  // ── Actions ────────────────────────────────────────────────────────────────

  const handleStart = async () => {
    setStartError(null);
    try {
      const extra: Record<string, string> = {};
      if (mailProvider) extra.mail_provider = mailProvider;

      const { task_id } = await aarApi.createTask({
        platform,
        count,
        concurrency,
        proxy: proxy.trim() || undefined,
        executor_type: executorType,
        captcha_solver: captchaSolver,
        register_delay_seconds: delaySeconds,
        extra,
      });

      const newTask: AarTask = {
        task_id,
        platform,
        status: "pending",
        total: count,
        success: 0,
        skipped: 0,
        errors: [],
      };
      attachToTask(newTask);
    } catch (e: unknown) {
      setStartError(e instanceof Error ? e.message : String(e));
    }
  };

  const handleStop = async (taskId: string) => {
    try { await aarApi.stopTask(taskId); } catch (_) {}
  };

  const handleSkip = async (taskId: string) => {
    try { await aarApi.skipCurrent(taskId); } catch (_) {}
  };

  const handleDismiss = (taskId: string) => {
    sseRefs.current[taskId]?.close();
    if (pollRefs.current[taskId]) clearInterval(pollRefs.current[taskId]);
    delete sseRefs.current[taskId];
    delete pollRefs.current[taskId];
    setActiveTasks((prev) => { const n = { ...prev }; delete n[taskId]; return n; });
  };

  const handleToggle = (taskId: string) => {
    updateTask(taskId, (at) => ({ ...at, expanded: !at.expanded }));
  };

  const handleDeleteLogs = async (ids: number[]) => {
    try {
      await aarApi.batchDeleteTaskLogs(ids);
      loadHistory();
    } catch (_) {}
  };

  // ── Render ─────────────────────────────────────────────────────────────────

  const activeList = Object.values(activeTasks).sort((a, b) =>
    a.task.task_id < b.task.task_id ? 1 : -1
  );

  return (
    <div className="flex gap-6">
      {/* Left: Controls */}
      <div className="w-72 flex-shrink-0 space-y-4">
        <div className="card p-5 space-y-4">
          <h2 className="text-base font-semibold text-gray-900">Đăng ký mới</h2>

          {/* Platform */}
          <div className="space-y-1">
            <label className="block text-xs font-medium text-gray-700">Platform</label>
            <select
              value={platform}
              onChange={(e) => setPlatform(e.target.value)}
              className="input w-full"
            >
              {platforms.map((p) => (
                <option key={p.name} value={p.name}>{p.label || p.name}</option>
              ))}
            </select>
          </div>

          {/* Count + Concurrency */}
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="block text-xs font-medium text-gray-700">Số lượng</label>
              <input
                type="number" min={1} max={500}
                value={count} onChange={(e) => setCount(Number(e.target.value))}
                className="input w-full"
              />
            </div>
            <div className="space-y-1">
              <label className="block text-xs font-medium text-gray-700">Concurrency</label>
              <input
                type="number" min={1} max={5}
                value={concurrency} onChange={(e) => setConcurrency(Number(e.target.value))}
                className="input w-full"
              />
            </div>
          </div>

          {/* Executor + Captcha */}
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="block text-xs font-medium text-gray-700">Executor</label>
              <select value={executorType} onChange={(e) => setExecutorType(e.target.value)} className="input w-full">
                {EXECUTORS.map((e) => <option key={e} value={e}>{e}</option>)}
              </select>
            </div>
            <div className="space-y-1">
              <label className="block text-xs font-medium text-gray-700">Captcha</label>
              <select value={captchaSolver} onChange={(e) => setCaptchaSolver(e.target.value)} className="input w-full">
                {CAPTCHA_SOLVERS.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
          </div>

          {/* Mail provider */}
          <div className="space-y-1">
            <label className="block text-xs font-medium text-gray-700">Mail Provider</label>
            <select value={mailProvider} onChange={(e) => setMailProvider(e.target.value)} className="input w-full">
              <option value="">Dùng default từ config</option>
              {MAIL_PROVIDERS.map((p) => <option key={p} value={p}>{p}</option>)}
            </select>
          </div>

          {/* Proxy */}
          <div className="space-y-1">
            <label className="block text-xs font-medium text-gray-700">Proxy (tùy chọn)</label>
            <input
              type="text"
              value={proxy}
              onChange={(e) => setProxy(e.target.value)}
              placeholder="http://user:pass@host:port"
              className="input w-full text-xs font-mono"
            />
          </div>

          {/* Delay */}
          <div className="space-y-1">
            <label className="block text-xs font-medium text-gray-700">Delay giữa tài khoản (giây)</label>
            <input
              type="number" min={0} step={0.5}
              value={delaySeconds} onChange={(e) => setDelaySeconds(Number(e.target.value))}
              className="input w-full"
            />
          </div>

          {startError && (
            <div className="text-xs text-red-600 bg-red-50 rounded-lg px-3 py-2 border border-red-200">
              {startError}
            </div>
          )}

          <button
            onClick={handleStart}
            disabled={!platform}
            className="btn btn-primary w-full"
          >
            ▶ Bắt đầu đăng ký
          </button>
        </div>
      </div>

      {/* Right: Tasks + History */}
      <div className="flex-1 space-y-6 min-w-0">
        {/* Active tasks */}
        <div>
          <h2 className="text-sm font-semibold text-gray-700 mb-3">Tasks đang chạy ({activeList.length})</h2>
          {activeList.length === 0 ? (
            <div className="card px-5 py-8 text-center text-gray-400 text-sm">
              Chưa có task nào. Bấm "Bắt đầu đăng ký" để tạo task mới.
            </div>
          ) : (
            <div className="space-y-3">
              {activeList.map((at) => (
                <TaskCard
                  key={at.task.task_id}
                  at={at}
                  onStop={handleStop}
                  onSkip={handleSkip}
                  onDismiss={handleDismiss}
                  onToggle={handleToggle}
                />
              ))}
            </div>
          )}
        </div>

        {/* History */}
        <div>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-gray-700">Lịch sử ({historyTotal})</h2>
            <button onClick={loadHistory} className="text-xs text-gray-400 hover:text-gray-600">Reload</button>
          </div>
          <HistoryTable logs={history} onDelete={handleDeleteLogs} />
        </div>
      </div>
    </div>
  );
}
