import { useEffect, useMemo, useState, useCallback } from "react";
import { api, Account } from "../api/client";
import GmailVariationsModal from "../components/GmailVariationsModal";

// ── Constants ─────────────────────────────────────────────────────────────────

const SERVICE_COLORS: Record<string, string> = {
  OPENROUTER: "bg-violet-100 text-violet-700",
  ELEVENLABS:  "bg-amber-100 text-amber-700",
  CHATGPT:     "bg-emerald-100 text-emerald-700",
  LEONARDO:    "bg-blue-100 text-blue-700",
  "2SLIDES":   "bg-pink-100 text-pink-700",
  PROTON:      "bg-orange-100 text-orange-700",
  ARTIFICIALANALYSIS: "bg-teal-100 text-teal-700",
  OLLAMA:      "bg-gray-100 text-gray-700",
};

const PAGE_SIZE = 50;
const CHECKABLE_SERVICES = new Set(["CHATGPT", "ELEVENLABS", "OPENROUTER"]);

// Services là mailbox provider — KHÔNG phải target service để thêm account vào
const MAILBOX_PROVIDER_SERVICES = new Set(["GMAIL", "GOOGLEMAIL", "PROTONMAIL"]);

type SortKey = "email" | "service" | "credits" | "status" | "quota_pct" | "created_at" | "updated_at";
type SortDir = "asc" | "desc";

type ColKey = "email" | "service" | "api_key" | "password" | "credits" | "status" | "quota_pct" | "created_at" | "last_checked" | "last_error" | "actions";

const ALL_COLS: { key: ColKey; label: string }[] = [
  { key: "email",        label: "Email" },
  { key: "service",      label: "Service" },
  { key: "api_key",      label: "API Key" },
  { key: "password",     label: "Password" },
  { key: "credits",      label: "Credits" },
  { key: "status",       label: "Status" },
  { key: "quota_pct",    label: "Quota" },
  { key: "created_at",   label: "Created" },
  { key: "last_checked", label: "Last Checked" },
  { key: "last_error",   label: "Last Error" },
  { key: "actions",      label: "Actions" },
];

const DEFAULT_VISIBLE_COLS = new Set<ColKey>(["email", "service", "api_key", "password", "credits", "status", "quota_pct", "created_at", "actions"]);

// ── Filter types ──────────────────────────────────────────────────────────────

interface Filters {
  email: string;
  status: "all" | "active" | "disabled" | "unchecked";
  quotaOp: "" | ">" | "<" | "=";
  quotaVal: string;
  hasKey: "all" | "yes" | "no";
}

const DEFAULT_FILTERS: Filters = {
  email: "", status: "all", quotaOp: "", quotaVal: "",
  hasKey: "all",
};

const isGmailMailbox = (email?: string) => {
  const normalized = (email ?? "").trim().toLowerCase();
  return normalized.endsWith("@gmail.com") || normalized.endsWith("@googlemail.com");
};

// ── Per-service fields for Add Account modal ─────────────────────────────────

type AddField = "api_key" | "password" | "totp_secret" | "app_password" | "source_email";

// Chỉ liệt kê field mà service đó thực sự dùng — dựa trên AccountRecord registrar lưu
const SERVICE_FIELDS: Record<string, AddField[]> = {
  OPENROUTER:         ["api_key", "password"],
  ELEVENLABS:         ["api_key", "password"],
  CHATGPT:            ["password"],
  LEONARDO:           ["password"],
  "2SLIDES":          ["api_key"],
  PROTON:             ["password"],
  ARTIFICIALANALYSIS: ["api_key"],
  TESTMAIL:           ["api_key"],
  MAILOSAUR:          ["api_key", "password"],
  KLING:              [],
  KLINGAI:            [],
  OLLAMA:             ["api_key", "password"],
  GMAIL:              ["password", "totp_secret", "app_password", "source_email"],
  GOOGLEMAIL:         ["password", "totp_secret", "app_password", "source_email"],
};

// Service không có trong map → show tất cả
const ALL_ADD_FIELDS: AddField[] = ["api_key", "password", "totp_secret", "app_password", "source_email"];

const getServiceFields = (service: string): AddField[] =>
  SERVICE_FIELDS[service.toUpperCase()] ?? ALL_ADD_FIELDS;

// ── Small components ──────────────────────────────────────────────────────────

function SortIcon({ active, dir }: { active: boolean; dir: SortDir }) {
  return (
    <span className={`ml-1 inline-flex flex-col gap-[1px] ${active ? "text-brand-600" : "text-gray-300"}`}>
      <svg className={`w-3 h-3 transition-transform ${active && dir === "desc" ? "rotate-180" : ""}`}
        fill="currentColor" viewBox="0 0 16 16">
        <path d="M7.247 4.86l-4.796 5.481A.5.5 0 003 11h10a.5.5 0 00.371-.834l-4.796-5.48a.5.5 0 00-.742 0z" />
      </svg>
    </span>
  );
}

function ThSortable({ label, col, sortKey, sortDir, onSort }: {
  label: string; col: SortKey;
  sortKey: SortKey; sortDir: SortDir;
  onSort: (c: SortKey) => void;
}) {
  return (
    <th
      onClick={() => onSort(col)}
      className="text-left text-xs font-semibold text-gray-500 uppercase tracking-wide px-4 py-3 cursor-pointer select-none hover:text-gray-700 whitespace-nowrap"
    >
      {label}
      <SortIcon active={sortKey === col} dir={sortDir} />
    </th>
  );
}

