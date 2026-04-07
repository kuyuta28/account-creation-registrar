/**
 * GmailVariationsModal.tsx
 *
 * Modal hiển thị tất cả Gmail alias variations (+ dot . googlemail) từ một base Gmail account.
 * User chọn kỹ thuật muốn dùng, xem danh sách variations và availability trong DB,
 * rồi thêm trực tiếp vào DB cho một service cụ thể.
 */

import { useState, useEffect, useCallback } from "react";
import { api, GmailVariationResult, GmailVariationDefaults } from "../api/client";

interface Props {
  baseEmail: string;        // Gmail gốc (e.g. "abc@gmail.com")
  service: string;          // Service đang chọn để check/add
  availableServices: string[];
  onServiceChange: (svc: string) => void;
  onClose: () => void;
  onAdded?: (count: number) => void;
}

type Technique = "plus" | "dot" | "googlemail";

const TECHNIQUE_LABELS: Record<Technique, { label: string; desc: string; icon: string }> = {
  plus: {
    label: "+tag",
    desc: "abc+tag@gmail.com — vô hạn variations",
    icon: "＋",
  },
  dot: {
    label: "dot (.)",
    desc: "a.b.c@gmail.com — 2^(len-1) variations",
    icon: "·",
  },
  googlemail: {
    label: "@googlemail",
    desc: "duplicate tất cả variations → @googlemail.com",
    icon: "G",
  },
};

