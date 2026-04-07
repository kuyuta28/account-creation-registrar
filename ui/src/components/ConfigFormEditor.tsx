import { useState, useCallback, useEffect, useRef } from "react";
import { parse, stringify } from "yaml";

type YamlPrimitive = string | number | boolean | null;
type YamlValue = YamlPrimitive | YamlValue[] | { [key: string]: YamlValue };
type YamlObject = Record<string, YamlValue>;

/* ── Helpers ──────────────────────────────────────── */

const toLabel = (key: string): string =>
  key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

const setAt = (obj: YamlObject, path: string[], value: YamlValue): YamlObject => {
  if (path.length === 1) return { ...obj, [path[0]]: value };
  return {
    ...obj,
    [path[0]]: setAt((obj[path[0]] as YamlObject) ?? {}, path.slice(1), value),
  };
};

/* ── Main ─────────────────────────────────────────── */

interface Props {
  content: string;
  onChange: (yaml: string) => void;
}

export default function ConfigFormEditor({ content, onChange }: Props) {
  const [data, setData] = useState<YamlObject>({});
  const [parseError, setParseError] = useState<string | null>(null);
  const lastEmitted = useRef<string | null>(null);

  useEffect(() => {
    // Skip re-parse if this content came from our own edit
    if (lastEmitted.current !== null && content === lastEmitted.current) return;
    try {
      const parsed = parse(content);
      if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
        setData(parsed as YamlObject);
        setParseError(null);
      } else if (parsed == null) {
        setData({});
        setParseError(null);
      } else {
        setParseError("YAML root phải là object");
      }
    } catch (e: unknown) {
      setParseError(e instanceof Error ? e.message : String(e));
    }
  }, [content]);

  const update = useCallback(
    (path: string[], value: YamlValue) => {
      setData((prev) => {
        const next = setAt(prev, path, value);
        const yaml = stringify(next, { lineWidth: 0 });
        lastEmitted.current = yaml;
        onChange(yaml);
        return next;
      });
    },
    [onChange],
  );

  if (parseError) {
    return (
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="text-center space-y-1">
          <p className="text-red-500 text-sm font-medium">Lỗi parse YAML</p>
          <p className="text-gray-400 text-xs font-mono">{parseError}</p>
          <p className="text-gray-400 text-xs mt-2">Dùng tab <b>Raw</b> để sửa.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-4">
      {Object.entries(data).map(([key, value]) =>
        value !== null && typeof value === "object" && !Array.isArray(value) ? (
          <SectionCard key={key} title={key} fields={value as YamlObject} path={[key]} onUpdate={update} />
        ) : (
          <div key={key} className="border border-gray-200 rounded-lg p-4">
            <Field name={key} value={value} path={[key]} onUpdate={update} />
          </div>
        ),
      )}
    </div>
  );
}

/* ── Section Card ─────────────────────────────────── */

function SectionCard({
  title,
  fields,
  path,
  onUpdate,
}: {
  title: string;
  fields: YamlObject;
  path: string[];
  onUpdate: (p: string[], v: YamlValue) => void;
}) {
  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden">
      <div className="bg-gray-50/80 px-4 py-2.5 border-b border-gray-100">
        <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
          {toLabel(title)}
        </h3>
      </div>
      <div className="p-4 space-y-3">
        {Object.entries(fields).map(([k, v]) => (
          <Field key={k} name={k} value={v} path={[...path, k]} onUpdate={onUpdate} />
        ))}
      </div>
    </div>
  );
}

/* ── Field Renderer ───────────────────────────────── */

