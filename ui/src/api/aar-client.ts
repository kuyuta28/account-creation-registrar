/**
 * aar-client.ts — API client cho any-auto-register (AAR) service
 * Base URL: VITE_AAR_BASE_URL (port 8080)
 */
if (!import.meta.env.VITE_AAR_BASE_URL) throw new Error("VITE_AAR_BASE_URL không được cấu hình");
export const AAR_ORIGIN = import.meta.env.VITE_AAR_BASE_URL;
const BASE = `${AAR_ORIGIN}/api`;

// ── HTTP Helpers ──────────────────────────────────────────────────────────────

async function _req<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers: body !== undefined ? { "Content-Type": "application/json" } : {},
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    let msg = `HTTP ${res.status}`;
    try { const d = await res.json(); msg = d.detail || d.message || msg; } catch (_) {}
    throw new Error(msg);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

const aarGet  = <T>(path: string)                    => _req<T>("GET",    path);
const aarPost = <T>(path: string, body?: unknown)    => _req<T>("POST",   path, body ?? {});
const aarPut  = <T>(path: string, body: unknown)     => _req<T>("PUT",    path, body);
// const aarPatch= <T>(path: string, body: unknown)     => _req<T>("PATCH",  path, body);
const aarDel  = <T>(path: string)                    => _req<T>("DELETE", path);

// ── Types ─────────────────────────────────────────────────────────────────────

export interface AarPlatform {
  name: string;
  label?: string;
}

export interface AarAccount {
  id: number;
  platform: string;
  email: string;
  password: string;
  status: string;       // registered | active | disabled | banned | ...
  token: string;
  cashier_url?: string;
  user_id?: string;
  created_at?: string;
  updated_at?: string;
  extra?: Record<string, unknown>;
}

export interface AarAccountsResponse {
  total: number;
  page: number;
  items: AarAccount[];
}

export interface AarAccountStats {
  total: number;
  by_platform: Record<string, number>;
  by_status: Record<string, number>;
}

export interface AarTask {
  task_id: string;
  platform: string;
  status: "pending" | "running" | "done" | "failed" | "stopped";
  total: number;
  success: number;
  skipped: number;
  errors: string[];
  progress?: string;
  cashier_urls?: string[];
  source?: string;
  meta?: Record<string, unknown>;
}

export interface AarTaskLog {
  id: number;
  platform: string;
  email: string;
  status: string;   // success | failed | skipped
  error?: string;
  created_at?: string;
}

export interface AarTaskLogsResponse {
  total: number;
  items: AarTaskLog[];
}

export interface AarRegisterRequest {
  platform: string;
  count: number;
  concurrency: number;
  proxy?: string;
  executor_type?: string;
  captcha_solver?: string;
  register_delay_seconds?: number;
  extra?: Record<string, string>;
}

export interface AarConfig {
  [key: string]: string;
}

// ── Platforms ─────────────────────────────────────────────────────────────────

const getPlatforms = () => aarGet<AarPlatform[]>("/platforms");

// ── Accounts ──────────────────────────────────────────────────────────────────

const getAccounts = (params?: { platform?: string; status?: string; email?: string; page?: number; page_size?: number }) => {
  const q = new URLSearchParams();
  if (params?.platform)  q.set("platform",  params.platform);
  if (params?.status)    q.set("status",    params.status);
  if (params?.email)     q.set("email",     params.email);
  if (params?.page)      q.set("page",      String(params.page));
  if (params?.page_size) q.set("page_size", String(params.page_size));
  const qs = q.toString();
  return aarGet<AarAccountsResponse>(`/accounts${qs ? "?" + qs : ""}`);
};

const getAccountStats = () => aarGet<AarAccountStats>("/accounts/stats");

const deleteAccount = (id: number) => aarDel<{ ok: boolean }>(`/accounts/${id}`);

const batchDeleteAccounts = (ids: number[]) =>
  aarPost<{ deleted: number }>("/accounts/batch-delete", { ids });

const exportAccounts = (platform?: string) => {
  const q = new URLSearchParams();
  if (platform) q.set("platform", platform);
  return `${BASE}/accounts/export${q.toString() ? "?" + q.toString() : ""}`;
};

// ── Tasks ─────────────────────────────────────────────────────────────────────

const createTask = (req: AarRegisterRequest) =>
  aarPost<{ task_id: string }>("/tasks/register", req);

const listTasks = () => aarGet<AarTask[]>("/tasks");

const getTask = (taskId: string) => aarGet<AarTask>(`/tasks/${taskId}`);

const stopTask = (taskId: string) => aarPost<{ ok: boolean }>(`/tasks/${taskId}/stop`);

const skipCurrent = (taskId: string) => aarPost<{ ok: boolean }>(`/tasks/${taskId}/skip-current`);