export default function GmailVariationsModal({ baseEmail, service, availableServices, onServiceChange, onClose, onAdded }: Props) {
  const [techniques, setTechniques] = useState<Set<Technique>>(new Set(["plus"]));
  const [plusTags, setPlusTags] = useState("1,2,3,4,5,6,7,8,9,10");
  const [defaultsLoaded, setDefaultsLoaded] = useState(false);
  const [variations, setVariations] = useState<GmailVariationResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [adding, setAdding] = useState(false);
  const [addError, setAddError] = useState("");
  const [addDone, setAddDone] = useState(0);

  const toggleTechnique = (t: Technique) => {
    setTechniques((prev) => {
      const next = new Set(prev);
      next.has(t) ? next.delete(t) : next.add(t);
      return next;
    });
  };

  const fetchVariations = useCallback(async () => {
    setLoading(true);
    setError("");
    setVariations([]);
    setSelected(new Set());
    try {
      const tags = plusTags
        .split(",")
        .map((t) => t.trim())
        .filter(Boolean);
      const res = await api.getGmailVariations({
        base_email: baseEmail,
        service,
        use_plus: techniques.has("plus"),
        use_dot: techniques.has("dot"),
        use_googlemail: techniques.has("googlemail"),
        plus_tags: techniques.has("plus") ? tags : [],
      });
      setVariations(res.variations);
      // Auto-select tất cả available
      setSelected(new Set(res.variations.filter((v) => v.available).map((v) => v.email)));
    } catch (e: any) {
      setError(e.message ?? "Lỗi không xác định");
    } finally {
      setLoading(false);
    }
  }, [baseEmail, service, techniques, plusTags]);

  useEffect(() => {
    api.getGmailVariationDefaults().then((d: GmailVariationDefaults) => {
      const next = new Set<Technique>();
      if (d.use_plus) next.add("plus");
      if (d.use_dot) next.add("dot");
      if (d.use_googlemail) next.add("googlemail");
      setTechniques(next.size > 0 ? next : new Set(["plus"]));
      setPlusTags(d.plus_tags);
      setDefaultsLoaded(true);
    });
  }, []);

  useEffect(() => {
    fetchVariations();
  }, []); // chỉ fetch lần đầu

  const toggleSelect = (email: string, available: boolean) => {
    if (!available) return;
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(email) ? next.delete(email) : next.add(email);
      return next;
    });
  };

  const selectAll = () =>
    setSelected(new Set(variations.filter((v) => v.available).map((v) => v.email)));
  const deselectAll = () => setSelected(new Set());

  const handleAdd = async () => {
    if (selected.size === 0) return;
    setAdding(true);
    setAddError("");
    let added = 0;
    const errors: string[] = [];

    await Promise.all(
      [...selected].map(async (email) => {
        try {
          await api.addAccount(service, email, "", "", "", "", baseEmail);
          added++;
        } catch (e: any) {
          errors.push(`${email}: ${e.message}`);
        }
      })
    );

    setAdding(false);
    setAddDone(added);
    if (errors.length > 0) {
      setAddError(errors.join("\n"));
    }
    if (added > 0) {
      // Refresh để update availability
      fetchVariations();
      onAdded?.(added);
    }
  };

  const availableCount = variations.filter((v) => v.available).length;
  const techniqueGroups: Record<string, GmailVariationResult[]> = {};
  for (const v of variations) {
    if (!techniqueGroups[v.technique]) techniqueGroups[v.technique] = [];
    techniqueGroups[v.technique].push(v);
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-2xl flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
          <div>
            <h2 className="text-base font-semibold text-gray-900">Gmail Variations</h2>
            <p className="text-xs text-gray-500 mt-0.5">
              <span className="font-mono text-brand-600">{baseEmail}</span>
              {" → "}
              <span className="font-medium">{service}</span>
            </p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl leading-none">×</button>
        </div>

        {/* Config */}
        <div className="px-5 py-3 border-b border-gray-100 space-y-3">
        {/* Service selector */}
          <div className="flex items-center gap-2">
            <label className="text-xs text-gray-500 whitespace-nowrap">Service:</label>
            <select
              value={service}
              onChange={(e) => { onServiceChange(e.target.value); setVariations([]); setSelected(new Set()); }}
              className="px-2 py-1 text-xs border border-gray-200 rounded-md focus:outline-none focus:border-brand-400 bg-white"
            >
              {availableServices.map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </div>

          {/* Technique checkboxes */}
          <div className="flex flex-wrap gap-2">
            {(Object.entries(TECHNIQUE_LABELS) as [Technique, typeof TECHNIQUE_LABELS[Technique]][]).map(([key, meta]) => (
              <button
                key={key}
                onClick={() => toggleTechnique(key)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs font-medium transition-colors ${
                  techniques.has(key)
                    ? "border-brand-400 bg-brand-50 text-brand-700"
                    : "border-gray-200 bg-white text-gray-500 hover:border-gray-300"
                }`}
              >
                <span className="w-4 h-4 flex items-center justify-center border rounded border-current text-[10px] font-bold">
                  {techniques.has(key) ? "✓" : meta.icon}
                </span>
                <span>{meta.label}</span>
                <span className="text-gray-400 font-normal hidden sm:inline">— {meta.desc}</span>
              </button>
            ))}
          </div>

          {/* Plus tags config */}
          {techniques.has("plus") && (
            <div className="flex items-center gap-2">
              <label className="text-xs text-gray-500 whitespace-nowrap">Plus tags:</label>
              <input
                type="text"
                value={plusTags}
                onChange={(e) => setPlusTags(e.target.value)}
                placeholder="1,2,3,promo,beta..."
                className="flex-1 px-2 py-1 text-xs border border-gray-200 rounded-md focus:outline-none focus:border-brand-400 font-mono"
              />
              <span className="text-xs text-gray-400">
                {plusTags.split(",").filter((t) => t.trim()).length} tags
              </span>
            </div>
          )}

          {/* Hint khi googlemail bật nhưng không có technique nào để nhân */}
          {techniques.has("googlemail") && !techniques.has("plus") && !techniques.has("dot") && (
            <p className="text-[11px] text-amber-600 bg-amber-50 border border-amber-200 rounded-md px-2.5 py-1.5">
              Tick thêm <strong>+tag</strong> hoặc <strong>dot</strong> để nhân đôi variations sang @googlemail.com
            </p>
          )}

          <button
            onClick={fetchVariations}
            disabled={loading || techniques.size === 0 || !defaultsLoaded}
            className="px-3 py-1.5 bg-brand-600 hover:bg-brand-700 disabled:bg-gray-300 text-white text-xs rounded-lg font-medium transition-colors"
          >
            {loading ? "Đang tải..." : "Tạo variations"}
          </button>
        </div>

        {/* Results */}
        <div className="flex-1 overflow-y-auto px-5 py-3">
          {error && (
            <div className="mb-3 px-3 py-2 bg-red-50 border border-red-200 rounded-lg text-xs text-red-700">{error}</div>
          )}

          {variations.length > 0 && (
            <>
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs text-gray-500">
                  <span className="font-medium text-gray-800">{variations.length}</span> variations ·{" "}
                  <span className="text-emerald-600 font-medium">{availableCount} available</span> ·{" "}
                  <span className="text-blue-600 font-medium">{selected.size} selected</span>
                </span>
                <div className="flex gap-2">
                  <button onClick={selectAll} className="text-xs text-brand-600 hover:underline">Select all</button>
                  <span className="text-gray-300">|</span>
                  <button onClick={deselectAll} className="text-xs text-gray-500 hover:underline">Deselect</button>
                </div>
              </div>

              {/* Group by technique */}
              {(Object.entries(techniqueGroups) as [string, GmailVariationResult[]][]).map(([tech, items]) => (
                <div key={tech} className="mb-4">
                  <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-1.5">
                    {TECHNIQUE_LABELS[tech as Technique]?.label ?? tech} ({items.length})
                  </h4>
                  <div className="grid grid-cols-1 gap-0.5">
                    {items.map((v) => (
                      <label
                        key={v.email}
                        className={`flex items-center gap-2.5 px-2.5 py-1.5 rounded-lg cursor-pointer transition-colors ${
                          !v.available
                            ? "opacity-40 cursor-not-allowed bg-gray-50"
                            : selected.has(v.email)
                            ? "bg-brand-50 hover:bg-brand-100"
                            : "hover:bg-gray-50"
                        }`}
                      >
                        <input
                          type="checkbox"
                          checked={selected.has(v.email)}
                          disabled={!v.available}
                          onChange={() => toggleSelect(v.email, v.available)}
                          className="accent-brand-600"
                        />
                        <span className="font-mono text-xs text-gray-800 flex-1">{v.email}</span>
                        {v.available ? (
                          <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-emerald-50 text-emerald-600 font-medium">available</span>
                        ) : (
                          <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-gray-100 text-gray-400 font-medium">used</span>
                        )}
                      </label>
                    ))}
                  </div>
                </div>
              ))}
            </>
          )}

          {!loading && variations.length === 0 && !error && (
            <p className="text-sm text-gray-400 text-center py-8">Chọn kỹ thuật rồi nhấn "Tạo variations"</p>
          )}
        </div>

        {/* Footer */}
        <div className="px-5 py-3 border-t border-gray-100 flex items-center justify-between gap-3">
          <div className="flex-1">
            {addDone > 0 && (
              <span className="text-xs text-emerald-600 font-medium">✓ Đã thêm {addDone} accounts</span>
            )}
            {addError && (
              <span className="text-xs text-red-600 font-medium">{addError}</span>
            )}
          </div>
          <button onClick={onClose} className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800">
            Đóng
          </button>
          <button
            onClick={handleAdd}
            disabled={selected.size === 0 || adding}
            className="px-4 py-2 bg-brand-600 hover:bg-brand-700 disabled:bg-gray-300 text-white text-sm rounded-lg font-medium transition-colors"
          >
            {adding ? "Đang thêm..." : `Thêm ${selected.size} accounts`}
          </button>
        </div>
      </div>
    </div>
  );
}