function Field({
  name,
  value,
  path,
  onUpdate,
}: {
  name: string;
  value: YamlValue;
  path: string[];
  onUpdate: (p: string[], v: YamlValue) => void;
}) {
  // Boolean → toggle
  if (typeof value === "boolean") {
    return (
      <div className="flex items-center justify-between py-1">
        <label className="text-sm text-gray-600">{toLabel(name)}</label>
        <button
          type="button"
          onClick={() => onUpdate(path, !value)}
          className={`relative w-10 h-[22px] rounded-full transition-colors ${
            value ? "bg-brand-500" : "bg-gray-300"
          }`}
        >
          <span
            className={`absolute top-[3px] left-[3px] w-4 h-4 bg-white rounded-full shadow transition-transform ${
              value ? "translate-x-[18px]" : ""
            }`}
          />
        </button>
      </div>
    );
  }

  // Number
  if (typeof value === "number") {
    return (
      <div className="flex items-center gap-3 py-0.5">
        <label className="text-sm text-gray-600 w-48 shrink-0">{toLabel(name)}</label>
        <input
          type="number"
          value={value}
          onChange={(e) => onUpdate(path, e.target.value === "" ? 0 : Number(e.target.value))}
          className="input flex-1 font-mono text-xs"
        />
      </div>
    );
  }

  // String
  if (typeof value === "string") {
    return (
      <div className="flex items-center gap-3 py-0.5">
        <label className="text-sm text-gray-600 w-48 shrink-0">{toLabel(name)}</label>
        <input
          type="text"
          value={value}
          onChange={(e) => onUpdate(path, e.target.value)}
          className="input flex-1 font-mono text-xs"
        />
      </div>
    );
  }

  // Array of primitives
  if (Array.isArray(value) && value.every((v) => typeof v === "string" || typeof v === "number")) {
    return <ListField name={name} items={value.map(String)} path={path} onUpdate={onUpdate} />;
  }

  // Generic array (fallback)
  if (Array.isArray(value)) {
    return <ListField name={name} items={value.map(String)} path={path} onUpdate={onUpdate} />;
  }

  // Nested object
  if (value !== null && typeof value === "object") {
    const entries = Object.entries(value as YamlObject);
    const allArrays = entries.length > 0 && entries.every(([, v]) => Array.isArray(v));

    if (allArrays) {
      return (
        <DictOfListsField
          name={name}
          data={value as Record<string, string[]>}
          path={path}
          onUpdate={onUpdate}
        />
      );
    }

    return (
      <div className="space-y-2 py-0.5">
        <label className="text-sm font-medium text-gray-500">{toLabel(name)}</label>
        <div className="ml-3 pl-3 border-l-2 border-gray-100 space-y-3">
          {entries.map(([k, v]) => (
            <Field key={k} name={k} value={v} path={[...path, k]} onUpdate={onUpdate} />
          ))}
        </div>
      </div>
    );
  }

  // null / undefined → editable empty string
  return (
    <div className="flex items-center gap-3 py-0.5">
      <label className="text-sm text-gray-600 w-48 shrink-0">{toLabel(name)}</label>
      <input
        type="text"
        value=""
        onChange={(e) => onUpdate(path, e.target.value)}
        className="input flex-1 font-mono text-xs"
        placeholder="(trống)"
      />
    </div>
  );
}

/* ── List Field ───────────────────────────────────── */

function ListField({
  name,
  items,
  path,
  onUpdate,
}: {
  name: string;
  items: string[];
  path: string[];
  onUpdate: (p: string[], v: YamlValue) => void;
}) {
  const [draft, setDraft] = useState("");

  const add = () => {
    const v = draft.trim();
    if (!v) return;
    onUpdate(path, [...items, v]);
    setDraft("");
  };

  return (
    <div className="space-y-2 py-0.5">
      <div className="flex items-center justify-between">
        <label className="text-sm font-medium text-gray-600">{toLabel(name)}</label>
        <span className="text-[10px] text-gray-400 font-mono">{items.length} items</span>
      </div>

      <div className="space-y-1 max-h-52 overflow-y-auto">
        {items.map((item, i) => (
          <div key={i} className="flex items-center gap-2 group">
            <span className="text-[10px] text-gray-300 w-5 text-right font-mono">{i + 1}</span>
            <input
              type="text"
              value={item}
              onChange={(e) => {
                const next = [...items];
                next[i] = e.target.value;
                onUpdate(path, next);
              }}
              className="input flex-1 font-mono text-xs py-1"
            />
            <button
              onClick={() => onUpdate(path, items.filter((_, j) => j !== i))}
              className="text-gray-300 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-opacity px-1 text-xs"
            >
              ✕
            </button>
          </div>
        ))}
      </div>

      <div className="flex items-center gap-2">
        <input
          type="text"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && add()}
          placeholder="Thêm mới…"
          className="input flex-1 font-mono text-xs py-1"
        />
        <button onClick={add} disabled={!draft.trim()} className="btn-primary py-1 text-xs px-3">
          +
        </button>
      </div>
    </div>
  );
}