const getTaskLogs = (params?: { platform?: string; page?: number; page_size?: number }) => {
  const q = new URLSearchParams();
  if (params?.platform)  q.set("platform",  params.platform);
  if (params?.page)      q.set("page",      String(params.page));
  if (params?.page_size) q.set("page_size", String(params.page_size));
  const qs = q.toString();
  return aarGet<AarTaskLogsResponse>(`/tasks/logs${qs ? "?" + qs : ""}`);
};

const batchDeleteTaskLogs = (ids: number[]) =>
  aarPost<{ deleted: number }>("/tasks/logs/batch-delete", { ids });

/** SSE stream: returns EventSource */
const sseTaskLogs = (taskId: string, since = 0): EventSource =>
  new EventSource(`${BASE}/tasks/${taskId}/logs/stream?since=${since}`);

// ── Config ────────────────────────────────────────────────────────────────────

const getConfig = () => aarGet<AarConfig>("/config");

const saveConfig = (data: Record<string, string>) =>
  aarPut<{ updated: string[] }>("/config", { data });

const importAppleMail = (file: File) => {
  const fd = new FormData();
  fd.append("file", file);
  return fetch(`${BASE}/config/applemail/import`, { method: "POST", body: fd }).then((r) => {
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r.json();
  });
};

const getAppleMailPool = () => aarGet<{ count: number; emails: string[] }>("/config/applemail/pool");

// ── Export ────────────────────────────────────────────────────────────────────

export const aarApi = {
  // Platforms
  getPlatforms,
  // Accounts
  getAccounts,
  getAccountStats,
  deleteAccount,
  batchDeleteAccounts,
  exportAccounts,
  // Tasks
  createTask,
  listTasks,
  getTask,
  stopTask,
  skipCurrent,
  getTaskLogs,
  batchDeleteTaskLogs,
  sseTaskLogs,
  // Config
  getConfig,
  saveConfig,
  importAppleMail,
  getAppleMailPool,
};

// ── Config key categories ─────────────────────────────────────────────────────
// Dùng để render ConfigPage theo nhóm

