import { useEffect, useState } from "react";
import { api } from "../api/client";

interface ServiceRow {
  name: string;
}

export default function ServicesPage() {
  const [services, setServices] = useState<ServiceRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [newName, setNewName] = useState("");
  const [adding, setAdding] = useState(false);
  const [addError, setAddError] = useState("");

  const [deletingSet, setDeletingSet] = useState<Set<string>>(new Set());

  const [toast, setToast] = useState<{ msg: string; ok: boolean } | null>(null);
  const showToast = (msg: string, ok: boolean) => {
    setToast({ msg, ok });
    setTimeout(() => setToast(null), 3000);
  };

  const load = () => {
    setLoading(true);
    setError("");
    api.getServices()
      .then((list) => setServices(list.map((name) => ({ name }))))
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const handleAdd = () => {
    const name = newName.trim().toUpperCase();
    if (!name) { setAddError("Tên service không được trống"); return; }
    setAdding(true);
    setAddError("");
    api.addService(name)
      .then(() => {
        showToast(`Đã thêm service ${name}`, true);
        setNewName("");
        load();
      })
      .catch((e) => setAddError(String(e)))
      .finally(() => setAdding(false));
  };

  const handleDelete = async (name: string) => {
    const ok = await confirm(`Xóa service "${name}"?\n\nLưu ý: Các accounts thuộc service này sẽ không bị xóa nhưng service sẽ không còn khả dụng.`);
    if (!ok) return;
    setDeletingSet((s) => new Set(s).add(name));
    api.deleteService(name)
      .then(() => {
        showToast(`Đã xóa service ${name}`, true);
        load();
      })
      .catch((e) => showToast(`Lỗi: ${String(e)}`, false))
      .finally(() => setDeletingSet((s) => { const n = new Set(s); n.delete(name); return n; }));
  };

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
      <div className="flex items-center justify-between mb-5">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Services</h2>
          <p className="text-xs text-gray-500 mt-0.5">Quản lý danh sách services trong hệ thống</p>
        </div>
        <button onClick={load} disabled={loading} className="btn-secondary py-2">
          <svg className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
        </button>
      </div>

      {/* Add service form */}
      <div className="bg-white rounded-xl border border-gray-200 p-4 mb-5">
        <h3 className="text-sm font-semibold text-gray-700 mb-3">Thêm service mới</h3>
        {addError && (
          <div className="text-xs text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2 mb-3">{addError}</div>
        )}
        <div className="flex gap-2">
          <input
            type="text"
            value={newName}
            onChange={(e) => setNewName(e.target.value.toUpperCase())}
            onKeyDown={(e) => e.key === "Enter" && handleAdd()}
            placeholder="VD: MIDJOURNEY"
            className="flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm font-mono uppercase focus:ring-2 focus:ring-brand-500 focus:border-brand-500"
          />
          <button
            onClick={handleAdd}
            disabled={adding || !newName.trim()}
            className="btn-primary text-sm px-4"
          >
            {adding ? "Đang thêm..." : "Thêm"}
          </button>
        </div>
        <p className="text-xs text-gray-400 mt-2">Tên sẽ được tự động chuyển thành UPPERCASE. <code>has_registrar</code> = false (thêm thủ công, không auto-create).</p>
      </div>

      {/* Error */}
      {error && (
        <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2 mb-4">{error}</div>
      )}

      {/* Table */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-100 bg-gray-50">
              <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Service</th>
              <th className="text-right px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading && services.length === 0 && (
              <tr>
                <td colSpan={2} className="text-center py-12 text-gray-400 text-sm">Đang tải...</td>
              </tr>
            )}
            {!loading && services.length === 0 && (
              <tr>
                <td colSpan={2} className="text-center py-12 text-gray-400 text-sm">Chưa có service nào</td>
              </tr>
            )}
            {services.map(({ name }) => (
              <tr key={name} className="border-b border-gray-50 last:border-0 hover:bg-gray-50 transition-colors">
                <td className="px-4 py-3">
                  <span className="font-mono text-sm font-medium text-gray-800">{name}</span>
                </td>
                <td className="px-4 py-3 text-right">
                  <button
                    onClick={() => handleDelete(name)}
                    disabled={deletingSet.has(name)}
                    className="text-xs text-red-500 hover:text-red-700 disabled:opacity-40 font-medium transition-colors"
                  >
                    {deletingSet.has(name) ? "Đang xóa..." : "Xóa"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
