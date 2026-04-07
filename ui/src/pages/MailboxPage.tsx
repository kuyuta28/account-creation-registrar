import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api/client";

// ── Types ─────────────────────────────────────────────────────────────
interface ActiveMailbox {
  email: string;
  provider: string;
  created_at: number;
}

interface Message {
  id: string;
  from: string;
  subject: string;
  has_body: boolean;
}

interface MessageDetail {
  id: string;
  body: string;
  text: string;
  is_html: boolean;
  links: string[];
  otp: string | null;
}

// ── Helpers ───────────────────────────────────────────────────────────
const timeAgo = (ts: number) => {
  const sec = Math.floor(Date.now() / 1000 - ts);
  if (sec < 60) return `${sec}s ago`;
  if (sec < 3600) return `${Math.floor(sec / 60)}m ago`;
  return `${Math.floor(sec / 3600)}h ago`;
};

const copyText = async (text: string) => {
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    /* noop */
  }
};

const truncateUrl = (url: string, max = 55) => {
  try {
    const u = new URL(url);
    const display = u.hostname + u.pathname.slice(0, 40);
    return display.length > max ? display.slice(0, max) + "…" : display;
  } catch {
    return url.length > max ? url.slice(0, max) + "…" : url;
  }
};

// ── Component ─────────────────────────────────────────────────────────
export default function MailboxPage() {
  const [boxes, setBoxes] = useState<ActiveMailbox[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [detail, setDetail] = useState<MessageDetail | null>(null);
  const [creating, setCreating] = useState(false);
  const [provider, setProvider] = useState("mail.tm");
  const [polling, setPolling] = useState(false);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState("");
  const [viewMode, setViewMode] = useState<"rendered" | "text" | "source">(
    "rendered"
  );
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const iframeRef = useRef<HTMLIFrameElement>(null);

  // Load mailboxes on mount
  const loadBoxes = useCallback(async () => {
    try {
      const list = await api.listMailboxes();
      setBoxes(list);
    } catch (e: any) {
      setError(e.message);
    }
  }, []);

  useEffect(() => {
    loadBoxes();
  }, [loadBoxes]);

  // Auto-poll messages when a mailbox is selected
  useEffect(() => {
    if (!selected) {
      setMessages([]);
      setDetail(null);
      return;
    }
    let cancelled = false;

    const poll = async () => {
      if (cancelled) return;
      setPolling(true);
      try {
        const msgs = await api.getMessages(selected);
        if (!cancelled) setMessages(msgs);
      } catch {
        /* mailbox might have been removed */
      }
      if (!cancelled) setPolling(false);
    };

    poll();
    const id = setInterval(poll, 5000);
    pollRef.current = id;
    return () => {
      cancelled = true;
      clearInterval(id);
      pollRef.current = null;
    };
  }, [selected]);

  // Write HTML into iframe document (srcDoc doesn't work in Tauri webview)
  useEffect(() => {
    if (!detail?.is_html || viewMode !== "rendered") return;
    const iframe = iframeRef.current;
    if (!iframe) return;

    // Small delay to ensure iframe is mounted
    const timer = setTimeout(() => {
      try {
        const doc = iframe.contentDocument;
        if (!doc) return;
        doc.open();
        // Inject base styles to constrain email content
        doc.write(`
          <style>
            body { margin: 0; padding: 16px; font-family: -apple-system, system-ui, sans-serif; font-size: 14px; overflow-x: hidden; }
            img { max-width: 100%; height: auto; }
            a { color: #2563eb; }
          </style>
          ${detail.body}
        `);
        doc.close();
        // Auto-resize
        requestAnimationFrame(() => {
          try {
            const h = doc.body?.scrollHeight || 300;
            iframe.style.height = Math.min(h + 20, 600) + "px";
          } catch { /* noop */ }
        });
      } catch { /* noop */ }
    }, 50);

    return () => clearTimeout(timer);
  }, [detail, viewMode]);

  // ── Handlers ────────────────────────────────────────────────────────
  const handleCreate = async () => {
    setCreating(true);
    setError("");
    try {
      const box = await api.createMailbox(provider);
      setBoxes((prev) => [box, ...prev]);
      setSelected(box.email);
    } catch (e: any) {
      setError(e.message);
    }
    setCreating(false);
  };

  const handleDelete = async (email: string) => {
    try {
      await api.deleteMailbox(email);
      setBoxes((prev) => prev.filter((b) => b.email !== email));
      if (selected === email) setSelected(null);
    } catch (e: any) {
      setError(e.message);
    }
  };

  const handleViewDetail = async (msg: Message) => {
    if (!selected) return;
    try {
      const d = await api.getMessageDetail(selected, msg.id);
      setDetail(d);
      setViewMode(d.is_html ? "rendered" : "text");
    } catch (e: any) {
      setError(e.message);
    }
  };

  const handleCopy = async (text: string, label: string) => {
    await copyText(text);
    setCopied(label);
    setTimeout(() => setCopied(""), 2000);
  };

  // ── Render ──────────────────────────────────────────────────────────
  return (
    <div className="space-y-4">
      {/* Header row: title + create */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">Mailbox</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Temp email — nhận OTP, magic link, verification
          </p>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={provider}
            onChange={(e) => setProvider(e.target.value)}
            className="rounded-lg border border-gray-300 px-3 py-2 text-sm focus:ring-2 focus:ring-brand-500 focus:border-brand-500"
          >
            <option value="mail.tm">mail.tm</option>
            <option value="mailslurp">MailSlurp</option>
            <option value="testmail.app">testmail.app</option>
            <option value="mailosaur">Mailosaur</option>
            <option value="guerrillamail">Guerrilla Mail</option>
          </select>
          <button
            onClick={handleCreate}
            disabled={creating}
            className="btn-primary"
          >
            {creating ? "Creating…" : "+ New Mailbox"}
          </button>
        </div>
      </div>

      {error && (
        <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700 flex items-center justify-between">
          <span>{error}</span>
          <button
            className="text-red-400 hover:text-red-600 text-xs ml-4"
            onClick={() => setError("")}
          >
            ✕
          </button>
        </div>
      )}

      {/* Main 2-column layout */}
      <div className="grid grid-cols-12 gap-4" style={{ minHeight: 500 }}>
        {/* Left: mailbox list */}
        <div className="col-span-3 card p-0 overflow-hidden flex flex-col">
          <div className="px-4 py-3 border-b border-gray-100 bg-gray-50/50">
            <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
              Mailboxes
              <span className="ml-1 text-gray-400 font-normal lowercase">
                ({boxes.length})
              </span>
            </h2>
          </div>
          <div className="flex-1 overflow-y-auto divide-y divide-gray-100">
            {boxes.length === 0 && (
              <p className="px-4 py-12 text-sm text-gray-400 text-center">
                No mailboxes yet
              </p>
            )}
            {boxes.map((box) => (
              <div
                key={box.email}
                onClick={() => setSelected(box.email)}
                className={`px-3 py-2.5 cursor-pointer transition-colors group ${
                  selected === box.email
                    ? "bg-brand-50 border-l-2 border-brand-500"
                    : "hover:bg-gray-50 border-l-2 border-transparent"
                }`}
              >
                <div className="flex items-start justify-between gap-1">
                  <div className="min-w-0 flex-1">
                    <p
                      className="text-[13px] font-medium text-gray-900 truncate cursor-pointer hover:text-brand-600"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleCopy(box.email, box.email);
                      }}
                      title={box.email}
                    >
                      {box.email}
                    </p>
                    <div className="flex items-center gap-1.5 mt-0.5">
                      <span
                        className={`inline-block w-1.5 h-1.5 rounded-full ${
                          box.provider === "mailslurp"
                            ? "bg-violet-400"
                            : "bg-emerald-400"
                        }`}
                      />
                      <span className="text-[11px] text-gray-400">
                        {box.provider} · {timeAgo(box.created_at)}
                      </span>
                    </div>
                  </div>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDelete(box.email);
                    }}
                    className="opacity-0 group-hover:opacity-100 p-1 text-gray-400 hover:text-red-500 text-xs transition-all"
                    title="Remove"
                  >
                    ✕
                  </button>
                </div>
                {copied === box.email && (
                  <span className="text-[10px] text-emerald-500 font-medium">
                    Copied!
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Right: inbox + detail */}
        <div className="col-span-9 flex flex-col gap-4">
          {!selected ? (
            <div className="card flex-1 flex items-center justify-center">
              <div className="text-center">
                <span className="text-3xl">📭</span>
                <p className="text-gray-400 text-sm mt-2">
                  Chọn mailbox bên trái để xem inbox
                </p>
              </div>
            </div>
          ) : (
            <>
              {/* Inbox header */}
              <div className="card p-0 overflow-hidden">
                <div className="px-4 py-2.5 border-b border-gray-100 bg-gray-50/50 flex items-center justify-between">
                  <div className="flex items-center gap-2 min-w-0">
                    <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wider shrink-0">
                      Inbox
                    </h2>
                    <span className="text-[13px] text-gray-600 truncate font-mono">
                      {selected}
                    </span>
                    <button
                      onClick={() => handleCopy(selected, "hdr-email")}
                      className="shrink-0 text-gray-400 hover:text-brand-600 transition-colors"
                      title="Copy email"
                    >
                      <svg
                        className="w-3.5 h-3.5"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"
                        />
                      </svg>
                    </button>
                    {copied === "hdr-email" && (
                      <span className="text-[10px] text-emerald-500">
                        Copied!
                      </span>
                    )}
                  </div>
                  {polling && (
                    <span className="flex items-center gap-1 text-[11px] text-gray-400">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                      polling
                    </span>
                  )}
                </div>
                <div className="max-h-[200px] overflow-y-auto divide-y divide-gray-100">
                  {messages.length === 0 && (
                    <div className="px-4 py-10 text-center">
                      <p className="text-sm text-gray-400">
                        Chưa có email — auto-poll mỗi 5s
                      </p>
                    </div>
                  )}
                  {messages.map((msg) => (
                    <div
                      key={msg.id}
                      onClick={() => handleViewDetail(msg)}
                      className={`px-4 py-2.5 cursor-pointer hover:bg-gray-50 transition-colors flex items-center gap-3 ${
                        detail?.id === msg.id ? "bg-brand-50" : ""
                      }`}
                    >
                      <div className="w-8 h-8 rounded-full bg-gray-100 flex items-center justify-center shrink-0">
                        <span className="text-sm">✉</span>
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-medium text-gray-900 truncate">
                          {msg.subject || "(no subject)"}
                        </p>
                        <p className="text-xs text-gray-500 truncate">
                          {msg.from}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Detail */}
              {detail && (
                <div className="card p-0 overflow-hidden flex-1 flex flex-col">
                  {/* Detail header + extracted data */}
                  <div className="px-4 py-3 border-b border-gray-100 bg-gray-50/50 space-y-2">
                    <div className="flex items-center justify-between">
                      <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
                        Message Detail
                      </h3>
                      <button
                        onClick={() => setDetail(null)}
                        className="text-xs text-gray-400 hover:text-gray-600"
                      >
                        ✕ Close
                      </button>
                    </div>

                    {/* Extracted OTP + Links */}
                    {(detail.otp || detail.links.length > 0) && (
                      <div className="flex items-center gap-3 flex-wrap">
                        {detail.otp && (
                          <button
                            onClick={() => handleCopy(detail.otp!, "otp")}
                            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-amber-50 border border-amber-200 hover:bg-amber-100 transition-colors"
                          >
                            <span className="text-amber-500 text-sm">🔑</span>
                            <span className="font-mono text-lg font-bold text-amber-800 tracking-widest">
                              {detail.otp}
                            </span>
                            <span className="text-[10px] text-amber-500 ml-1">
                              {copied === "otp" ? "✓ copied" : "click to copy"}
                            </span>
                          </button>
                        )}
                        {detail.links.length > 0 && (
                          <div className="flex items-center gap-1.5 flex-wrap">
                            {detail.links.map((link, i) => (
                              <button
                                key={i}
                                onClick={() => handleCopy(link, `link-${i}`)}
                                className={`inline-flex items-center gap-1 px-2 py-1 rounded-md text-[11px] transition-colors ${
                                  copied === `link-${i}`
                                    ? "bg-emerald-50 border border-emerald-200 text-emerald-700"
                                    : "bg-gray-100 border border-gray-200 text-gray-600 hover:bg-blue-50 hover:border-blue-200 hover:text-blue-700"
                                }`}
                                title={link}
                              >
                                <svg
                                  className="w-3 h-3 shrink-0"
                                  fill="none"
                                  stroke="currentColor"
                                  viewBox="0 0 24 24"
                                >
                                  <path
                                    strokeLinecap="round"
                                    strokeLinejoin="round"
                                    strokeWidth={2}
                                    d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1"
                                  />
                                </svg>
                                <span className="truncate max-w-[200px]">
                                  {copied === `link-${i}`
                                    ? "✓ copied"
                                    : truncateUrl(link)}
                                </span>
                              </button>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </div>

                  {/* View mode tabs */}
                  <div className="px-4 py-1.5 border-b border-gray-100 flex gap-1">
                    {(
                      [
                        ["rendered", "Preview"],
                        ["text", "Text"],
                        ["source", "Source"],
                      ] as const
                    ).map(([mode, label]) => (
                      <button
                        key={mode}
                        onClick={() => setViewMode(mode)}
                        className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
                          viewMode === mode
                            ? "bg-brand-100 text-brand-700"
                            : "text-gray-500 hover:text-gray-700 hover:bg-gray-100"
                        }`}
                      >
                        {label}
                      </button>
                    ))}
                  </div>

                  {/* Content */}
                  <div className="flex-1 overflow-auto">
                    {viewMode === "rendered" && detail.is_html ? (
                      <iframe
                        ref={iframeRef}
                        sandbox="allow-same-origin"
                        className="w-full border-0"
                        style={{ minHeight: 250, maxHeight: 600 }}
                        title="Email preview"
                      />
                    ) : viewMode === "text" || !detail.is_html ? (
                      <div className="p-4">
                        <pre className="text-sm text-gray-700 whitespace-pre-wrap break-words font-sans leading-relaxed">
                          {detail.text || detail.body || "(empty)"}
                        </pre>
                      </div>
                    ) : (
                      <div className="bg-gray-950 p-4">
                        <pre className="text-xs text-gray-300 whitespace-pre-wrap break-words font-mono leading-5">
                          {detail.body || "(empty)"}
                        </pre>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