export const AAR_CONFIG_SECTIONS: { label: string; keys: { key: string; label: string; secret?: boolean; textarea?: boolean; hint?: string }[] }[] = [
  {
    label: "Mail chung",
    keys: [
      { key: "mail_provider", label: "Mail Provider mặc định", hint: "luckmail, duckmail, freemail, moemail, skymail, cloudmail, maliapi, applemail, gptmail, opentrashmail, cfworker" },
      { key: "mailbox_otp_timeout_seconds", label: "OTP timeout (giây)" },
    ],
  },
  {
    label: "Captcha",
    keys: [
      { key: "yescaptcha_key", label: "YesCaptcha API Key", secret: true },
      { key: "twocaptcha_key", label: "2Captcha API Key", secret: true },
      { key: "default_captcha_solver", label: "Captcha Solver mặc định", hint: "yescaptcha, twocaptcha, local_solver" },
      { key: "default_executor", label: "Executor mặc định", hint: "protocol, browser" },
    ],
  },
  {
    label: "SMS (SMSToMe)",
    keys: [
      { key: "smstome_cookie", label: "SMSToMe Cookie", secret: true, textarea: true, hint: "cf_clearance=...; smstome_session=..." },
      { key: "smstome_country_slugs", label: "Country slugs", hint: "Cách nhau dấu phẩy: us,sg,vn" },
      { key: "smstome_phone_attempts", label: "Số lần thử phone" },
      { key: "smstome_otp_timeout_seconds", label: "OTP timeout (giây)" },
      { key: "smstome_poll_interval_seconds", label: "Poll interval (giây)" },
      { key: "smstome_sync_max_pages_per_country", label: "Max pages/country" },
    ],
  },
  {
    label: "LuckMail",
    keys: [
      { key: "luckmail_base_url", label: "Base URL" },
      { key: "luckmail_api_key", label: "API Key", secret: true },
      { key: "luckmail_email_type", label: "Email type" },
      { key: "luckmail_domain", label: "Domain" },
    ],
  },
  {
    label: "DuckMail",
    keys: [
      { key: "duckmail_api_url", label: "API URL" },
      { key: "duckmail_provider_url", label: "Provider URL" },
      { key: "duckmail_bearer", label: "Bearer Token", secret: true },
      { key: "duckmail_domain", label: "Domain" },
      { key: "duckmail_api_key", label: "API Key", secret: true },
    ],
  },
  {
    label: "FreeMail",
    keys: [
      { key: "freemail_api_url", label: "API URL" },
      { key: "freemail_admin_token", label: "Admin Token", secret: true },
      { key: "freemail_username", label: "Username" },
      { key: "freemail_password", label: "Password", secret: true },
      { key: "freemail_domain", label: "Domain" },
    ],
  },
  {
    label: "MoeEmail",
    keys: [
      { key: "moemail_api_url", label: "API URL" },
      { key: "moemail_api_key", label: "API Key", secret: true },
    ],
  },
  {
    label: "SkyMail",
    keys: [
      { key: "skymail_api_base", label: "API Base URL" },
      { key: "skymail_token", label: "Token", secret: true },
      { key: "skymail_domain", label: "Domain" },
    ],
  },
  {
    label: "CloudMail",
    keys: [
      { key: "cloudmail_api_base", label: "API Base URL" },
      { key: "cloudmail_admin_email", label: "Admin Email" },
      { key: "cloudmail_admin_password", label: "Admin Password", secret: true },
      { key: "cloudmail_domain", label: "Domain" },
      { key: "cloudmail_subdomain", label: "Subdomain" },
      { key: "cloudmail_timeout", label: "Timeout" },
    ],
  },
  {
    label: "MaliAPI",
    keys: [
      { key: "maliapi_base_url", label: "Base URL" },
      { key: "maliapi_api_key", label: "API Key", secret: true },
      { key: "maliapi_domain", label: "Domain" },
      { key: "maliapi_auto_domain_strategy", label: "Auto domain strategy" },
    ],
  },
  {
    label: "GPTMail",
    keys: [
      { key: "gptmail_base_url", label: "Base URL" },
      { key: "gptmail_api_key", label: "API Key", secret: true },
      { key: "gptmail_domain", label: "Domain" },
    ],
  },
  {
    label: "OpenTrashMail",
    keys: [
      { key: "opentrashmail_api_url", label: "API URL" },
      { key: "opentrashmail_domain", label: "Domain" },
      { key: "opentrashmail_password", label: "Password", secret: true },
    ],
  },
  {
    label: "CFWorker Mail",
    keys: [
      { key: "cfworker_api_url", label: "API URL" },
      { key: "cfworker_admin_token", label: "Admin Token", secret: true },
      { key: "cfworker_custom_auth", label: "Custom Auth", secret: true },
      { key: "cfworker_domain", label: "Domain" },
      { key: "cfworker_domains", label: "Domains list (JSON)" },
      { key: "cfworker_enabled_domains", label: "Enabled domains (JSON)" },
      { key: "cfworker_subdomain", label: "Subdomain" },
      { key: "cfworker_random_subdomain", label: "Random subdomain", hint: "true/false" },
      { key: "cfworker_fingerprint", label: "Fingerprint" },
    ],
  },
  {
    label: "AppleMail",
    keys: [
      { key: "applemail_base_url", label: "Base URL" },
      { key: "applemail_pool_dir", label: "Pool directory" },
      { key: "applemail_pool_file", label: "Pool file" },
    ],
  },
  {
    label: "Sub2API",
    keys: [
      { key: "sub2api_api_url", label: "API URL" },
      { key: "sub2api_api_key", label: "API Key", secret: true },
      { key: "sub2api_group_ids", label: "Group IDs" },
    ],
  },
  {
    label: "CPA Manager",
    keys: [
      { key: "cpa_api_url", label: "API URL" },
      { key: "cpa_api_key", label: "API Key", secret: true },
      { key: "cpa_cleanup_enabled", label: "Cleanup enabled", hint: "true/false" },
      { key: "cpa_cleanup_interval_minutes", label: "Cleanup interval (min)" },
      { key: "cpa_cleanup_threshold", label: "Cleanup threshold" },
      { key: "cpa_cleanup_concurrency", label: "Cleanup concurrency" },
      { key: "cpa_cleanup_register_delay_seconds", label: "Re-register delay (giây)" },
    ],
  },
  {
    label: "Laoudo",
    keys: [
      { key: "laoudo_auth", label: "Auth token", secret: true },
      { key: "laoudo_email", label: "Email" },
      { key: "laoudo_account_id", label: "Account ID" },
    ],
  },
  {
    label: "Integrations",
    keys: [
      { key: "team_manager_url", label: "Team Manager URL" },
      { key: "team_manager_key", label: "Team Manager Key", secret: true },
      { key: "codex_proxy_url", label: "Codex Proxy URL" },
      { key: "codex_proxy_key", label: "Codex Proxy Key", secret: true },
      { key: "codex_proxy_upload_type", label: "Upload type" },
      { key: "cliproxyapi_base_url", label: "CLIProxy API URL" },
      { key: "cliproxyapi_management_key", label: "CLIProxy Key", secret: true },
      { key: "grok2api_url", label: "Grok2API URL" },
      { key: "grok2api_app_key", label: "Grok2API App Key", secret: true },
      { key: "grok2api_pool", label: "Grok2API Pool" },
      { key: "grok2api_quota", label: "Grok2API Quota" },
      { key: "kiro_manager_path", label: "Kiro Manager Path" },
      { key: "kiro_manager_exe", label: "Kiro Manager Exe" },
    ],
  },
  {
    label: "Contribution",
    keys: [
      { key: "contribution_enabled", label: "Enabled", hint: "true/false" },
      { key: "contribution_server_url", label: "Server URL" },
      { key: "contribution_key", label: "Key", secret: true },
    ],
  },
];
