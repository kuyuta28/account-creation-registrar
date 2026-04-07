if (!import.meta.env.VITE_API_BASE_URL) throw new Error("VITE_API_BASE_URL không được cấu hình");
export const _API_ORIGIN = import.meta.env.VITE_API_BASE_URL;
const BASE = `${_API_ORIGIN}/api/v1`;

// ── Envelope ──────────────────────────────────────────────────────────────────
interface _ApiEnvelope<T> {
  success: boolean;
  data?: T;
  error?: { code: string; message: string };
  meta: { request_id: string; ts: string };
}

export interface Account {
  email: string;
  service: string;
  api_key?: string;
  password?: string;
  disabled: boolean;
  credits?: number;
  check_status?: string;
  quota_pct?: number | null;
  status?: "active" | "disabled" | "unchecked";
  last_checked?: string;
  last_error?: string;
  created_at?: string;
  updated_at?: string;
  session_state?: string;   // Playwright storage_state JSON
  totp_secret?: string;     // Base32 TOTP secret (GMAIL 2FA)
  app_password?: string;    // Gmail App Password cho IMAP
  source_email?: string;    // Base Gmail nếu email này là alias
}

// ── Gmail Variations ──────────────────────────────────────────────────────────
export interface GmailVariationResult {
  email: string;
  technique: "plus" | "dot" | "googlemail";
  tag: string | null;
  available: boolean;
}

export interface GmailVariationsResponse {
  base_email: string;
  service: string;
  total: number;
  available: number;
  variations: GmailVariationResult[];
}

export interface GmailVariationDefaults {
  use_plus: boolean;
  use_dot: boolean;
  use_googlemail: boolean;
  plus_tags: string;           // comma-separated, e.g. "1,2,3,4,5,6,7,8,9,10"
  dot_max_username_len: number;
}

// ── Gmail Mailboxes ───────────────────────────────────────────────────────────
export interface GmailMailbox {
  email: string;             // canonical @gmail.com
  app_password: string;      // Gmail App Password cho IMAP
  totp_secret: string;       // Base32 TOTP secret cho 2FA
  password: string;          // Google account password
  source_email: string;      // base Gmail nếu là alias
  google_auth_state: string; // Playwright storage_state JSON
  disabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface MailboxServiceBlock {
  email: string;
  service: string;
  reason: string;
  blocked_at: string;
}

export interface SmsPhone {
  phone: string;
  label: string;
  disabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface MailProvider {
  id: number;
  provider_type: string;
  api_key: string;
  server_id: string;
  connection_str: string;
  label: string;
  disabled: boolean;
  fail_count: number;
  tags: string[];
}

export interface MailProviderDomain {
  domain: string;
  tags: string[];
  total: number;
  active: number;
}

export interface Job {
  id: string;
  service: string;
  count: number;
  workers: number;
  status: "pending" | "running" | "done" | "failed" | "stopped";
  created_at: string;
  created_count: number;
  processed_count: number;
  error?: string;
}

export interface ImageLabJob {
  id: string;
  prompt: string;
  models: string[];
  aspect_ratio: string;
  dimensions: string;
  generations: number;
  workers: number;
  status: "pending" | "running" | "done" | "failed" | "cancelled";
  created_at: string;
  total_accounts: number;
  completed_accounts: number;
  image_paths: string[];
  error?: string;
}

// ── AA Proxy types ────────────────────────────────────────────────────────────

export interface AAModel {
  id: string;
  name: string;
  creator: string;
  creatorLogo: string;
  ttiElo: number | null;
  itiElo: number | null;
  ttiPricePerGeneration: number | null;
  itiPricePerGeneration: number | null;
  hasTtiEndpoint: boolean;
  hasItiEndpoint: boolean;
}

export interface AAImage {
  id: string;
  imageUrl: string;
  modelId: string;
  modelName: string;
  isLiked: boolean;
  status: "generated" | "pending" | "failed";
  errorMessage: string | null;
  generationIndex: number;
}

export interface AAGeneration {
  id: string;
  prompt: string;
  aspectRatio: string;
  createdAt: string;
  images: AAImage[];
}

export interface AAGenerationResult {
  generationId?: string;
  images?: AAImage[];
  [key: string]: unknown;
}

// ── Core fetch helpers ────────────────────────────────────────────────────────

const _parse = async <T>(r: Response): Promise<T> => {
  const body = (await r.json()) as _ApiEnvelope<T>;
  if (!body.success) {
    throw new Error(body.error?.message ?? `HTTP ${r.status}`);
  }
  return body.data as T;
};

const get = <T>(path: string) =>
  fetch(`${BASE}${path}`).then((r) => _parse<T>(r));

const post = <T>(path: string, body: unknown) =>
  fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }).then((r) => _parse<T>(r));