function QuotaBadge({ pct }: { pct?: number | null }) {
  if (pct == null) return <span className="text-gray-300 text-xs">—</span>;
  const color = pct > 50 ? "text-emerald-700 bg-emerald-50"
    : pct > 20 ? "text-amber-700 bg-amber-50"
    : "text-red-700 bg-red-50";
  return <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${color}`}>{pct}%</span>;
}

function StatusCell({ acc }: { acc: Account }) {
  // Dùng `status` computed từ BE — không tự tính ở FE
  const status = acc.status ?? "unchecked";
  const cursor = status === "disabled" && acc.last_error ? "cursor-help" : "";

  const config: Record<string, { label: string; dot: string; bg: string }> = {
    active:    { label: "Active",    dot: "bg-emerald-500", bg: "bg-emerald-50 text-emerald-700" },
    disabled:  { label: "Disabled",  dot: "bg-red-500",     bg: "bg-red-50 text-red-700" },
    unchecked: { label: "Unchecked", dot: "bg-gray-400",    bg: "bg-gray-100 text-gray-500" },
  };
  const { label, dot, bg } = config[status] ?? config.unchecked;

  return (
    <span title={acc.last_error || undefined}
      className={`inline-flex items-center gap-1.5 text-xs font-medium px-2.5 py-0.5 rounded-full ${bg} ${cursor}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${dot}`} />
      {label}
    </span>
  );
}

// ── Filter bar ────────────────────────────────────────────────────────────────

function FilterBar({ filters, onChange, onReset, activeCount }: {
  filters: Filters;
  onChange: (f: Partial<Filters>) => void;
  onReset: () => void;
  activeCount: number;
}) {
  const hasFilters = filters.email || filters.status !== "all" ||
    filters.quotaOp || filters.hasKey !== "all";

  const sel = "px-2 py-1.5 text-xs border border-gray-200 rounded-md bg-white focus:outline-none focus:border-brand-400";
  const inp = "px-2 py-1.5 text-xs border border-gray-200 rounded-md bg-white focus:outline-none focus:border-brand-400";

  return (
    <div className="flex flex-wrap items-center gap-2 mb-4 p-3 bg-gray-50/80 rounded-lg border border-gray-100">
      {/* Email search */}
      <div className="relative">
        <svg className="absolute left-2 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-400 pointer-events-none"
          fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
            d="M21 21l-4.35-4.35M17 11A6 6 0 115 11a6 6 0 0112 0z" />
        </svg>
        <input
          type="text"
          placeholder="Email / API key…"
          value={filters.email}
          onChange={(e) => onChange({ email: e.target.value })}
          className={`${inp} pl-7 w-[200px]`}
        />
      </div>

      <span className="text-gray-300 text-xs">│</span>

      {/* Status */}
      <select value={filters.status} onChange={(e) => onChange({ status: e.target.value as Filters["status"] })}
        className={sel}>
        <option value="all">All Status</option>
        <option value="active">Active</option>
        <option value="disabled">Disabled</option>
        <option value="unchecked">Unchecked</option>
      </select>

      {/* Quota filter */}
      <div className="flex items-center gap-1">
        <span className="text-xs text-gray-500">Quota</span>
        <select value={filters.quotaOp} onChange={(e) => onChange({ quotaOp: e.target.value as Filters["quotaOp"] })}
          className={`${sel} w-[50px]`}>
          <option value="">—</option>
          <option value=">">&gt;</option>
          <option value="<">&lt;</option>
          <option value="=">=</option>
        </select>
        {filters.quotaOp && (
          <input
            type="number"
            min={0} max={100}
            placeholder="%"
            value={filters.quotaVal}
            onChange={(e) => onChange({ quotaVal: e.target.value })}
            className={`${inp} w-[60px]`}
          />
        )}
      </div>

      {/* Has key */}
      <select value={filters.hasKey} onChange={(e) => onChange({ hasKey: e.target.value as Filters["hasKey"] })}
        className={sel}>
        <option value="all">All Keys</option>
        <option value="yes">Has Key</option>
        <option value="no">No Key</option>
      </select>

      {/* Count + Reset */}
      <span className="text-xs text-gray-400 ml-auto">{activeCount} results</span>
      {hasFilters && (
        <button onClick={onReset}
          className="text-xs text-red-500 hover:text-red-700 font-medium">
          ✕ Clear
        </button>
      )}
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export default function AccountsPage() {
  return <AccountsTab />;
}

// ── Accounts Tab ──────────────────────────────────────────────────────────────

function AccountsTab() {
  const [allAccounts, setAllAccounts] = useState<Account[]>([]);
  const [services, setServices]       = useState<string[]>(["ALL"]);
  const [loading, setLoading]         = useState(false);
  const [copied, setCopied]           = useState<string | null>(null);
  const [checking, setChecking]       = useState<Set<string>>(new Set());
  const [toast, setToast]             = useState<{msg: string; ok: boolean} | null>(null);
  const [batchRunning, setBatchRunning] = useState(false);
  const [batchProgress, setBatchProgress] = useState("");
  const [orPrivacyRunning, setOrPrivacyRunning] = useState(false);
  const [orPrivacyProgress, setOrPrivacyProgress] = useState("");
  const [syncing, setSyncing]             = useState(false);
  const [syncingOR, setSyncingOR]         = useState(false);
  const [syncingAuth, setSyncingAuth]     = useState(false);
  const [cleaningOR, setCleaningOR]       = useState(false);
  const [cleanORProgress, setCleanORProgress] = useState("");
  const [fixingPrivacy, setFixingPrivacy] = useState(false);
  const [fixPrivacyProgress, setFixPrivacyProgress] = useState("");
  const [showDeleteDisabledModal, setShowDeleteDisabledModal] = useState(false);
  const [deletingDisabled, setDeletingDisabled] = useState(false);
  const [showAddModal, setShowAddModal] = useState(false);
  const [addForm, setAddForm]         = useState({ service: "", email: "", api_key: "", password: "", totp_secret: "", app_password: "", source_email: "" });
  const [addError, setAddError]       = useState("");
  const [adding, setAdding]           = useState(false);
  const [editAcc, setEditAcc]         = useState<Account | null>(null);
  const [editForm, setEditForm]       = useState({ api_key: "", password: "", totp_secret: "", app_password: "" });
  const [editError, setEditError]     = useState("");
  const [editing, setEditing]         = useState(false);
  const [detailAcc, setDetailAcc]     = useState<Account | null>(null);
  const [detailData, setDetailData]   = useState<any>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState("");
  const [gmailVariationsAcc, setGmailVariationsAcc] = useState<Account | null>(null);
  const [gmailVariationsService, setGmailVariationsService] = useState("");
  const [showActions, setShowActions] = useState(false);
  const [showCols, setShowCols] = useState(false);
  const [visibleCols, setVisibleCols] = useState<Set<ColKey>>(new Set(DEFAULT_VISIBLE_COLS));
  const toggleCol = (col: ColKey) =>
    setVisibleCols((prev) => { const next = new Set(prev); next.has(col) ? next.delete(col) : next.add(col); return next; });
  const col = (k: ColKey) => visibleCols.has(k);

  const showToast = (msg: string, ok: boolean) => {
    setToast({ msg, ok });
    setTimeout(() => setToast(null), 4000);
  };

  // filter state
  const [serviceFilter, setServiceFilter] = useState("ALL");
  const [filters, setFilters] = useState<Filters>(DEFAULT_FILTERS);
  const updateFilters = useCallback((patch: Partial<Filters>) => {
    setFilters((f) => ({ ...f, ...patch }));
    setPage(1);
  }, []);
  const resetFilters = useCallback(() => { setFilters(DEFAULT_FILTERS); setPage(1); }, []);

  // sorting state
  const [sortKey, setSortKey] = useState<SortKey>("email");
  const [sortDir, setSortDir] = useState<SortDir>("asc");

  // pagination
  const [page, setPage] = useState(1);

  const load = () => {
    setLoading(true);
    Promise.all([api.getAccounts(), api.getServices()])
      .then(([accounts, serviceList]) => {
        setAllAccounts(accounts);
        setServices(["ALL", ...serviceList]);
      })
      .catch((err) => showToast(`Load lỗi: ${String(err)}`, false))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const handleSort = (col: SortKey) => {
    if (sortKey === col) setSortDir((d) => d === "asc" ? "desc" : "asc");
    else { setSortKey(col); setSortDir("asc"); }
    setPage(1);
  };

  // ── client-side filter + sort + paginate ──────────────────────────────────
  const filtered = useMemo(() => {
    const q = filters.email.toLowerCase().trim();
    const quotaNum = filters.quotaOp && filters.quotaVal ? parseInt(filters.quotaVal) : NaN;
    return allAccounts.filter((a) => {
      if (serviceFilter !== "ALL" && a.service !== serviceFilter) return false;
      // Dùng `status` từ BE — không tự tính ở FE
      if (filters.status !== "all" && a.status !== filters.status) return false;
      // text search
      if (q && !a.email.toLowerCase().includes(q) &&
               !(a.api_key ?? "").toLowerCase().includes(q)) return false;
      // quota
      if (filters.quotaOp && !isNaN(quotaNum)) {
        const aPct = a.quota_pct ?? 0;
        if (filters.quotaOp === ">" && aPct <= quotaNum) return false;
        if (filters.quotaOp === "<" && aPct >= quotaNum) return false;
        if (filters.quotaOp === "=" && aPct !== quotaNum) return false;
      }
      // has key
      if (filters.hasKey === "yes" && !a.api_key) return false;
      if (filters.hasKey === "no" && !!a.api_key) return false;
      return true;
    });
  }, [allAccounts, serviceFilter, filters]);

  const sorted = useMemo(() => {
    return [...filtered].sort((a, b) => {
      let va: string | number = "";
      let vb: string | number = "";
      if (sortKey === "email")      { va = a.email;              vb = b.email; }
      if (sortKey === "service")    { va = a.service;            vb = b.service; }
      if (sortKey === "credits")    { va = a.credits ?? -1;      vb = b.credits ?? -1; }
      if (sortKey === "status") {
        const rank = (x: Account) => ({ active: 0, unchecked: 1, disabled: 2 }[x.status ?? "unchecked"] ?? 1);
        va = rank(a); vb = rank(b);
      }
      if (sortKey === "quota_pct")  { va = a.quota_pct ?? -1; vb = b.quota_pct ?? -1; }
      if (sortKey === "created_at") { va = a.created_at ?? "";   vb = b.created_at ?? ""; }
      if (sortKey === "updated_at") { va = a.updated_at ?? "";   vb = b.updated_at ?? ""; }
      if (va < vb) return sortDir === "asc" ? -1 : 1;
      if (va > vb) return sortDir === "asc" ? 1 : -1;
      return 0;
    });
  }, [filtered, sortKey, sortDir]);

  const totalPages = Math.max(1, Math.ceil(sorted.length / PAGE_SIZE));
  const pageData   = sorted.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  const remove = async (acc: Account) => {
    const ok = await confirm(`Xóa ${acc.email}?`);
    if (!ok) return;
    api.deleteAccount(acc.service, acc.email).then(load).catch((err) => showToast(`Xóa lỗi: ${String(err)}`, false));
  };

  const toggleDisabled = (acc: Account) => {
    api.updateAccount(acc.service, acc.email, { disabled: !acc.disabled }).then(load).catch((err) => showToast(`Update lỗi: ${String(err)}`, false));
  };

  const checkOne = (acc: Account) => {
    const key = `${acc.service}:${acc.email}`;
    setChecking((s) => new Set(s).add(key));
    api.checkAccount(acc.service, acc.email)
      .then((r) => {
        const msg = r.valid
          ? `✓ Valid${r.quota_pct ? ` · Quota: ${r.quota_pct}` : ""}${r.token_refreshed ? " (refreshed)" : ""}`
          : `✗ Invalid: ${r.last_error || "unknown"}`;
        showToast(msg, r.valid);
        load();
      })
      .catch((err) => { showToast(`Lỗi: ${String(err)}`, false); load(); })
      .finally(() => setChecking((s) => { const next = new Set(s); next.delete(key); return next; }));
  };

  const checkAll = () => {
    setBatchRunning(true);
    setBatchProgress("Starting...");
    const svc = serviceFilter !== "ALL" ? serviceFilter : undefined;
    api.startBatchCheck(svc)
      .then(({ total }) => {
        setBatchProgress(`0 / ${total}`);
        const poll = setInterval(() => {
          api.getBatchCheckStatus().then((s) => {
            setBatchProgress(`${s.checked} / ${s.total} (✓${s.valid} ✗${s.invalid})`);
            if (!s.running) {
              clearInterval(poll);
              setBatchRunning(false);
              showToast(`Check xong: ✓${s.valid} valid, ✗${s.invalid} invalid, ${s.errors} errors`, s.invalid === 0);
              load();
            }
          }).catch((err) => {
            console.error("Batch poll error:", err);
            clearInterval(poll);
            setBatchRunning(false);
            showToast(`Batch check lỗi: ${String(err)}`, false);
          });
        }, 2000);
      })
      .catch((err) => { showToast(`Lỗi: ${String(err)}`, false); setBatchRunning(false); });
  };

  const disabledCountForService = useMemo(() => {
    const base = serviceFilter === "ALL" ? allAccounts : allAccounts.filter((a) => a.service === serviceFilter);
    return base.filter((a) => a.status === "disabled").length;
  }, [allAccounts, serviceFilter]);

  const deleteDisabled = () => {
    setDeletingDisabled(true);
    const svc = serviceFilter !== "ALL" ? serviceFilter : undefined;
    api.deleteDisabledAccounts(svc)
      .then((r) => {
        showToast(`Đã xóa ${r.deleted} tài khoản disabled`, true);
        setShowDeleteDisabledModal(false);
        load();
      })
      .catch((err) => showToast(`Lỗi: ${String(err)}`, false))
      .finally(() => setDeletingDisabled(false));
  };

  const syncOpenRouterToCliproxy = () => {
    setSyncingOR(true);
    api.syncOpenRouterToCliproxy()
      .then((r) => showToast(
        r.added > 0
          ? `Đã thêm ${r.added} key vào CLIProxy (tổng: ${r.total})`
          : `CLIProxy đã có đủ key (${r.total} key)`,
        true
      ))
      .catch((err) => showToast(`Sync OR lỗi: ${String(err)}`, false))
      .finally(() => setSyncingOR(false));
  };

  const checkORPrivacy = () => {
    setOrPrivacyRunning(true);
    setOrPrivacyProgress("Starting...");
    api.startORPrivacyCheck()
      .then(({ total }) => {
        setOrPrivacyProgress(`0 / ${total}`);
        const poll = setInterval(() => {
          api.getORPrivacyCheckStatus().then((s) => {
            setOrPrivacyProgress(`${s.checked} / ${s.total} (🚫${s.privacy_blocked} ⏭${s.skipped})`);
            if (!s.running) {
              clearInterval(poll);
              setOrPrivacyRunning(false);
              showToast(
                `OR Privacy check xong: ✓${s.ok} OK, 🚫${s.privacy_blocked} bị block, ⏭${s.skipped} skipped`,
                s.privacy_blocked === 0,
              );
              load();
            }
          }).catch((err) => {
            console.error("OR privacy poll error:", err);
            clearInterval(poll);
            setOrPrivacyRunning(false);
            showToast(`OR Privacy check lỗi: ${String(err)}`, false);
          });
        }, 2000);
      })
      .catch((err) => { showToast(`Lỗi: ${String(err)}`, false); setOrPrivacyRunning(false); });
  };

  const syncProxy = () => {
    setSyncing(true);
    api.syncCliProxy()
      .then((r) => showToast(`Sync done: xóa ${r.deleted} file (${r.bad_count} disabled)`, true))
      .catch((err) => showToast(`Sync lỗi: ${String(err)}`, false))
      .finally(() => setSyncing(false));
  };

  const syncAuth = () => {
    setSyncingAuth(true);
    api.syncAuth()
      .then((r) => showToast(`Đã sync ${r.synced} auth file(s)`, true))
      .catch((err) => showToast(`Sync auth lỗi: ${String(err)}`, false))
      .finally(() => setSyncingAuth(false));
  };

  const launchKlingSession = () => {
    api.launchKlingSession()
      .then(() => showToast("Browser Kling đã mở — đăng nhập Google để lưu session", true))
      .catch((err) => showToast(`Kling session lỗi: ${String(err)}`, false));
  };

  const checkAndCleanOR = () => {
    setCleaningOR(true);
    setCleanORProgress("Starting...");
    api.startCheckAndCleanOR()
      .then(({ total }) => {
        setCleanORProgress(`0 / ${total}`);
        const poll = setInterval(() => {
          api.getCheckAndCleanORStatus().then((s) => {
            setCleanORProgress(`${s.checked} / ${s.total}`);
            if (!s.running) {
              clearInterval(poll);
              setCleaningOR(false);
              showToast(`OR clean xong: ✓${s.ok} sống, 🗑${s.deleted_db} xóa DB, 🗑${s.deleted_cliproxy} xóa CLIProxy`, s.deleted_db >= 0);
              load();
            }
          }).catch((err) => { clearInterval(poll); setCleaningOR(false); showToast(`Lỗi: ${String(err)}`, false); });
        }, 3000);
      })
      .catch((err) => { showToast(`Lỗi: ${String(err)}`, false); setCleaningOR(false); });
  };

  const fixORPrivacy = () => {
    setFixingPrivacy(true);
    setFixPrivacyProgress("Starting...");
    api.startFixORPrivacy()
      .then(({ total }) => {
        setFixPrivacyProgress(`0 / ${total}`);
        const poll = setInterval(() => {
          api.getFixORPrivacyStatus().then((s) => {
            setFixPrivacyProgress(`${s.processed} / ${s.total} (✓${s.ok} ✗${s.failed})`);
            if (!s.running) {
              clearInterval(poll);
              setFixingPrivacy(false);
              showToast(`Fix privacy xong: ✓${s.ok} OK, ✗${s.failed} fail, ⏭${s.skipped} skip`, s.failed === 0);
            }
          }).catch((err) => { clearInterval(poll); setFixingPrivacy(false); showToast(`Lỗi: ${String(err)}`, false); });
        }, 3000);
      })
      .catch((err) => { showToast(`Lỗi: ${String(err)}`, false); setFixingPrivacy(false); });
  };

  const handleAddAccount = () => {
    if (!addForm.service || !addForm.email) { setAddError("Service và Email bắt buộc"); return; }
    setAdding(true);
    setAddError("");
    api.addAccount(
      addForm.service.toUpperCase(),
      addForm.email,
      addForm.api_key,
      addForm.password,
      addForm.totp_secret,
      addForm.app_password,
      addForm.source_email,
    )
      .then(() => {
        showToast(`Đã thêm ${addForm.email}`, true);
        setShowAddModal(false);
        setAddForm({ service: "", email: "", api_key: "", password: "", totp_secret: "", app_password: "", source_email: "" });
        load();
      })
      .catch((err) => setAddError(String(err)))
      .finally(() => setAdding(false));
  };

  const openEdit = (acc: Account) => {
    setEditAcc(acc);
    setEditForm({
      api_key:      acc.api_key      ?? "",
      password:     acc.password     ?? "",
      totp_secret:  acc.totp_secret  ?? "",
      app_password: acc.app_password ?? "",
    });
    setEditError("");
  };

  const handleEditAccount = () => {
    if (!editAcc) return;
    setEditing(true);
    setEditError("");
    const patch: Record<string, string> = {};
    if (editForm.api_key      !== (editAcc.api_key      ?? "")) patch.api_key      = editForm.api_key;
    if (editForm.password     !== (editAcc.password     ?? "")) patch.password     = editForm.password;
    if (editForm.totp_secret  !== (editAcc.totp_secret  ?? "")) patch.totp_secret  = editForm.totp_secret;
    if (editForm.app_password !== (editAcc.app_password ?? "")) patch.app_password = editForm.app_password;
    if (Object.keys(patch).length === 0) { setEditAcc(null); setEditing(false); return; }
    api.updateAccount(editAcc.service, editAcc.email, patch)
      .then(() => {
        showToast(`Đã cập nhật ${editAcc.email}`, true);
        setEditAcc(null);
        load();
      })
      .catch((err) => setEditError(String(err)))
      .finally(() => setEditing(false));
  };

  const openDetail = (acc: Account) => {
    if (!acc.api_key) return;
    setDetailAcc(acc);
    setDetailData(null);
    setDetailError("");
    setDetailLoading(true);
    api.getKeyDetail(acc.service, acc.api_key)
      .then(setDetailData)
      .catch((err) => setDetailError(String(err)))
      .finally(() => setDetailLoading(false));
  };

  const serviceCounts = useMemo(() => {
    const counts: Record<string, number> = { ALL: allAccounts.length };
    for (const a of allAccounts) counts[a.service] = (counts[a.service] ?? 0) + 1;
    return counts;
  }, [allAccounts]);

  const activeCount  = useMemo(() => allAccounts.filter(a => !a.disabled).length, [allAccounts]);
  const withKeyCount = useMemo(() => allAccounts.filter(a => !!a.api_key).length, [allAccounts]);

  return (
    <div>
      {/* Toast */}
      {toast && (
        <div className={`fixed bottom-5 right-5 z-50 px-4 py-3 rounded-lg shadow-lg text-sm font-medium transition-all ${
          toast.ok ? "bg-emerald-600 text-white" : "bg-red-600 text-white"
        }`}>
          {toast.msg}
        </div>
      )}

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-5">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Accounts</h2>
          <p className="text-xs text-gray-500 mt-0.5">
            {filtered.length.toLocaleString()} / {allAccounts.length.toLocaleString()} shown
            &nbsp;·&nbsp;
            <span className="text-emerald-600 font-medium">{activeCount.toLocaleString()} active</span>
            &nbsp;·&nbsp;
            <span className="text-violet-600 font-medium">{withKeyCount.toLocaleString()} with key</span>
          </p>
        </div>
        <div className="flex items-center gap-2">
          {/* Add */}
          <button onClick={() => setShowAddModal(true)} className="btn-primary gap-1.5 text-xs py-2">
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            Add
          </button>

          {/* Check All */}
          <button onClick={checkAll} disabled={batchRunning} className="btn-secondary gap-1.5 text-xs py-2">
            {batchRunning ? (
              <>
                <svg className="w-3.5 h-3.5 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
                {batchProgress}
              </>
            ) : (
              <>
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                Check All
              </>
            )}
          </button>

          {/* Actions dropdown */}
          <div className="relative">
            <button
              onClick={() => setShowActions((v) => !v)}
              className="btn-secondary text-xs py-2 gap-1"
            >
              Actions
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>
            {showActions && (
              <>
                <div className="fixed inset-0 z-20" onClick={() => setShowActions(false)} />
                <div className="absolute right-0 top-full mt-1 z-30 w-52 bg-white rounded-xl shadow-lg border border-gray-100 py-1 text-sm">
                  <button
                    onClick={() => { setShowActions(false); setShowDeleteDisabledModal(true); }}
                    disabled={disabledCountForService === 0}
                    className="w-full text-left px-4 py-2 hover:bg-red-50 text-red-600 disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-2"
                  >
                    <svg className="w-3.5 h-3.5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                        d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                    </svg>
                    Delete Disabled
                    {disabledCountForService > 0 && (
                      <span className="ml-auto inline-flex items-center justify-center w-5 h-5 rounded-full bg-red-100 text-red-600 text-[10px] font-bold">
                        {disabledCountForService}
                      </span>
                    )}
                  </button>
                  <div className="border-t border-gray-100 my-1" />
                  <button
                    onClick={() => { setShowActions(false); syncOpenRouterToCliproxy(); }}
                    disabled={syncingOR}
                    className="w-full text-left px-4 py-2 hover:bg-gray-50 text-gray-700 disabled:opacity-40 flex items-center gap-2"
                  >
                    <svg className="w-3.5 h-3.5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                    </svg>
                    {syncingOR ? "Syncing OR…" : "Sync OR → CLIProxy"}
                  </button>
                  <button
                    onClick={() => { setShowActions(false); checkORPrivacy(); }}
                    disabled={orPrivacyRunning}
                    className="w-full text-left px-4 py-2 hover:bg-orange-50 text-orange-700 disabled:opacity-40 flex items-center gap-2"
                  >
                    <svg className="w-3.5 h-3.5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                        d="M12 15v2m0 0v2m0-2h2m-2 0H10m2-6V7m0 0V5m0 2h2m-2 0H10M5 3h14a2 2 0 012 2v14a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2z" />
                    </svg>
                    {orPrivacyRunning ? `Check OR Privacy… ${orPrivacyProgress}` : "Check OR Privacy"}
                  </button>
                  <button
                    onClick={() => { setShowActions(false); syncProxy(); }}
                    disabled={syncing}
                    className="w-full text-left px-4 py-2 hover:bg-gray-50 text-gray-700 disabled:opacity-40 flex items-center gap-2"
                  >
                    <svg className="w-3.5 h-3.5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                        d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                    </svg>
                    {syncing ? "Syncing…" : "Sync CLIProxy"}
                  </button>
                  <button
                    onClick={() => { setShowActions(false); syncAuth(); }}
                    disabled={syncingAuth}
                    className="w-full text-left px-4 py-2 hover:bg-blue-50 text-blue-700 disabled:opacity-40 flex items-center gap-2"
                  >
                    <svg className="w-3.5 h-3.5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                        d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
                    </svg>
                    {syncingAuth ? "Syncing Auth…" : "Sync Auth"}
                  </button>
                  <button
                    onClick={() => { setShowActions(false); launchKlingSession(); }}
                    className="w-full text-left px-4 py-2 hover:bg-purple-50 text-purple-700 flex items-center gap-2"
                  >
                    <svg className="w-3.5 h-3.5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                        d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9" />
                    </svg>
                    Kling Session
                  </button>
                  <div className="border-t border-gray-100 my-1" />
                  <button
                    onClick={() => { setShowActions(false); checkAndCleanOR(); }}
                    disabled={cleaningOR}
                    className="w-full text-left px-4 py-2 hover:bg-red-50 text-red-700 disabled:opacity-40 flex items-center gap-2"
                  >
                    <svg className="w-3.5 h-3.5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                        d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                    </svg>
                    {cleaningOR ? `OR Clean… ${cleanORProgress}` : "Check & Clean OR"}
                  </button>
                  <button
                    onClick={() => { setShowActions(false); fixORPrivacy(); }}
                    disabled={fixingPrivacy}
                    className="w-full text-left px-4 py-2 hover:bg-indigo-50 text-indigo-700 disabled:opacity-40 flex items-center gap-2"
                  >
                    <svg className="w-3.5 h-3.5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                        d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                    </svg>
                    {fixingPrivacy ? `Fix Privacy… ${fixPrivacyProgress}` : "Fix OR Privacy"}
                  </button>
                </div>
              </>
            )}
          </div>

          {/* Columns toggle */}
          <div className="relative">
            <button
              onClick={() => setShowCols((v) => !v)}
              className="btn-secondary text-xs py-2 gap-1"
              title="Toggle columns"
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 17V7m0 10a2 2 0 01-2 2H5a2 2 0 01-2-2V7a2 2 0 012-2h2a2 2 0 012 2m0 10a2 2 0 002 2h2a2 2 0 002-2M9 7a2 2 0 012-2h2a2 2 0 012 2m0 10V7m0 10a2 2 0 002 2h2a2 2 0 002-2V7a2 2 0 00-2-2h-2a2 2 0 00-2 2" />
              </svg>
              Cols
            </button>
            {showCols && (
              <>
                <div className="fixed inset-0 z-20" onClick={() => setShowCols(false)} />
                <div className="absolute right-0 top-full mt-1 z-30 w-44 bg-white rounded-xl shadow-lg border border-gray-100 py-2">
                  <p className="px-3 pb-1.5 text-[10px] font-semibold text-gray-400 uppercase tracking-wide">Hiện cột</p>
                  {ALL_COLS.map(({ key, label }) => (
                    <label key={key} className="flex items-center gap-2.5 px-3 py-1.5 hover:bg-gray-50 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={visibleCols.has(key)}
                        onChange={() => toggleCol(key)}
                        className="accent-violet-600 w-3.5 h-3.5"
                      />
                      <span className="text-xs text-gray-700">{label}</span>
                    </label>
                  ))}
                </div>
              </>
            )}
          </div>

          {/* Refresh */}
          <button onClick={load} className="btn-secondary py-2" disabled={loading}>
            <svg className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
          </button>
        </div>
      </div>

      {/* Delete Disabled Confirm Modal */}
      {showDeleteDisabledModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={() => !deletingDisabled && setShowDeleteDisabledModal(false)}>
          <div className="bg-white rounded-xl shadow-xl w-full max-w-sm p-6 space-y-4" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center gap-3">
              <div className="flex-shrink-0 w-10 h-10 rounded-full bg-red-100 flex items-center justify-center">
                <svg className="w-5 h-5 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
                </svg>
              </div>
              <div>
                <h2 className="text-base font-semibold text-gray-900">Xác nhận xóa</h2>
                <p className="text-sm text-gray-500 mt-0.5">Hành động này không thể hoàn tác</p>
              </div>
            </div>
            <p className="text-sm text-gray-700">
              Sẽ có{" "}
              <span className="font-bold text-red-600">{disabledCountForService}</span>{" "}
              tài khoản{" "}
              <span className="font-semibold">{serviceFilter === "ALL" ? "" : serviceFilter + " "}</span>
              ở trạng thái <span className="font-semibold text-red-600">disabled</span> sẽ bị xóa vĩnh viễn.
              Bạn có chắc muốn xóa không?
            </p>
            <div className="flex justify-end gap-2 pt-1">
              <button
                onClick={() => setShowDeleteDisabledModal(false)}
                disabled={deletingDisabled}
                className="btn-secondary text-sm">
                Hủy
              </button>
              <button
                onClick={deleteDisabled}
                disabled={deletingDisabled}
                className="px-4 py-2 text-sm font-medium rounded-lg bg-red-600 text-white hover:bg-red-700 disabled:opacity-50 transition-colors">
                {deletingDisabled ? "Đang xóa..." : "Xóa ngay"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Add Account Modal */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={() => setShowAddModal(false)}>
          <div className="bg-white rounded-xl shadow-xl w-full max-w-md p-6 space-y-4" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold text-gray-900">Add Account</h2>
              <button onClick={() => setShowAddModal(false)} className="text-gray-400 hover:text-gray-600">✕</button>
            </div>
            {addError && (
              <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">{addError}</div>
            )}
            {(() => {
              const fields = new Set(getServiceFields(addForm.service));
              const show = (f: AddField) => !addForm.service || fields.has(f);
              return (
                <div className="space-y-3">
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">Service *</label>
                    <select
                      value={addForm.service}
                      onChange={(e) => setAddForm((f) => ({ ...f, service: e.target.value }))}
                      className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:ring-2 focus:ring-brand-500 focus:border-brand-500"
                    >
                      <option value="">— Chọn service —</option>
                      {services.filter((s) => s !== "ALL").map((s) => (
                        <option key={s} value={s}>{s}</option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">Email *</label>
                    <input
                      type="email"
                      value={addForm.email}
                      onChange={(e) => setAddForm((f) => ({ ...f, email: e.target.value }))}
                      placeholder="user@example.com"
                      className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:ring-2 focus:ring-brand-500 focus:border-brand-500"
                    />
                  </div>

                  {show("api_key") && (
                    <div>
                      <label className="block text-xs font-medium text-gray-600 mb-1">API Key</label>
                      <input
                        type="text"
                        value={addForm.api_key}
                        onChange={(e) => setAddForm((f) => ({ ...f, api_key: e.target.value }))}
                        placeholder="sk-..."
                        className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm font-mono focus:ring-2 focus:ring-brand-500 focus:border-brand-500"
                      />
                    </div>
                  )}

                  {show("password") && (
                    <div>
                      <label className="block text-xs font-medium text-gray-600 mb-1">Password</label>
                      <input
                        type="text"
                        value={addForm.password}
                        onChange={(e) => setAddForm((f) => ({ ...f, password: e.target.value }))}
                        className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:ring-2 focus:ring-brand-500 focus:border-brand-500"
                      />
                    </div>
                  )}

                  {show("totp_secret") && (
                    <div>
                      <label className="block text-xs font-medium text-gray-600 mb-1">TOTP Secret <span className="text-gray-400 font-normal">(base32)</span></label>
                      <input
                        type="text"
                        value={addForm.totp_secret}
                        onChange={(e) => setAddForm((f) => ({ ...f, totp_secret: e.target.value.replace(/\s/g, "").toUpperCase() }))}
                        placeholder="B5ALQJP5LX2M..."
                        className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm font-mono focus:ring-2 focus:ring-brand-500 focus:border-brand-500"
                      />
                    </div>
                  )}

                  {show("app_password") && (
                    <div>
                      <label className="block text-xs font-medium text-gray-600 mb-1">App Password <span className="text-gray-400 font-normal">(IMAP)</span></label>
                      <input
                        type="text"
                        value={addForm.app_password}
                        onChange={(e) => setAddForm((f) => ({ ...f, app_password: e.target.value.replace(/\s/g, "") }))}
                        placeholder="hbjdivqfpjqjirnx"
                        className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm font-mono focus:ring-2 focus:ring-brand-500 focus:border-brand-500"
                      />
                    </div>
                  )}

                  {show("source_email") && (
                    <div>
                      <label className="block text-xs font-medium text-gray-600 mb-1">Source Email <span className="text-gray-400 font-normal">(base Gmail nếu là alias)</span></label>
                      <input
                        type="text"
                        value={addForm.source_email}
                        onChange={(e) => setAddForm((f) => ({ ...f, source_email: e.target.value }))}
                        placeholder="base@gmail.com"
                        className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:ring-2 focus:ring-brand-500 focus:border-brand-500"
                      />
                    </div>
                  )}
                </div>
              );
            })()}
            <div className="flex justify-end gap-2 pt-2">
              <button onClick={() => setShowAddModal(false)} className="btn-secondary text-sm">Cancel</button>
              <button onClick={handleAddAccount} disabled={adding} className="btn-primary text-sm">
                {adding ? "Adding..." : "Add Account"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* OpenRouter Key Detail Modal */}
      {detailAcc && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={() => setDetailAcc(null)}>
          <div className="bg-white rounded-xl shadow-xl w-full max-w-lg p-6 space-y-4" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold text-gray-900">OpenRouter Key Detail</h2>
                <p className="text-xs text-gray-500 font-mono mt-0.5 truncate max-w-[350px]" title={detailAcc.email}>
                  {detailAcc.email}
                </p>
              </div>
              <button onClick={() => setDetailAcc(null)} className="text-gray-400 hover:text-gray-600">✕</button>
            </div>

            {detailLoading && (
              <div className="flex items-center justify-center py-8">
                <svg className="w-6 h-6 text-brand-500 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
              </div>
            )}

            {detailError && (
              <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">{detailError}</div>
            )}

            {detailData && !detailLoading && (() => {
              const d = detailData;
              const fmt = (n: number | null | undefined) =>
                n == null ? "—" : typeof n === "number" ? `$${n.toFixed(4)}` : String(n);
              const limitPct = d.limit && d.limit > 0 && d.limit_remaining != null
                ? Math.round((d.limit_remaining / d.limit) * 100)
                : null;
              return (
                <div className="space-y-4">
                  {/* Status badges */}
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="inline-flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-full bg-emerald-50 text-emerald-700">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                      Valid
                    </span>
                    <span className={`text-xs font-medium px-2.5 py-1 rounded-full ${
                      d.is_free_tier ? "bg-gray-100 text-gray-600" : "bg-violet-50 text-violet-700"
                    }`}>
                      {d.is_free_tier ? "Free Tier" : "Paid"}
                    </span>
                    {d.label && (
                      <span className="text-xs font-medium px-2.5 py-1 rounded-full bg-blue-50 text-blue-700">
                        {d.label}
                      </span>
                    )}
                  </div>

                  {/* Credits limit + remaining */}
                  {d.limit != null && (
                    <div className="bg-gray-50 rounded-lg p-4 space-y-2">
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-gray-600">Credit Limit</span>
                        <span className="font-semibold text-gray-900">{fmt(d.limit)}</span>
                      </div>
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-gray-600">Remaining</span>
                        <span className={`font-semibold ${
                          limitPct != null && limitPct < 20 ? "text-red-600" : limitPct != null && limitPct < 50 ? "text-amber-600" : "text-emerald-600"
                        }`}>{fmt(d.limit_remaining)}</span>
                      </div>
                      {limitPct != null && (
                        <div className="w-full h-2 bg-gray-200 rounded-full overflow-hidden">
                          <div
                            className={`h-full rounded-full transition-all ${
                              limitPct < 20 ? "bg-red-500" : limitPct < 50 ? "bg-amber-500" : "bg-emerald-500"
                            }`}
                            style={{ width: `${limitPct}%` }}
                          />
                        </div>
                      )}
                      {d.limit_reset && (
                        <p className="text-xs text-gray-400">Resets: {d.limit_reset}</p>
                      )}
                    </div>
                  )}

                  {/* Usage table */}
                  <div className="border border-gray-200 rounded-lg overflow-hidden">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="bg-gray-50 border-b border-gray-200">
                          <th className="text-left text-xs font-semibold text-gray-500 uppercase px-4 py-2">Period</th>
                          <th className="text-right text-xs font-semibold text-gray-500 uppercase px-4 py-2">Usage</th>
                          <th className="text-right text-xs font-semibold text-gray-500 uppercase px-4 py-2">BYOK</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-100">
                        {([
                          ["All Time", d.usage, d.byok_usage],
                          ["Monthly", d.usage_monthly, d.byok_usage_monthly],
                          ["Weekly", d.usage_weekly, d.byok_usage_weekly],
                          ["Daily", d.usage_daily, d.byok_usage_daily],
                        ] as [string, number, number][]).map(([label, usage, byok]) => (
                          <tr key={label} className="hover:bg-gray-50">
                            <td className="px-4 py-2 text-gray-700 font-medium">{label}</td>
                            <td className="px-4 py-2 text-right font-mono tabular-nums text-gray-900">{fmt(usage)}</td>
                            <td className="px-4 py-2 text-right font-mono tabular-nums text-gray-400">{fmt(byok)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              );
            })()}

            <div className="flex justify-end pt-2">
              <button onClick={() => setDetailAcc(null)} className="btn-secondary text-sm">Close</button>
            </div>
          </div>
        </div>
      )}

      {/* Service tabs */}
      <div className="flex gap-1.5 mb-4 flex-wrap">
        {services.map((s) => (
          <button key={s}
            onClick={() => { setServiceFilter(s); setPage(1); }}
            className={`px-3.5 py-1.5 rounded-full text-xs font-medium transition-all border ${
              serviceFilter === s
                ? "border-brand-500 bg-brand-50 text-brand-700"
                : "border-gray-200 bg-white text-gray-500 hover:border-gray-300 hover:text-gray-700"
            }`}>
            {s}
            <span className={`ml-1.5 text-xs ${serviceFilter === s ? "text-brand-400" : "text-gray-400"}`}>
              {serviceCounts[s] ?? 0}
            </span>
          </button>
        ))}
      </div>

      {/* Advanced filter bar */}
      <FilterBar filters={filters} onChange={updateFilters} onReset={resetFilters} activeCount={filtered.length} />

      {/* Table */}
      <div className="card overflow-hidden">
        <table className="w-full table-fixed">
          <colgroup>
            {col("email")        && <col className="w-[22%]" />}
            {col("service")      && <col className="w-[90px]" />}
            {col("api_key")      && <col className="w-[160px]" />}
            {col("password")     && <col className="w-[110px]" />}
            {col("credits")      && <col className="w-[65px]" />}
            {col("status")       && <col className="w-[85px]" />}
            {col("quota_pct")    && <col className="w-[65px]" />}
            {col("created_at")   && <col className="w-[80px]" />}
            {col("last_checked") && <col className="w-[130px]" />}
            {col("last_error")   && <col className="w-[18%]" />}
            {col("actions")      && <col className="w-[100px]" />}
          </colgroup>
          <thead>
            <tr className="bg-gray-50 border-b border-gray-100">
              {col("email")        && <ThSortable label="Email"        col="email"      sortKey={sortKey} sortDir={sortDir} onSort={handleSort} />}
              {col("service")      && <ThSortable label="Service"      col="service"    sortKey={sortKey} sortDir={sortDir} onSort={handleSort} />}
              {col("api_key")      && <th className="text-left text-xs font-semibold text-gray-500 uppercase tracking-wide px-4 py-3 whitespace-nowrap">API Key</th>}
              {col("password")     && <th className="text-left text-xs font-semibold text-gray-500 uppercase tracking-wide px-4 py-3">Password</th>}
              {col("credits")      && <ThSortable label="Credits"      col="credits"    sortKey={sortKey} sortDir={sortDir} onSort={handleSort} />}
              {col("status")       && <ThSortable label="Status"       col="status"     sortKey={sortKey} sortDir={sortDir} onSort={handleSort} />}
              {col("quota_pct")    && <ThSortable label="Quota"        col="quota_pct"  sortKey={sortKey} sortDir={sortDir} onSort={handleSort} />}
              {col("created_at")   && <ThSortable label="Created"      col="created_at" sortKey={sortKey} sortDir={sortDir} onSort={handleSort} />}
              {col("last_checked") && <th className="text-left text-xs font-semibold text-gray-500 uppercase tracking-wide px-4 py-3 whitespace-nowrap">Last Checked</th>}
              {col("last_error")   && <th className="text-left text-xs font-semibold text-gray-500 uppercase tracking-wide px-4 py-3 whitespace-nowrap">Last Error</th>}
              {col("actions")      && <th className="text-center text-xs font-semibold text-gray-500 uppercase tracking-wide px-4 py-3 whitespace-nowrap">Actions</th>}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50">
            {pageData.map((a) => {
              const key = `${a.service}:${a.email}`;
              const isChecking = checking.has(key);
              return (
                <tr key={key} className={`hover:bg-blue-50/40 transition-colors group ${a.disabled ? "opacity-50" : ""}`}>
                  {col("email") && (
                    <td className="px-4 py-3 font-mono text-xs text-gray-700 truncate cursor-pointer hover:text-brand-600"
                      onClick={() => { navigator.clipboard.writeText(a.email); showToast(`Copied: ${a.email}`, true); }}
                      title={a.email}>
                      {a.email}
                    </td>
                  )}
                  {col("service") && (
                    <td className="px-4 py-3">
                      <span className={`badge ${SERVICE_COLORS[a.service] ?? "bg-gray-100 text-gray-600"}`}>
                        {a.service}
                      </span>
                    </td>
                  )}
                  {col("api_key") && (
                    <td className="px-3 py-3">
                      {a.api_key ? (
                        <button
                          onClick={() => { navigator.clipboard.writeText(a.api_key!); setCopied(a.api_key!); setTimeout(() => setCopied(null), 1500); }}
                          className="flex items-center gap-1 font-mono text-xs text-gray-500 hover:text-brand-600 transition-colors w-full truncate">
                          {copied === a.api_key ? (
                            <span className="text-emerald-600 font-medium shrink-0">✓ Copied</span>
                          ) : (
                            <>
                              <svg className="w-3 h-3 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                                  d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                              </svg>
                              <span className="truncate">{a.api_key.slice(0, 18)}…</span>
                            </>
                          )}
                        </button>
                      ) : <span className="text-gray-300 text-xs">—</span>}
                    </td>
                  )}
                  {col("password") && (
                    <td className="px-3 py-3 font-mono text-xs text-gray-600 truncate">
                      {a.password
                        ? <button onClick={() => { navigator.clipboard.writeText(a.password!); showToast(`Copied password`, true); }} className="hover:text-brand-600 transition-colors truncate w-full text-left" title={a.password}>{a.password}</button>
                        : <span className="text-gray-300">—</span>}
                    </td>
                  )}
                  {col("credits") && (
                    <td className="px-4 py-3 text-sm text-gray-600 tabular-nums">
                      {a.credits != null ? a.credits.toLocaleString() : <span className="text-gray-300">—</span>}
                    </td>
                  )}
                  {col("status") && (
                    <td className="px-4 py-3"><StatusCell acc={a} /></td>
                  )}
                  {col("quota_pct") && (
                    <td className="px-4 py-3"><QuotaBadge pct={a.quota_pct} /></td>
                  )}
                  {col("created_at") && (
                    <td className="px-4 py-3 text-xs text-gray-400 whitespace-nowrap">
                      {a.created_at ? new Date(a.created_at).toLocaleDateString("vi-VN") : "—"}
                    </td>
                  )}
                  {col("last_checked") && (
                    <td className="px-4 py-3 text-xs text-gray-400 whitespace-nowrap">
                      {a.last_checked ?? "—"}
                    </td>
                  )}
                  {col("last_error") && (
                    <td className="px-4 py-3 text-xs text-red-400 max-w-[200px] truncate" title={a.last_error ?? ""}>
                      {a.last_error || <span className="text-gray-300">—</span>}
                    </td>
                  )}
                  {col("actions") && (
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-center gap-1">
                        {a.service === "OPENROUTER" && a.api_key && (
                          <button onClick={() => openDetail(a)} title="Key Detail"
                            className="p-1 rounded hover:bg-violet-50 text-gray-400 hover:text-violet-600">
                            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                                d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                            </svg>
                          </button>
                        )}
                        {CHECKABLE_SERVICES.has(a.service) && (
                          <button onClick={() => checkOne(a)} disabled={isChecking}
                            title={a.last_checked ? `Checked: ${a.last_checked}` : "Check account"}
                            className="p-1 rounded hover:bg-brand-50 text-gray-400 hover:text-brand-600 disabled:opacity-40">
                            <svg className={`w-3.5 h-3.5 ${isChecking ? "animate-spin" : ""}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                                d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                            </svg>
                          </button>
                        )}
                        <button onClick={() => openEdit(a)} title="Edit account"
                          className="p-1 rounded hover:bg-blue-50 text-gray-400 hover:text-blue-600">
                          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                              d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                          </svg>
                        </button>
                        {isGmailMailbox(a.email) && !!a.app_password && (
                          <button onClick={() => setGmailVariationsAcc(a)} title="Gmail variations (+/./googlemail)"
                            className="p-1 rounded hover:bg-emerald-50 text-gray-400 hover:text-emerald-600">
                            {/* @ icon */}
                            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                                d="M16 12a4 4 0 10-8 0 4 4 0 008 0zm0 0v1.5a2.5 2.5 0 005 0V12a9 9 0 10-9 9m4.5-1.206a8.959 8.959 0 01-4.5 1.207" />
                            </svg>
                          </button>
                        )}
                        <button onClick={() => toggleDisabled(a)}
                          title={a.disabled ? "Enable" : "Disable"}
                          className={`p-1 rounded hover:bg-gray-100 ${a.disabled ? "text-emerald-500 hover:text-emerald-700" : "text-gray-400 hover:text-amber-600"}`}>
                          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            {a.disabled ? (
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                            ) : (
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728L5.636 5.636" />
                            )}
                          </svg>
                        </button>
                        <button onClick={() => remove(a)} title="Delete"
                          className="p-1 rounded hover:bg-red-50 text-gray-400 hover:text-red-600">
                          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                              d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                          </svg>
                        </button>
                      </div>
                    </td>
                  )}
                </tr>
              );
            })}
            {!loading && filtered.length === 0 && (
              <tr>
                <td colSpan={visibleCols.size} className="py-16 text-center">
                  <svg className="w-10 h-10 text-gray-200 mx-auto mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                      d="M21 21l-4.35-4.35M17 11A6 6 0 115 11a6 6 0 0112 0z" />
                  </svg>
                  <p className="text-sm text-gray-400">Không tìm thấy kết quả</p>
                </td>
              </tr>
            )}
          </tbody>
        </table>

        {/* Pagination footer */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between px-5 py-3 border-t border-gray-100 bg-gray-50">
            <span className="text-xs text-gray-500">
              Trang {page}/{totalPages} · {sorted.length} kết quả
            </span>
            <div className="flex items-center gap-1">
              <button
                disabled={page === 1}
                onClick={() => setPage(1)}
                className="px-2 py-1 text-xs rounded border border-gray-200 bg-white text-gray-600 hover:bg-gray-50 disabled:opacity-30 disabled:cursor-not-allowed"
              >«</button>
              <button
                disabled={page === 1}
                onClick={() => setPage((p) => p - 1)}
                className="px-2.5 py-1 text-xs rounded border border-gray-200 bg-white text-gray-600 hover:bg-gray-50 disabled:opacity-30 disabled:cursor-not-allowed"
              >‹</button>
              {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                const start = Math.max(1, Math.min(page - 2, totalPages - 4));
                const p = start + i;
                return (
                  <button key={p} onClick={() => setPage(p)}
                    className={`px-2.5 py-1 text-xs rounded border ${
                      p === page ? "border-brand-500 bg-brand-50 text-brand-700 font-semibold"
                                 : "border-gray-200 bg-white text-gray-600 hover:bg-gray-50"
                    }`}
                  >{p}</button>
                );
              })}
              <button
                disabled={page === totalPages}
                onClick={() => setPage((p) => p + 1)}
                className="px-2.5 py-1 text-xs rounded border border-gray-200 bg-white text-gray-600 hover:bg-gray-50 disabled:opacity-30 disabled:cursor-not-allowed"
              >›</button>
              <button
                disabled={page === totalPages}
                onClick={() => setPage(totalPages)}
                className="px-2 py-1 text-xs rounded border border-gray-200 bg-white text-gray-600 hover:bg-gray-50 disabled:opacity-30 disabled:cursor-not-allowed"
              >»</button>
            </div>
          </div>
        )}
      </div>

      {/* Edit Account Modal */}
      {editAcc && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={() => setEditAcc(null)}>
          <div className="bg-white rounded-xl shadow-xl w-full max-w-md p-6 space-y-4" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold text-gray-900">Edit Account</h2>
                <p className="text-xs text-gray-500 font-mono mt-0.5 truncate max-w-[340px]" title={editAcc.email}>
                  {editAcc.service} · {editAcc.email}
                </p>
              </div>
              <button onClick={() => setEditAcc(null)} className="text-gray-400 hover:text-gray-600">✕</button>
            </div>
            {editError && (
              <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">{editError}</div>
            )}
            <div className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">API Key</label>
                <input type="text" value={editForm.api_key}
                  onChange={(e) => setEditForm((f) => ({ ...f, api_key: e.target.value }))}
                  placeholder="sk-... / aa_..."
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm font-mono focus:ring-2 focus:ring-brand-500 focus:border-brand-500" />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Password</label>
                <input type="text" value={editForm.password}
                  onChange={(e) => setEditForm((f) => ({ ...f, password: e.target.value }))}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:ring-2 focus:ring-brand-500 focus:border-brand-500" />
              </div>
              {isGmailMailbox(editAcc.email) && (
                <>
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">TOTP Secret <span className="text-gray-400 font-normal">(base32)</span></label>
                    <input type="text" value={editForm.totp_secret}
                      onChange={(e) => setEditForm((f) => ({ ...f, totp_secret: e.target.value.replace(/\s/g, "").toUpperCase() }))}
                      placeholder="B5ALQJP5LX2M..."
                      className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm font-mono focus:ring-2 focus:ring-brand-500 focus:border-brand-500" />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">App Password <span className="text-gray-400 font-normal">(IMAP — myaccount.google.com/apppasswords)</span></label>
                    <input type="text" value={editForm.app_password}
                      onChange={(e) => setEditForm((f) => ({ ...f, app_password: e.target.value.replace(/\s/g, "") }))}
                      placeholder="hbjdivqfpjqjirnx"
                      className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm font-mono focus:ring-2 focus:ring-brand-500 focus:border-brand-500" />
                  </div>
                </>
              )}
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button onClick={() => setEditAcc(null)} className="btn-secondary text-sm">Cancel</button>
              <button onClick={handleEditAccount} disabled={editing} className="btn-primary text-sm">
                {editing ? "Saving..." : "Save Changes"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Gmail Variations Modal */}
      {gmailVariationsAcc && (
        <GmailVariationsModal
          baseEmail={gmailVariationsAcc.email}
          service={gmailVariationsService || "ELEVENLABS"}
          availableServices={services.filter((s) => s !== "ALL" && !MAILBOX_PROVIDER_SERVICES.has(s))}
          onServiceChange={setGmailVariationsService}
          onClose={() => { setGmailVariationsAcc(null); setGmailVariationsService(""); }}
          onAdded={(count) => { showToast(`Đã thêm ${count} Gmail variations`, true); load(); }}
        />
      )}

    </div>
  );
}
