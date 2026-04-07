import { useCallback, useEffect, useState } from "react";
import { api, SmsPhone } from "../api/client";

interface SmsPhoneModalProps {
  initial?: SmsPhone;
  onClose: () => void;
  onSaved: (phone: SmsPhone) => void;
}

function SmsPhoneModal({ initial, onClose, onSaved }: SmsPhoneModalProps) {
  const [phone, setPhone] = useState(initial?.phone ?? "");
  const [label, setLabel] = useState(initial?.label ?? "");
  const [disabled, setDisabled] = useState(initial?.disabled ?? false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const handleSave = async () => {
    if (!phone.trim()) {
      setError("Số điện thoại không được để trống");
      return;
    }

    setSaving(true);
    setError("");
    try {
      const saved = await api.upsertSmsPhone({
        phone: phone.trim(),
        label: label.trim(),
        disabled,
      });
      onSaved(saved);
    } catch (e: any) {
      setError(e.message ?? "Lỗi không xác định");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="w-full max-w-md rounded-xl bg-white shadow-2xl">
        <div className="flex items-center justify-between border-b border-gray-100 px-5 py-4">
          <h2 className="text-base font-semibold text-gray-900">
            {initial ? "Sửa SMS Phone" : "Thêm SMS Phone"}
          </h2>
          <button onClick={onClose} className="text-xl leading-none text-gray-400 hover:text-gray-600">×</button>
        </div>
        <div className="space-y-3 px-5 py-4">
          <div>
            <label className="mb-1 block text-xs text-gray-500">Số điện thoại</label>
            <input
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              disabled={!!initial}
              placeholder="0901234567"
              className={`w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm font-mono focus:border-brand-400 focus:outline-none ${initial ? "bg-gray-50 text-gray-400" : ""}`}
            />
          </div>
          <div>
            <label className="mb-1 block text-xs text-gray-500">Label</label>
            <input
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              placeholder="SIM 1 - Ollama OTP"
              className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm focus:border-brand-400 focus:outline-none"
            />
          </div>
          <label className="flex items-center gap-2 text-sm text-gray-600">
            <input
              type="checkbox"
              checked={disabled}
              onChange={(e) => setDisabled(e.target.checked)}
              className="rounded"
            />
            Disabled
          </label>
          {error && <p className="text-xs text-red-600">{error}</p>}
        </div>
        <div className="flex justify-end gap-2 border-t border-gray-100 px-5 py-3">
          <button onClick={onClose} className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800">Hủy</button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
          >
            {saving ? "Đang lưu…" : "Lưu"}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function SmsPhonesPage() {
  const [phones, setPhones] = useState<SmsPhone[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [modalTarget, setModalTarget] = useState<SmsPhone | "new" | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const items = await api.getSmsPhones();
      setPhones(items);
    } catch (e: any) {
      setError(e.message ?? "Không tải được SMS phones");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const handleSaved = (saved: SmsPhone) => {
    setPhones((prev) => {
      const exists = prev.some((item) => item.phone === saved.phone);
      return exists
        ? prev.map((item) => (item.phone === saved.phone ? saved : item))
        : [saved, ...prev];
    });
    setModalTarget(null);
  };

  const handleDelete = async (phone: string) => {
    setDeleting(phone);
    setError("");
    try {
      await api.deleteSmsPhone(phone);
      setPhones((prev) => prev.filter((item) => item.phone !== phone));
    } catch (e: any) {
      setError(e.message ?? "Xóa thất bại");
    } finally {
      setDeleting(null);
    }
  };

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">SMS Phones</h1>
          <p className="mt-0.5 text-sm text-gray-500">
            Quản lý số SIM dùng nhận OTP qua webhook từ điện thoại Android.
          </p>
        </div>
        <button
          onClick={() => setModalTarget("new")}
          className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700"
        >
          + Thêm SIM
        </button>
      </div>

      <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
        Webhook URL mẫu: <span className="font-mono">/api/v1/sms/webhook?phone=0901234567</span>
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-500">Phone</th>
              <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-500">Label</th>
              <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-500">Status</th>
              <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wider text-gray-500">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 bg-white">
            {!loading && phones.length === 0 && (
              <tr>
                <td colSpan={4} className="px-4 py-10 text-center text-sm text-gray-400">
                  Chưa có SIM phone nào
                </td>
              </tr>
            )}
            {phones.map((item) => (
              <tr key={item.phone} className="hover:bg-gray-50">
                <td className="px-4 py-3 font-mono text-sm text-gray-900">{item.phone}</td>
                <td className="px-4 py-3 text-sm text-gray-700">
                  {item.label || <span className="text-gray-400">—</span>}
                </td>
                <td className="px-4 py-3 text-sm">
                  <span className={`rounded-full px-2 py-1 text-xs font-medium ${item.disabled ? "bg-red-50 text-red-700" : "bg-emerald-50 text-emerald-700"}`}>
                    {item.disabled ? "Disabled" : "Active"}
                  </span>
                </td>
                <td className="px-4 py-3 text-right text-sm">
                  <div className="flex items-center justify-end gap-2">
                    <button
                      onClick={() => setModalTarget(item)}
                      className="rounded-lg border border-gray-200 px-3 py-1.5 text-gray-700 hover:bg-gray-100"
                    >
                      Sửa
                    </button>
                    <button
                      onClick={() => void handleDelete(item.phone)}
                      disabled={deleting === item.phone}
                      className="rounded-lg border border-red-200 px-3 py-1.5 text-red-600 hover:bg-red-50 disabled:opacity-50"
                    >
                      {deleting === item.phone ? "Đang xóa…" : "Xóa"}
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {modalTarget && (
        <SmsPhoneModal
          initial={modalTarget === "new" ? undefined : modalTarget}
          onClose={() => setModalTarget(null)}
          onSaved={handleSaved}
        />
      )}
    </div>
  );
}
