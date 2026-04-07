import { useCallback, useEffect, useState } from "react";
import { aarApi, AarAccount, AarAccountStats } from "../api/aar-client";

const PAGE_SIZE = 50;

const STATUS_BADGE: Record<string, string> = {
  registered: "bg-blue-50 text-blue-600 border border-blue-200",
  active:     "bg-emerald-50 text-emerald-700 border border-emerald-200",
  disabled:   "bg-gray-100 text-gray-500",
  banned:     "bg-red-50 text-red-600 border border-red-200",
  failed:     "bg-orange-50 text-orange-600 border border-orange-200",
};

// ── AccountRow ─────────────────────────────────────────────────────────────────

function AccountRow({
  account, selected, onSelect, onDelete,
}: {
  account: AarAccount;
  selected: boolean;
  onSelect: (id: number, v: boolean) => void;
  onDelete: (id: number) => void;
}) {
  const [delConfirm, setDelConfirm] = useState(false);

  const handleDelete = () => {
    if (!delConfirm) { setDelConfirm(true); setTimeout(() => setDelConfirm(false), 2500); return; }
    onDelete(account.id);
  };

  const badgeCls = STATUS_BADGE[account.status] ?? "bg-gray-100 text-gray-600";

  return (
    <tr className="border-b border-gray-50 hover:bg-gray-50/50">
      <td className="px-4 py-2.5">
        <input type="checkbox" checked={selected} onChange={(e) => onSelect(account.id, e.target.checked)} className="rounded" />
      </td>
      <td className="px-4 py-2.5 text-xs font-medium text-gray-700 capitalize">{account.platform}</td>
      <td className="px-4 py-2.5 text-xs text-gray-600 font-mono max-w-xs truncate">{account.email}</td>
      <td className="px-4 py-2.5">
        <span className={`badge text-xs px-2 py-0.5 ${badgeCls}`}>{account.status}</span>
      </td>
      <td className="px-4 py-2.5 text-xs text-gray-500 font-mono max-w-[8rem] truncate" title={account.token}>
        {account.token ? account.token.slice(0, 20) + "..." : "–"}
      </td>
      <td className="px-4 py-2.5 text-xs text-gray-400">
        {account.created_at ? new Date(account.created_at).toLocaleDateString() : "–"}
      </td>
      <td className="px-4 py-2.5">
        <button
          onClick={handleDelete}
          className={`text-xs px-2 py-1 rounded-lg transition-colors ${
            delConfirm
              ? "bg-red-500 text-white"
              : "text-gray-400 hover:text-red-500 hover:bg-red-50"
          }`}
        >
          {delConfirm ? "Chắc?" : "Xóa"}
        </button>
      </td>
    </tr>
  );
}

// ── Stats Panel ────────────────────────────────────────────────────────────────

function StatsPanel({ stats }: { stats: AarAccountStats }) {
  return (
    <div className="flex flex-wrap gap-4 mb-6">
      <div className="card px-4 py-3 flex-shrink-0">
        <div className="text-2xl font-bold text-gray-900">{stats.total}</div>
        <div className="text-xs text-gray-500 mt-0.5">Tổng accounts</div>
      </div>
      {Object.entries(stats.by_platform).map(([platform, count]) => (
        <div key={platform} className="card px-4 py-3 flex-shrink-0">
          <div className="text-xl font-bold text-indigo-600">{count}</div>
          <div className="text-xs text-gray-500 mt-0.5 capitalize">{platform}</div>
        </div>
      ))}
    </div>
  );
}

// ── Main Page ──────────────────────────────────────────────────────────────────