/* ── Dict-of-Lists Field (per_service) ────────────── */

function DictOfListsField({
  name,
  data,
  path,
  onUpdate,
}: {
  name: string;
  data: Record<string, string[]>;
  path: string[];
  onUpdate: (p: string[], v: YamlValue) => void;
}) {
  const [newKey, setNewKey] = useState("");

  const addEntry = () => {
    const k = newKey.trim();
    if (!k || k in data) return;
    onUpdate(path, { ...data, [k]: [] });
    setNewKey("");
  };

  const removeEntry = (key: string) => {
    const next = { ...data };
    delete next[key];
    onUpdate(path, next);
  };

  return (
    <div className="space-y-2 py-0.5">
      <label className="text-sm font-medium text-gray-600">{toLabel(name)}</label>

      <div className="space-y-1.5">
        {Object.entries(data).map(([key, vals]) => (
          <div key={key} className="flex items-center gap-2 bg-gray-50 rounded-lg px-3 py-2">
            <span className="text-xs font-medium text-gray-700 w-28 shrink-0 font-mono">{key}</span>
            <div className="flex-1 flex flex-wrap gap-1.5">
              {(vals ?? []).map((v, i) => (
                <span key={i} className="badge bg-brand-50 text-brand-700 text-[11px] gap-1">
                  {v}
                  <button
                    onClick={() => onUpdate([...path, key], vals.filter((_, j) => j !== i))}
                    className="hover:text-red-500"
                  >
                    ×
                  </button>
                </span>
              ))}
              <InlineAdd onAdd={(v) => onUpdate([...path, key], [...(vals ?? []), v])} />
            </div>
            <button
              onClick={() => removeEntry(key)}
              className="text-gray-300 hover:text-red-500 text-xs px-0.5"
            >
              ✕
            </button>
          </div>
        ))}
      </div>

      <div className="flex items-center gap-2">
        <input
          type="text"
          value={newKey}
          onChange={(e) => setNewKey(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && addEntry()}
          placeholder="Service…"
          className="input font-mono text-xs py-1 w-36"
        />
        <button onClick={addEntry} disabled={!newKey.trim()} className="btn-secondary py-1 text-xs px-3">
          + Service
        </button>
      </div>
    </div>
  );
}

/* ── Inline Add (badge-style) ─────────────────────── */

function InlineAdd({ onAdd }: { onAdd: (v: string) => void }) {
  const [open, setOpen] = useState(false);
  const [val, setVal] = useState("");

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="badge bg-gray-100 text-gray-400 hover:text-gray-600 text-[11px] cursor-pointer"
      >
        +
      </button>
    );
  }

  return (
    <input
      autoFocus
      value={val}
      onChange={(e) => setVal(e.target.value)}
      onKeyDown={(e) => {
        if (e.key === "Enter" && val.trim()) {
          onAdd(val.trim());
          setVal("");
          setOpen(false);
        }
        if (e.key === "Escape") {
          setOpen(false);
          setVal("");
        }
      }}
      onBlur={() => {
        setOpen(false);
        setVal("");
      }}
      className="text-xs border border-brand-300 rounded px-1.5 py-0.5 w-24 focus:outline-none"
      placeholder="provider…"
    />
  );
}