const put = <T>(path: string, body: unknown) =>
  fetch(`${BASE}${path}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }).then((r) => _parse<T>(r));

const patch = <T>(path: string, body: unknown) =>
  fetch(`${BASE}${path}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }).then((r) => _parse<T>(r));

const del = <T>(path: string) =>
  fetch(`${BASE}${path}`, { method: "DELETE" }).then((r) => _parse<T>(r));

const postBinary = (path: string, body: unknown): Promise<ArrayBuffer> =>
  fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }).then((r) => {
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r.arrayBuffer();
  });

// ── API surface ───────────────────────────────────────────────────────────────

export const api = {
  getAccounts: (service?: string) =>
    get<Account[]>(`/accounts${service ? `?service=${service}` : ""}`),

  deleteAccount: (service: string, email: string) =>
    del<{ deleted: boolean }>(
      `/accounts/${encodeURIComponent(service)}/${encodeURIComponent(email)}`
    ),

  addAccount: (
    service: string,
    email: string,
    api_key = "",
    password = "",
    totp_secret = "",
    app_password = "",
    source_email = "",
  ) =>
    post<{ created: boolean }>("/accounts/add", { service, email, api_key, password, totp_secret, app_password, source_email }),

  updateAccount: (service: string, email: string, data: Partial<Account>) =>
    patch<{ updated: boolean }>(
      `/accounts/${encodeURIComponent(service)}/${encodeURIComponent(email)}`,
      data
    ),

  getServices: () => get<string[]>("/accounts/services"),

  addService: (name: string, has_registrar = false) =>
    post<{ created: boolean; name: string }>("/accounts/services", { name, has_registrar }),

  deleteService: (name: string) =>
    del<{ deleted: boolean }>(`/accounts/services/${encodeURIComponent(name)}`),

  syncAuth: (target_dir?: string) =>
    post<{ synced: number; files: string[] }>("/accounts/sync-auth" + (target_dir ? `?target_dir=${encodeURIComponent(target_dir)}` : ""), {}),

  launchKlingSession: (gmail_hint?: string) =>
    post<{ launched: boolean; note: string }>("/accounts/kling-session", { gmail_hint }),

  startCheckAndCleanOR: () =>
    post<{ total: number }>("/accounts/check-and-clean-openrouter", {}),

  getCheckAndCleanORStatus: () =>
    get<{ running: boolean; total: number; checked: number; ok: number; deleted_db: number; deleted_cliproxy: number }>("/accounts/check-and-clean-openrouter/status"),

  startFixORPrivacy: () =>
    post<{ total: number }>("/accounts/fix-openrouter-privacy", {}),

  getFixORPrivacyStatus: () =>
    get<{ running: boolean; total: number; processed: number; ok: number; failed: number; skipped: number }>("/accounts/fix-openrouter-privacy/status"),

  refreshKlingSession: (email: string) =>
    post<{ email: string; sliding: boolean; diff_days: Record<string, number>; saved: boolean }>("/accounts/refresh-kling-session", { email }),

  startJob: (service: string, count: number, workers = 1) =>
    post<Job>("/registration/jobs", { service, count, workers }),

  getJobs: () => get<Job[]>("/registration/jobs"),

  getJob: (id: string) => get<Job>(`/registration/jobs/${id}`),

  cancelJob: (id: string) =>
    post<{ cancelled: boolean }>(`/registration/jobs/${id}/cancel`, {}),

  getConfigRaw: (file = "config.yaml") =>
    get<{ content: string; file: string }>(`/config/raw?file=${encodeURIComponent(file)}`),

  saveConfigRaw: (content: string, file = "config.yaml") =>
    put<{ saved: boolean }>(`/config/raw?file=${encodeURIComponent(file)}`, { content }),

  listConfigFiles: () => get<{ files: string[] }>("/config/files"),

  addMailSlurpKey: (key: string) =>
    post<{ total: number }>("/config/mail/add-key", { key }),

  checkAccount: (service: string, email: string) =>
    post<{ valid: boolean; check_status: string; quota_pct: string; last_checked: string; last_error: string; name?: string; token_refreshed?: boolean }>(
      `/accounts/check?service=${encodeURIComponent(service)}&email=${encodeURIComponent(email)}`,
      {}
    ),

  startBatchCheck: (service?: string) =>
    post<{ total: number }>(`/accounts/check-all${service && service !== "ALL" ? `?service=${encodeURIComponent(service)}` : ""}`, {}),

  getBatchCheckStatus: () =>
    get<{ running: boolean; total: number; checked: number; valid: number; invalid: number; errors: number }>(
      "/accounts/check-all/status"
    ),

  startORPrivacyCheck: () =>
    post<{ total: number }>("/accounts/check-openrouter-privacy", {}),

  getORPrivacyCheckStatus: () =>
    get<{ running: boolean; total: number; checked: number; ok: number; privacy_blocked: number; skipped: number }>(
      "/accounts/check-openrouter-privacy/status"
    ),

  deleteDisabledAccounts: (service?: string) =>
    del<{ deleted: number }>(
      `/accounts/bulk-delete-disabled${service ? `?service=${encodeURIComponent(service)}` : ""}`
    ),

  cycleProviderTag: (providerDomain: string, service: string) =>
    post<{ tags: string[] }>(`/providers/${encodeURIComponent(providerDomain)}/tag/${encodeURIComponent(service)}/cycle`, {}),

  syncCliProxy: () =>
    post<{ deleted: number; files: string[]; bad_count: number }>("/accounts/sync-cliproxy", {}),

  syncOpenRouterToCliproxy: () =>
    post<{ added: number; total: number; keys_added: string[] }>("/accounts/sync-openrouter-cliproxy", {}),

  getKeyDetail: (service: string, apiKey: string) =>
    post<{
      valid: boolean;
      label?: string;
      is_free_tier?: boolean;
      limit?: number | null;
      limit_remaining?: number | null;
      limit_reset?: string | null;
      usage?: number;
      usage_daily?: number;
      usage_weekly?: number;
      usage_monthly?: number;
      byok_usage?: number;
      byok_usage_daily?: number;
      byok_usage_weekly?: number;
      byok_usage_monthly?: number;
    }>(
      `/accounts/key-detail?service=${encodeURIComponent(service)}&api_key=${encodeURIComponent(apiKey)}`,
      {}
    ),

  // ── Mailbox ──────────────────────────────────────────────────────────
  createMailbox: (provider?: string) =>
    post<{ email: string; provider: string; created_at: number }>("/mailbox", { provider: provider ?? null }),

  listMailboxes: () =>
    get<{ email: string; provider: string; created_at: number }[]>("/mailbox"),

  deleteMailbox: (email: string) =>
    del<{ deleted: boolean }>(`/mailbox/${encodeURIComponent(email)}`),

  getMessages: (email: string) =>
    get<{ id: string; from: string; subject: string; has_body: boolean }[]>(
      `/mailbox/${encodeURIComponent(email)}/messages`
    ),

  getMessageDetail: (email: string, messageId: string) =>
    get<{ id: string; body: string; text: string; is_html: boolean; links: string[]; otp: string | null }>(
      `/mailbox/${encodeURIComponent(email)}/messages/${encodeURIComponent(messageId)}`
    ),

  // ── Mail Providers ──────────────────────────────────────────────────
  getProviders: () =>
    get<MailProviderDomain[]>("/providers"),

  getAllProviders: () =>
    get<MailProvider[]>("/providers/all"),

  updateProvider: (id: number, data: { disabled?: boolean; label?: string }) =>
    patch<{ updated: boolean }>(`/providers/${id}`, data),

  setProviderTags: (providerDomain: string, tags: string[]) =>
    put<{ updated: number }>(`/providers/${encodeURIComponent(providerDomain)}/tags`, { tags }),

  // ── Image Lab ───────────────────────────────────────────────────────
  startImageLabJob: (params: {
    prompt: string;
    models: string[];
    aspect_ratio?: string;
    dimensions?: string;
    generations?: number;
    workers?: number;
  }) => post<ImageLabJob>("/image-lab/jobs", params),

  getImageLabJobs: () => get<ImageLabJob[]>("/image-lab/jobs"),

  getImageLabJob: (id: string) => get<ImageLabJob>(`/image-lab/jobs/${id}`),

  cancelImageLabJob: (id: string) =>
    post<{ cancelled: boolean }>(`/image-lab/jobs/${id}/cancel`, {}),

  openBrowserSession: (service: string, email: string, url?: string) =>
    post<{ launched: boolean }>("/accounts/open-browser", { service, email, url }),

  // ── AA Proxy ────────────────────────────────────────────────────────
  aaGetSession: (email: string) =>
    get<{ email: string; session: Record<string, unknown>; user: Record<string, unknown>; org: { name: string; balance: string; id: string } }>(
      `/aa/session?email=${encodeURIComponent(email)}`
    ),

  aaGetModels: (mode: "text_to_image" | "image_editing" | "all" = "text_to_image") =>
    get<AAModel[]>(`/aa/models?mode=${mode}`),

  aaGetGenerations: (email: string, limit = 20, cursor?: string) =>
    get<{ generations: AAGeneration[]; nextCursor: string | null; hasMore: boolean }>(
      `/aa/generations?email=${encodeURIComponent(email)}&limit=${limit}${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ""}`
    ),

  aaGenerate: (params: {
    email: string;
    prompt: string;
    model_ids: string[];
    generations_per_model?: number;
    width?: number;
    height?: number;
  }) => post<AAGenerationResult>("/aa/generate", params),

  aaGetGeneration: (genId: string, email: string) =>
    get<AAGenerationResult>(`/aa/generation/${genId}?email=${encodeURIComponent(email)}`),

  aaImageDownload: (email: string, imageId: string, filenameHint: string) =>
    postBinary("/aa/image-download", { email, image_id: imageId, filename_hint: filenameHint }),

  // ── Gmail Variations ────────────────────────────────────────────────
  getGmailVariationDefaults: () => get<GmailVariationDefaults>("/gmail/variations/defaults"),

  getGmailVariations: (params: {
    base_email: string;
    service: string;
    use_plus?: boolean;
    use_dot?: boolean;
    use_googlemail?: boolean;
    plus_tags?: string[];
  }) => post<GmailVariationsResponse>("/gmail/variations", params),

  getGmailUsed: (base_email: string, service?: string) =>
    get<{ base_email: string; service: string | null; count: number; accounts: Account[] }>(
      `/gmail/used?base_email=${encodeURIComponent(base_email)}${service ? `&service=${encodeURIComponent(service)}` : ""}`
    ),

  // ── Gmail Mailboxes ──────────────────────────────────────────────────
  getGmailMailboxes: () => get<GmailMailbox[]>("/gmail/mailboxes"),

  upsertGmailMailbox: (data: Omit<GmailMailbox, "created_at" | "updated_at" | "google_auth_state">) =>
    post<GmailMailbox>("/gmail/mailboxes", data),

  deleteGmailMailbox: (email: string) =>
    del<{ deleted: boolean }>(`/gmail/mailboxes/${encodeURIComponent(email)}`),

  getGmailMailbox: (email: string) =>
    get<GmailMailbox>(`/gmail/mailboxes/${encodeURIComponent(email)}`),

  openMailboxBrowser: (email: string) =>
    post<{ launched: boolean }>(`/gmail/mailboxes/${encodeURIComponent(email)}/open-browser`, {}),

  getMailboxTotp: (email: string) =>
    get<{ code: string; remaining: number; interval: number }>(`/gmail/mailboxes/${encodeURIComponent(email)}/totp`),

  refreshMailboxSession: (email: string) =>
    post<{ email: string; ok: boolean }>(`/gmail/mailboxes/${encodeURIComponent(email)}/refresh-session`, {}),

  refreshAllMailboxSessions: () =>
    post<{ results: Array<{ email: string; ok: boolean; error?: string }>; ok: number; fail: number; total: number }>(
      "/gmail/mailboxes/refresh-all-sessions", {}
    ),

  // ── Mailbox Service Blocks ───────────────────────────────────────────
  getMailboxBlocks: (service?: string) =>
    get<MailboxServiceBlock[]>(`/gmail/mailboxes/blocks${service ? `?service=${encodeURIComponent(service)}` : ""}`),

  addMailboxBlock: (email: string, service: string, reason = "") =>
    post<{ email: string; service: string; blocked: boolean }>(
      `/gmail/mailboxes/${encodeURIComponent(email)}/blocks`,
      { service, reason }
    ),

  removeMailboxBlock: (email: string, service: string) =>
    del<{ email: string; service: string; blocked: boolean }>(
      `/gmail/mailboxes/${encodeURIComponent(email)}/blocks/${encodeURIComponent(service)}`
    ),

  // ── SMS Phones ─────────────────────────────────────────────────────
  getSmsPhones: () => get<SmsPhone[]>("/sms/phones"),

  upsertSmsPhone: (data: { phone: string; label?: string; disabled?: boolean }) =>
    post<SmsPhone>("/sms/phones", data),

  patchSmsPhone: (phone: string, data: { label?: string; disabled?: boolean }) =>
    patch<SmsPhone>(`/sms/phones/${encodeURIComponent(phone)}`, data),

  deleteSmsPhone: (phone: string) =>
    del<{ deleted: boolean }>(`/sms/phones/${encodeURIComponent(phone)}`),

  getSmsMessages: (phone: string) =>
    get<{ phone: string; count: number; messages: Array<{ id: string; from_: string; subject: string; text: string; sent_stamp: number; unread: boolean }> }>(
      `/sms/messages/${encodeURIComponent(phone)}`
    ),
};

// ── WebSocket helpers ─────────────────────────────────────────────────────────

const _WS_BASE = _API_ORIGIN.replace(/^http/, "ws");

export const wsLogs = (jobId: string): WebSocket =>
  new WebSocket(`${_WS_BASE}/api/v1/registration/jobs/${jobId}/logs`);

export const wsImageLabLogs = (jobId: string): WebSocket =>
  new WebSocket(`${_WS_BASE}/api/v1/image-lab/jobs/${jobId}/logs`);