export default function AarAccountsPage() {
  const [accounts, setAccounts] = useState<AarAccount[]>([]);
  const [stats,    setStats]    = useState<AarAccountStats | null>(null);
  const [loading,  setLoading]  = useState(true);
  const [total,    setTotal]    = useState(0);
  const [page,     setPage]     = useState(1);

  // Filters
  const [filterPlatform, setFilterPlatform] = useState("");
  const [filterStatus,   setFilterStatus]   = useState("");
  const [filterEmail,    setFilterEmail]     = useState("");

  const [selected,  setSelected]  = useState<Set<number>>(new Set());
  const [toast, setToast] = useState<{ msg: string; ok: boolean } | null>(null);
  const [deleting, setDeleting] = useState(false);

  const showToast = useCallback((msg: string, ok: boolean) => {
    setToast({ msg, ok });
    setTimeout(() => setToast(null), 3000);
  }, []);

  const loadAccounts = useCallback(async () => {
    setLoading(true);
    try {
      const [res, statsRes] = await Promise.all([
        aarApi.getAccounts({
          platform:  filterPlatform || undefined,
          status:    filterStatus   || undefined,
          email:     filterEmail    || undefined,
          page,
          page_size: PAGE_SIZE,
        }),
        aarApi.getAccountStats(),
      ]);
      setAccounts(res.items);
      setTotal(res.total);
      setStats(statsRes);
      setSelected(new Set());
    } catch (e: unknown) {
      showToast((e instanceof Error ? e.message : String(e)), false);
    } finally {
      setLoading(false);
    }
  }, [filterPlatform, filterStatus, filterEmail, page, showToast]);

  useEffect(() => { loadAccounts(); }, [loadAccounts]);

  // Reset page to 1 when filters change
  useEffect(() => { setPage(1); }, [filterPlatform, filterStatus, filterEmail]);

  const handleSelectOne = useCallback((id: number, v: boolean) => {
    setSelected((prev) => {
      const next = new Set(prev);
      v ? next.add(id) : next.delete(id);
      return next;
    });
  }, []);

  const handleSelectAll = (v: boolean) => {
    setSelected(v ? new Set(accounts.map((a) => a.id)) : new Set());
  };

  const handleDeleteOne = useCallback(async (id: number) => {
    try {
      await aarApi.deleteAccount(id);
      showToast("Đã xóa account", true);
      loadAccounts();
    } catch (e: unknown) {
      showToast((e instanceof Error ? e.message : String(e)), false);
    }
  }, [loadAccounts, showToast]);

  const handleBatchDelete = async () => {
    if (selected.size === 0) return;
    setDeleting(true);
    try {
      const result = await aarApi.batchDeleteAccounts(Array.from(selected));
      showToast(`Đã xóa ${result.deleted} accounts`, true);
      setSelected(new Set());
      loadAccounts();
    } catch (e: unknown) {
      showToast((e instanceof Error ? e.message : String(e)), false);
    } finally {
      setDeleting(false);
    }
  };

  const exportUrl = aarApi.exportAccounts(filterPlatform || undefined);
  const totalPages = Math.ceil(total / PAGE_SIZE);
  const allSelected = accounts.length > 0 && accounts.every((a) => selected.has(a.id));

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between mb-5">
        <div>
          <h1 className="text-xl font-bold text-gray-900">AAR Accounts</h1>
          <p className="text-sm text-gray-500 mt-0.5">Accounts đã đăng ký qua any-auto-register</p>
        </div>
        <div className="flex items-center gap-2">
          {selected.size > 0 && (
            <button
              onClick={handleBatchDelete}
              disabled={deleting}
              className="btn btn-sm bg-red-500 hover:bg-red-600 text-white"
            >
              {deleting ? "Đang xóa..." : `Xóa ${selected.size} mục`}
            </button>
          )}
          <a
            href={exportUrl}
            target="_blank"
            rel="noreferrer"
            className="btn btn-sm btn-secondary"
          >
            Export CSV
          </a>
          <button onClick={loadAccounts} className="btn btn-sm btn-secondary">Reload</button>
        </div>
      </div>

      {/* Toast */}
      {toast && (
        <div className={`mb-4 px-4 py-2 rounded-lg text-sm font-medium ${toast.ok ? "bg-emerald-50 text-emerald-700 border border-emerald-200" : "bg-red-50 text-red-700 border border-red-200"}`}>
          {toast.msg}
        </div>
      )}

      {/* Stats */}
      {stats && <StatsPanel stats={stats} />}

      {/* Filters */}
      <div className="flex items-center gap-3 mb-4">
        <input
          type="text"
          placeholder="Lọc email..."
          value={filterEmail}
          onChange={(e) => setFilterEmail(e.target.value)}
          className="input-sm w-48"
        />
        <input
          type="text"
          placeholder="Platform (chatgpt, grok...)"
          value={filterPlatform}
          onChange={(e) => setFilterPlatform(e.target.value)}
          className="input-sm w-48"
        />
        <input
          type="text"
          placeholder="Status (active, banned...)"
          value={filterStatus}
          onChange={(e) => setFilterStatus(e.target.value)}
          className="input-sm w-40"
        />
        <button onClick={() => { setFilterEmail(""); setFilterPlatform(""); setFilterStatus(""); }} className="text-xs text-gray-400 hover:text-gray-600">
          Xóa filter
        </button>
      </div>

      {/* Table */}
      <div className="card flex-1 overflow-hidden flex flex-col">
        <div className="overflow-auto flex-1">
          <table className="w-full">
            <thead className="sticky top-0 bg-white border-b border-gray-100">
              <tr>
                <th className="px-4 py-3 text-left w-8">
                  <input type="checkbox" checked={allSelected} onChange={(e) => handleSelectAll(e.target.checked)} className="rounded" />
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">Platform</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">Email</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">Status</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">Token</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">Tạo lúc</th>
                <th className="px-4 py-3 w-16" />
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={7} className="px-4 py-12 text-center text-gray-400 text-sm">Đang tải...</td>
                </tr>
              ) : accounts.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-12 text-center text-gray-400 text-sm">Không có account nào</td>
                </tr>
              ) : accounts.map((acc) => (
                <AccountRow
                  key={acc.id}
                  account={acc}
                  selected={selected.has(acc.id)}
                  onSelect={handleSelectOne}
                  onDelete={handleDeleteOne}
                />
              ))}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="border-t border-gray-100 px-4 py-3 flex items-center justify-between">
            <span className="text-xs text-gray-500">{total} accounts · trang {page}/{totalPages}</span>
            <div className="flex items-center gap-1">
              <button
                disabled={page <= 1}
                onClick={() => setPage((p) => p - 1)}
                className="btn btn-xs btn-secondary disabled:opacity-40"
              >←</button>
              {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                const p = Math.max(1, Math.min(page - 2, totalPages - 4)) + i;
                return (
                  <button
                    key={p}
                    onClick={() => setPage(p)}
                    className={`btn btn-xs ${p === page ? "btn-primary" : "btn-secondary"}`}
                  >
                    {p}
                  </button>
                );
              })}
              <button
                disabled={page >= totalPages}
                onClick={() => setPage((p) => p + 1)}
                className="btn btn-xs btn-secondary disabled:opacity-40"
              >→</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
