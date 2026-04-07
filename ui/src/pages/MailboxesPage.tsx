/**
 * MailboxesPage.tsx
 *
 * Quản lý Gmail mailboxes — inbox credential dùng để đăng ký service.
 * Gmail mailbox ≠ service account: mailbox là hòm thư, account là tài khoản dịch vụ.
 */

import { useEffect, useState, useCallback } from "react";
import { api, GmailMailbox, MailboxServiceBlock } from "../api/client";

// ── Small helpers ─────────────────────────────────────────────────────────────

// ── Add Block Modal ───────────────────────────────────────────────────────────

interface AddBlockModalProps {
  email: string;
  existing: string[]; // services đã bị block
  services: string[];  // toàn bộ services có trong DB
  onClose: () => void;
  onAdded: (block: MailboxServiceBlock) => void;
}

function AddBlockModal({ email, existing, services, onClose, onAdded }: AddBlockModalProps) {
  const [service, setService] = useState("");
  const [reason, setReason]   = useState("");
  const [saving, setSaving]   = useState(false);
  const [error, setError]     = useState("");

  const available = services.filter((s) => !existing.includes(s));

  const handleSave = async () => {
    if (!service) { setError("Chọn service"); return; }
    setSaving(true);
    setError("");
    try {
      await api.addMailboxBlock(email, service, reason.trim());
      onAdded({ email, service, reason: reason.trim(), blocked_at: new Date().toISOString() });
    } catch (e: any) {
      setError(e.message ?? "Lỗi không xác định");
      setSaving(false);
    }
  };

  const inp = "w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:border-brand-400 bg-white";

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-sm">
        <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
          <div>
            <h2 className="text-base font-semibold text-gray-900">Thêm Service Block</h2>
            <p className="text-xs text-gray-400 mt-0.5 font-mono">{email}</p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl leading-none">×</button>
        </div>
        <div className="px-5 py-4 space-y-3">
          <div>
            <label className="text-xs text-gray-500 mb-1 block">Service</label>
            <select
              value={service}
              onChange={(e) => { setService(e.target.value); setError(""); }}
              className={inp}
            >
              <option value="">— Chọn service —</option>
              {available.map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-xs text-gray-500 mb-1 block">Lý do (tuỳ chọn)</label>
            <input
              className={inp}
              placeholder="VD: Error 47 - per-account block"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
          </div>
          {error && <p className="text-xs text-red-500">{error}</p>}
        </div>
        <div className="px-5 py-3 border-t border-gray-100 flex justify-end gap-2">
          <button onClick={onClose} className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800">Hủy</button>
          <button
            onClick={handleSave}
            disabled={saving || !service}
            className="px-4 py-2 text-sm font-medium bg-amber-600 text-white rounded-lg hover:bg-amber-700 disabled:opacity-50"
          >
            {saving ? "Đang lưu…" : "Block"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Add/Edit Modal ────────────────────────────────────────────────────────────

interface ModalProps {
  initial?: GmailMailbox;
  onClose: () => void;
  onSaved: (m: GmailMailbox) => void;
}

function MailboxModal({ initial, onClose, onSaved }: ModalProps) {
  const [form, setForm] = useState({
    email:        initial?.email ?? "",
    app_password: initial?.app_password ?? "",
    totp_secret:  initial?.totp_secret ?? "",
    password:     initial?.password ?? "",
    source_email: initial?.source_email ?? "",
    disabled:     initial?.disabled ?? false,
  });
  const [saving, setSaving] = useState(false);
  const [error, setError]   = useState("");

  const set = (k: keyof typeof form, v: string | boolean) =>
    setForm((prev) => ({ ...prev, [k]: v }));

  const handleSave = async () => {
    if (!form.email.trim()) { setError("Email không được để trống"); return; }
    setSaving(true);
    setError("");
    try {
      const saved = await api.upsertGmailMailbox({
        email:        form.email.trim(),
        app_password: form.app_password.trim(),
        totp_secret:  form.totp_secret.trim(),
        password:     form.password.trim(),
        source_email: form.source_email.trim(),
        disabled:     form.disabled,
      });
      onSaved(saved);
    } catch (e: any) {
      setError(e.message ?? "Lỗi không xác định");
    } finally {
      setSaving(false);
    }
  };

  const inp = "w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:border-brand-400 bg-white font-mono";

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-md">
        <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
          <h2 className="text-base font-semibold text-gray-900">
            {initial ? "Sửa Gmail Mailbox" : "Thêm Gmail Mailbox"}
          </h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl leading-none">×</button>
        </div>

        <div className="px-5 py-4 space-y-3">
          <div>
            <label className="text-xs text-gray-500 mb-1 block">Gmail address</label>
            <input
              type="email"
              value={form.email}
              onChange={(e) => set("email", e.target.value)}
              disabled={!!initial}
              placeholder="abc@gmail.com"
              className={`${inp} ${initial ? "bg-gray-50 text-gray-400" : ""}`}
            />
          </div>
          <div>
            <label className="text-xs text-gray-500 mb-1 block">App Password (tuỳ chọn)</label>
            <input
              type="text"
              value={form.app_password}
              onChange={(e) => set("app_password", e.target.value)}
              placeholder="xxxx xxxx xxxx xxxx"
              className={inp}
            />
          </div>
          <div>
            <label className="text-xs text-gray-500 mb-1 block">TOTP Secret (tuỳ chọn)</label>
            <input
              type="text"
              value={form.totp_secret}
              onChange={(e) => set("totp_secret", e.target.value)}
              placeholder="Base32 secret"
              className={inp}
            />
          </div>
          <div>
            <label className="text-xs text-gray-500 mb-1 block">Mật khẩu Google (tuỳ chọn)</label>
            <input
              type="text"
              value={form.password}
              onChange={(e) => set("password", e.target.value)}
              placeholder="Google account password"
              className={inp}
            />
          </div>
          <div>
            <label className="text-xs text-gray-500 mb-1 block">Source Email (tuỳ chọn)</label>
            <input
              type="email"
              value={form.source_email}
              onChange={(e) => set("source_email", e.target.value)}
              placeholder="base@gmail.com (nếu là alias)"
              className={inp}
            />
          </div>
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="mb-disabled"
              checked={form.disabled}
              onChange={(e) => set("disabled", e.target.checked)}
              className="rounded"
            />
            <label htmlFor="mb-disabled" className="text-sm text-gray-600">Disabled</label>
          </div>
          {error && <p className="text-xs text-red-600">{error}</p>}
        </div>

        <div className="px-5 py-3 border-t border-gray-100 flex justify-end gap-2">
          <button onClick={onClose}
            className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800">
            Hủy
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-4 py-2 text-sm font-medium bg-brand-600 text-white rounded-lg hover:bg-brand-700 disabled:opacity-50"
          >
            {saving ? "Đang lưu…" : "Lưu"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

const PAGE_SIZES = [12, 24, 48, 96] as const;

export default function MailboxesPage() {
  const [mailboxes, setMailboxes] = useState<GmailMailbox[]>([]);
  const [blocks, setBlocks]       = useState<MailboxServiceBlock[]>([]);
  const [allServices, setAllServices] = useState<string[]>([]);
  const [loading, setLoading]     = useState(true);
  const [toast, setToast]         = useState<{ msg: string; ok: boolean } | null>(null);
  const [editTarget, setEditTarget] = useState<GmailMailbox | "new" | null>(null);
  const [detailTarget, setDetailTarget] = useState<GmailMailbox | null>(null);
  const [deleting, setDeleting]   = useState<string | null>(null);
  const [refreshingSet, setRefreshingSet] = useState<Set<string>>(new Set());
  const [refreshingAll, setRefreshingAll] = useState(false);
  const [addBlockTarget, setAddBlockTarget] = useState<string | null>(null);
  const [opening, setOpening] = useState<string | null>(null);
  const [totpData, setTotpData] = useState<Record<string, { code: string; remaining: number } | null>>({});
  const [totpLoading, setTotpLoading] = useState<string | null>(null);

  // ── Search & Filter & Pagination ─────────────────────────────────────────
  const [search, setSearch]             = useState("");
  const [filterStatus, setFilterStatus] = useState<"all" | "active" | "disabled">("all");
  const [filterSession, setFilterSession] = useState<"all" | "has_session" | "no_session">("all");
  const [filterBlock, setFilterBlock]   = useState<"all" | "blocked" | "clean">("all");
  const [page, setPage]                 = useState(1);
  const [pageSize, setPageSize]         = useState<number>(24);

  const showToast = (msg: string, ok: boolean) => {
    setToast({ msg, ok });
    setTimeout(() => setToast(null), 4000);
  };

  const load = useCallback(() => {
    setLoading(true);
    Promise.all([api.getGmailMailboxes(), api.getMailboxBlocks(), api.getServices()])
      .then(([mbs, bks, svcs]) => { setMailboxes(mbs); setBlocks(bks); setAllServices(svcs); })
      .catch((e) => showToast(e.message, false))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  // Countdown TOTP remaining
  useEffect(() => {
    const activeEmails = Object.entries(totpData).filter(([, v]) => v !== null);
    if (activeEmails.length === 0) return;
    const timer = setInterval(() => {
      setTotpData((prev) => {
        const next = { ...prev };
        for (const [email, data] of Object.entries(next)) {
          if (data && data.remaining > 1) {
            next[email] = { ...data, remaining: data.remaining - 1 };
          } else if (data) {
            next[email] = null;
          }
        }
        return next;
      });
    }, 1000);
    return () => clearInterval(timer);
  }, [Object.keys(totpData).filter((k) => totpData[k] !== null).join(",")]);

  // blocks lookup: email → service[]
  const blocksByEmail = blocks.reduce<Record<string, MailboxServiceBlock[]>>((acc, b) => {
    (acc[b.email] ??= []).push(b);
    return acc;
  }, {});

  // ── Derived: filtered + paginated ────────────────────────────────────────
  const filtered = mailboxes.filter((m) => {
    if (search && !m.email.toLowerCase().includes(search.toLowerCase())) return false;
    if (filterStatus === "active"   && m.disabled)  return false;
    if (filterStatus === "disabled" && !m.disabled) return false;
    if (filterSession === "has_session" && !m.google_auth_state) return false;
    if (filterSession === "no_session"  &&  m.google_auth_state) return false;
    const hasBlock = (blocksByEmail[m.email]?.length ?? 0) > 0;
    if (filterBlock === "blocked" && !hasBlock) return false;
    if (filterBlock === "clean"   &&  hasBlock) return false;
    return true;
  });

  const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize));
  const safePage   = Math.min(page, totalPages);
  const paginated  = filtered.slice((safePage - 1) * pageSize, safePage * pageSize);

  const handleUnblock = async (email: string, service: string) => {
    try {
      await api.removeMailboxBlock(email, service);
      setBlocks((prev) => prev.filter((b) => !(b.email === email && b.service === service)));
      showToast(`Đã unblock ${email} cho ${service}`, true);
    } catch (e: any) {
      showToast(e.message, false);
    }
  };

  const handleBlockAdded = (block: MailboxServiceBlock) => {
    setBlocks((prev) => [...prev, block]);
    setAddBlockTarget(null);
    showToast(`Đã block ${block.email} cho ${block.service}`, true);
  };

  const handleSaved = (m: GmailMailbox) => {
    setMailboxes((prev) => {
      const idx = prev.findIndex((x) => x.email === m.email);
      return idx >= 0
        ? prev.map((x, i) => (i === idx ? m : x))
        : [...prev, m];
    });
    setEditTarget(null);
    showToast("Đã lưu mailbox", true);
  };

  const handleDelete = async (email: string) => {
    const ok = await confirm(`Xóa mailbox ${email}?`);
    if (!ok) return;
    setDeleting(email);
    try {
      await api.deleteGmailMailbox(email);
      setMailboxes((prev) => prev.filter((m) => m.email !== email));
      showToast("Đã xóa", true);
    } catch (e: any) {
      showToast(e.message, false);
    } finally {
      setDeleting(null);
    }
  };

  const toggleDisabled = async (m: GmailMailbox) => {
    try {
      const updated = await api.upsertGmailMailbox({ ...m, disabled: !m.disabled });
      setMailboxes((prev) => prev.map((x) => (x.email === m.email ? updated : x)));
    } catch (e: any) {
      showToast(e.message, false);
    }
  };

  const handleRefreshSession = async (email: string) => {
    setRefreshingSet(prev => new Set(prev).add(email));
    try {
      await api.refreshMailboxSession(email);
      showToast(`Đã lưu Google session cho ${email}`, true);
      load(); // reload để cập nhật updated_at
    } catch (e: any) {
      showToast(`Lỗi: ${e.message}`, false);
    } finally {
      setRefreshingSet(prev => { const next = new Set(prev); next.delete(email); return next; });
    }
  };

  const handleRefreshAllSessions = async () => {
    setRefreshingAll(true);
    try {
      const res = await api.refreshAllMailboxSessions();
      showToast(`Đã refresh ${res.ok}/${res.total} sessions${res.fail > 0 ? ` (đỏ ${res.fail})` : ""}`, res.fail === 0);
      load();
    } catch (e: any) {
      showToast(`Lỗi: ${e.message}`, false);
    } finally {
      setRefreshingAll(false);
    }
  };

  const handleOpenBrowser = async (email: string) => {
    setOpening(email);
    try {
      await api.openMailboxBrowser(email);
      showToast(`Đã mở browser cho ${email}`, true);
    } catch (e: any) {
      showToast(`Lỗi: ${e.message}`, false);
    } finally {
      setOpening(null);
    }
  };

  const handleShowTotp = async (email: string) => {
    // Toggle off nếu đang hiện
    if (totpData[email]) {
      setTotpData((prev) => ({ ...prev, [email]: null }));
      return;
    }
    setTotpLoading(email);
    try {
      const res = await api.getMailboxTotp(email);
      setTotpData((prev) => ({ ...prev, [email]: { code: res.code, remaining: res.remaining } }));
      // Auto-hide sau khi hết thời gian
      setTimeout(() => {
        setTotpData((prev) => ({ ...prev, [email]: null }));
      }, res.remaining * 1000);
    } catch (e: any) {
      showToast(`TOTP: ${e.message}`, false);
    } finally {
      setTotpLoading(null);
    }
  };

  const active   = mailboxes.filter((m) => !m.disabled).length;
  const disabled = mailboxes.filter((m) => m.disabled).length;
  const blocked  = new Set(blocks.map((b) => b.email)).size;

  // Reset về page 1 khi thay đổi filter/search/pageSize
  useEffect(() => { setPage(1); }, [search, filterStatus, filterSession, filterBlock, pageSize]);

  return (
    <div className="flex-1 min-h-0 flex flex-col">
      {/* Toast */}
      {toast && (
        <div className={`fixed top-4 right-4 z-50 px-4 py-2.5 rounded-lg text-sm font-medium shadow-lg ${toast.ok ? "bg-emerald-600 text-white" : "bg-red-600 text-white"}`}>
          {toast.msg}
        </div>
      )}

      {/* Header */}
      <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between shrink-0">
        <div>
          <h1 className="text-base font-semibold text-gray-900">Gmail Mailboxes</h1>
          <p className="text-xs text-gray-500 mt-0.5">
            {mailboxes.length} mailbox
            {active > 0 && <span className="ml-1 text-emerald-600">· {active} active</span>}
            {disabled > 0 && <span className="ml-1 text-red-500">· {disabled} disabled</span>}
            {blocked > 0 && <span className="ml-1 text-amber-600">· {blocked} có service block</span>}
          </p>
        </div>
        <button
          onClick={() => setEditTarget("new")}
          className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium bg-brand-600 text-white rounded-lg hover:bg-brand-700"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          Thêm mailbox
        </button>
        <button
          onClick={handleRefreshAllSessions}
          disabled={refreshingAll || refreshingSet.size > 0}
          className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium border border-gray-200 text-gray-700 rounded-lg hover:bg-gray-50 disabled:opacity-50"
          title="Login Google cho tất cả mailbox có password"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          {refreshingAll ? "Đang refresh…" : "Get All Sessions"}
        </button>
      </div>

      {/* Search & Filter bar */}
      <div className="px-6 py-3 border-b border-gray-100 flex flex-wrap items-center gap-2 shrink-0 bg-gray-50/50">
        {/* Search input */}
        <div className="relative flex-1 min-w-[200px] max-w-sm">
          <svg className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input
            type="text"
            placeholder="Tìm email..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-8 pr-8 py-1.5 text-sm border border-gray-200 rounded-lg focus:outline-none focus:border-brand-400 bg-white"
          />
          {search && (
            <button onClick={() => setSearch("")} className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-300 hover:text-gray-500">×</button>
          )}
        </div>

        {/* Status filter */}
        <select
          value={filterStatus}
          onChange={(e) => setFilterStatus(e.target.value as typeof filterStatus)}
          className="text-sm border border-gray-200 rounded-lg px-2 py-1.5 bg-white focus:outline-none focus:border-brand-400"
        >
          <option value="all">Tất cả trạng thái</option>
          <option value="active">Active</option>
          <option value="disabled">Disabled</option>
        </select>

        {/* Session filter */}
        <select
          value={filterSession}
          onChange={(e) => setFilterSession(e.target.value as typeof filterSession)}
          className="text-sm border border-gray-200 rounded-lg px-2 py-1.5 bg-white focus:outline-none focus:border-brand-400"
        >
          <option value="all">Tất cả session</option>
          <option value="has_session">Có session</option>
          <option value="no_session">Chưa có session</option>
        </select>

        {/* Block filter */}
        <select
          value={filterBlock}
          onChange={(e) => setFilterBlock(e.target.value as typeof filterBlock)}
          className="text-sm border border-gray-200 rounded-lg px-2 py-1.5 bg-white focus:outline-none focus:border-brand-400"
        >
          <option value="all">Tất cả blocks</option>
          <option value="blocked">Có service block</option>
          <option value="clean">Không bị block</option>
        </select>

        {/* Result count */}
        <span className="text-xs text-gray-400 ml-1">
          {filtered.length !== mailboxes.length
            ? `${filtered.length} / ${mailboxes.length}`
            : `${mailboxes.length}`} mailbox
        </span>

        {/* Clear filters */}
        {(search || filterStatus !== "all" || filterSession !== "all" || filterBlock !== "all") && (
          <button
            onClick={() => { setSearch(""); setFilterStatus("all"); setFilterSession("all"); setFilterBlock("all"); }}
            className="text-xs text-brand-600 hover:text-brand-800 underline ml-auto"
          >
            Xóa bộ lọc
          </button>
        )}
      </div>

      {/* Table */}
      <div className="flex-1 min-h-0 overflow-auto p-6">
        {loading ? (
          <div className="text-sm text-gray-400 text-center py-12">Đang tải…</div>
        ) : mailboxes.length === 0 ? (
          <div className="text-sm text-gray-400 text-center py-12">
            Chưa có mailbox nào.{" "}
            <button onClick={() => setEditTarget("new")} className="text-brand-600 hover:underline">
              Thêm ngay
            </button>
          </div>
        ) : filtered.length === 0 ? (
          <div className="text-sm text-gray-400 text-center py-12">
            Không có mailbox nào khớp bộ lọc.{" "}
            <button onClick={() => { setSearch(""); setFilterStatus("all"); setFilterSession("all"); setFilterBlock("all"); }} className="text-brand-600 hover:underline">
              Xóa bộ lọc
            </button>
          </div>
        ) : (
          <>
          <div className="grid grid-cols-3 gap-3">
            {paginated.map((m) => {
              const mBlocks = blocksByEmail[m.email] ?? [];
              return (
                <div
                  key={m.email}
                  className={`bg-white rounded-xl border border-gray-100 p-4 flex flex-col gap-3 ${m.disabled ? "opacity-60" : ""}`}
                >
                  {/* top row: email + status toggle */}
                  <div className="flex items-start justify-between gap-2">
                    <span className="font-mono text-xs text-gray-800 break-all leading-tight">{m.email}</span>
                    <button
                      onClick={() => toggleDisabled(m)}
                      className={`shrink-0 inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full cursor-pointer transition-colors ${
                        m.disabled
                          ? "bg-red-50 text-red-600 hover:bg-red-100"
                          : "bg-emerald-50 text-emerald-700 hover:bg-emerald-100"
                      }`}
                    >
                      <span className={`w-1.5 h-1.5 rounded-full ${m.disabled ? "bg-red-500" : "bg-emerald-500"}`} />
                      {m.disabled ? "Disabled" : "Active"}
                    </button>
                  </div>

                  {/* meta row: TOTP / Session / Updated */}
                  <div className="grid grid-cols-3 gap-2 text-xs">
                    <div className="flex flex-col gap-0.5">
                      <span className="text-gray-400">TOTP</span>
                      {m.totp_secret ? (
                        totpData[m.email] ? (
                          <button
                            onClick={() => {
                              navigator.clipboard.writeText(totpData[m.email]!.code);
                              showToast(`Copied: ${totpData[m.email]!.code}`, true);
                            }}
                            className="text-left font-mono text-brand-600 font-bold hover:text-brand-800 tracking-widest"
                            title="Click để copy"
                          >
                            {totpData[m.email]!.code}
                            <span className="ml-1 text-gray-400 font-normal text-[10px]">{totpData[m.email]!.remaining}s</span>
                          </button>
                        ) : (
                          <button
                            onClick={() => handleShowTotp(m.email)}
                            disabled={totpLoading === m.email}
                            className="text-left text-emerald-600 font-medium hover:text-emerald-800"
                          >
                            {totpLoading === m.email ? "…" : "✓ Show"}
                          </button>
                        )
                      ) : (
                        <span className="text-gray-300">—</span>
                      )}
                    </div>
                    <div className="flex flex-col gap-0.5">
                      <span className="text-gray-400">Session</span>
                      {m.google_auth_state
                        ? <span className="text-emerald-600 font-medium">✓ Active</span>
                        : <span className="text-gray-300">—</span>}
                    </div>
                    <div className="flex flex-col gap-0.5">
                      <span className="text-gray-400">Updated</span>
                      <span className="text-gray-500">{m.updated_at.slice(0, 10)}</span>
                    </div>
                  </div>

                  {/* blocks */}
                  {mBlocks.length > 0 && (
                    <div className="flex flex-wrap gap-1">
                      {mBlocks.map((b) => (
                        <span
                          key={b.service}
                          className="inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full bg-amber-50 text-amber-700"
                          title={b.reason || b.service}
                        >
                          {b.service}
                          <button
                            onClick={() => handleUnblock(m.email, b.service)}
                            className="ml-0.5 text-amber-400 hover:text-amber-700 leading-none"
                            title={`Unblock ${b.service}`}
                          >×</button>
                        </span>
                      ))}
                    </div>
                  )}

                  {/* actions */}
                  <div className="flex items-center gap-1 pt-1 border-t border-gray-50">
                    <button
                      onClick={() => handleOpenBrowser(m.email)}
                      disabled={opening === m.email || !m.google_auth_state}
                      className="p-1.5 text-gray-400 hover:text-blue-500 rounded disabled:opacity-30"
                      title={m.google_auth_state ? "Mo browser voi session nay" : "Chua co session - refresh truoc"}
                    >
                      {opening === m.email ? (
                        <svg className="w-3.5 h-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                        </svg>
                      ) : (
                        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                        </svg>
                      )}
                    </button>
                    <button
                      onClick={() => setDetailTarget(m)}
                      className="p-1.5 text-gray-400 hover:text-brand-600 rounded"
                      title="Chi tiết toàn bộ thông tin"
                    >
                      <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                    </button>
                    <button
                      onClick={() => handleRefreshSession(m.email)}
                      disabled={refreshingAll || refreshingSet.has(m.email)}
                      className="p-1.5 text-gray-400 hover:text-emerald-600 rounded disabled:opacity-50"
                      title="Login Google & lưu session"
                    >
                      {refreshingSet.has(m.email) ? (
                        <svg className="w-3.5 h-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                        </svg>
                      ) : (
                        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                        </svg>
                      )}
                    </button>
                    <button
                      onClick={() => setAddBlockTarget(m.email)}
                      className="p-1.5 text-gray-400 hover:text-amber-600 rounded"
                      title="Block cho service"
                    >
                      <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636" />
                      </svg>
                    </button>
                    <button
                      onClick={() => setEditTarget(m)}
                      className="p-1.5 text-gray-400 hover:text-brand-600 rounded"
                      title="Sửa"
                    >
                      <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                      </svg>
                    </button>
                    <button
                      onClick={() => handleDelete(m.email)}
                      disabled={deleting === m.email}
                      className="p-1.5 text-gray-400 hover:text-red-600 rounded disabled:opacity-50 ml-auto"
                      title="Xóa"
                    >
                      <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                      </svg>
                    </button>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Pagination */}
          <div className="mt-4 flex items-center justify-between gap-2">
            <div className="flex items-center gap-1.5">
              <span className="text-xs text-gray-400">Hiển thị</span>
              <select
                value={pageSize}
                onChange={(e) => setPageSize(Number(e.target.value))}
                className="text-xs border border-gray-200 rounded px-1.5 py-1 bg-white focus:outline-none"
              >
                {PAGE_SIZES.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
              <span className="text-xs text-gray-400">/ trang</span>
            </div>

            <div className="flex items-center gap-1">
              <button
                onClick={() => setPage(1)}
                disabled={safePage === 1}
                className="px-2 py-1 text-xs border border-gray-200 rounded hover:bg-gray-50 disabled:opacity-30"
              >«</button>
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={safePage === 1}
                className="px-2 py-1 text-xs border border-gray-200 rounded hover:bg-gray-50 disabled:opacity-30"
              >‹</button>

              {/* Page numbers */}
              {Array.from({ length: totalPages }, (_, i) => i + 1)
                .filter((p) => p === 1 || p === totalPages || Math.abs(p - safePage) <= 2)
                .reduce<(number | "...")[]>((acc, p, i, arr) => {
                  if (i > 0 && p - (arr[i - 1] as number) > 1) acc.push("...");
                  acc.push(p);
                  return acc;
                }, [])
                .map((p, i) =>
                  p === "..." ? (
                    <span key={`ellipsis-${i}`} className="px-2 py-1 text-xs text-gray-400">…</span>
                  ) : (
                    <button
                      key={p}
                      onClick={() => setPage(p as number)}
                      className={`px-2.5 py-1 text-xs border rounded ${
                        safePage === p
                          ? "bg-brand-600 text-white border-brand-600"
                          : "border-gray-200 hover:bg-gray-50"
                      }`}
                    >{p}</button>
                  )
                )}

              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={safePage === totalPages}
                className="px-2 py-1 text-xs border border-gray-200 rounded hover:bg-gray-50 disabled:opacity-30"
              >›</button>
              <button
                onClick={() => setPage(totalPages)}
                disabled={safePage === totalPages}
                className="px-2 py-1 text-xs border border-gray-200 rounded hover:bg-gray-50 disabled:opacity-30"
              >»</button>
            </div>

            <span className="text-xs text-gray-400">
              {(safePage - 1) * pageSize + 1}–{Math.min(safePage * pageSize, filtered.length)} / {filtered.length}
            </span>
          </div>
          </>
        )}
      </div>

      {/* Modal */}
      {editTarget !== null && (
        <MailboxModal
          initial={editTarget === "new" ? undefined : editTarget}
          onClose={() => setEditTarget(null)}
          onSaved={handleSaved}
        />
      )}
      {addBlockTarget !== null && (
        <AddBlockModal
          email={addBlockTarget}
          existing={(blocksByEmail[addBlockTarget] ?? []).map((b) => b.service)}
          services={allServices}
          onClose={() => setAddBlockTarget(null)}
          onAdded={handleBlockAdded}
        />
      )}
      {detailTarget !== null && (
        <MailboxDetailModal
          mailbox={detailTarget}
          blocks={blocksByEmail[detailTarget.email] ?? []}
          onClose={() => setDetailTarget(null)}
        />
      )}
    </div>
  );
}

// ── Mailbox Detail Modal ──────────────────────────────────────────────────────

function MailboxDetailModal({
  mailbox: m,
  blocks,
  onClose,
}: {
  mailbox: GmailMailbox;
  blocks: MailboxServiceBlock[];
  onClose: () => void;
}) {
  const row = (label: string, value: React.ReactNode) => (
    <div className="flex flex-col gap-0.5">
      <span className="text-xs text-gray-400">{label}</span>
      <span className="text-xs font-mono text-gray-800 break-all whitespace-pre-wrap">{value}</span>
    </div>
  );

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-lg max-h-[90vh] flex flex-col">
        <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between shrink-0">
          <div>
            <h2 className="text-base font-semibold text-gray-900">Chi tiết Mailbox</h2>
            <p className="text-xs text-gray-400 mt-0.5 font-mono">{m.email}</p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl leading-none">×</button>
        </div>
        <div className="overflow-auto flex-1 px-5 py-4 space-y-3">
          {row("email", m.email)}
          {row("app_password", m.app_password || "—")}
          {row("totp_secret", m.totp_secret || "—")}
          {row("password", m.password || "—")}
          {row("source_email", m.source_email || "—")}
          {row("disabled", m.disabled ? "true" : "false")}
          {row("created_at", m.created_at)}
          {row("updated_at", m.updated_at)}
          <div className="flex flex-col gap-0.5">
            <span className="text-xs text-gray-400">google_auth_state</span>
            <span className="text-xs font-mono text-gray-800 break-all">
              {m.google_auth_state
                ? `[có session — ${m.google_auth_state.length} chars]`
                : "—"}
            </span>
          </div>
          {blocks.length > 0 && (
            <div className="flex flex-col gap-1">
              <span className="text-xs text-gray-400">service_blocks</span>
              {blocks.map((b) => (
                <div key={b.service} className="text-xs font-mono text-amber-700 bg-amber-50 rounded px-2 py-1">
                  {b.service}{b.reason ? ` — ${b.reason}` : ""} <span className="text-gray-400">[{b.blocked_at.slice(0, 10)}]</span>
                </div>
              ))}
            </div>
          )}
        </div>
        <div className="px-5 py-3 border-t border-gray-100 flex justify-end shrink-0">
          <button onClick={onClose} className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800">Đóng</button>
        </div>
      </div>
    </div>
  );
}
