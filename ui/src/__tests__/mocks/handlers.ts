import { http, HttpResponse } from "msw";
import { Account, Job } from "../../api/client";
// Note: this path is correct — handlers.ts is at src/__tests__/mocks/, api/client is at src/api/

export const BASE = "http://127.0.0.1:8799/api/v1";

const _ok = <T>(data: T) => ({
  success: true,
  data,
  meta: { request_id: "test-req-id", ts: new Date().toISOString() },
});

export const mockAccounts: Account[] = [
  { email: "alice@test.com", service: "TWOSLIDES", disabled: false, api_key: "key-abc", credits: 100, created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-02T00:00:00Z" },
  { email: "bob@test.com",   service: "OPENROUTER", disabled: true,  api_key: undefined, credits: 0,   created_at: "2026-01-03T00:00:00Z", updated_at: "2026-01-04T00:00:00Z" },
  { email: "carol@test.com", service: "TWOSLIDES",  disabled: false, api_key: "key-xyz", credits: 50,  created_at: "2026-01-05T00:00:00Z", updated_at: "2026-01-06T00:00:00Z" },
];

export const mockJobs: Job[] = [
  { id: "job-1", service: "TWOSLIDES",  count: 10, workers: 2, status: "done", created_at: "2026-01-01T07:00:00Z", created_count: 10, processed_count: 10 },
  { id: "job-2", service: "OPENROUTER", count: 5,  workers: 1, status: "done", created_at: "2026-01-01T08:00:00Z", created_count: 5,  processed_count: 5  },
];

export const handlers = [
  http.get(`${BASE}/accounts`,              () => HttpResponse.json(_ok(mockAccounts))),
  http.get(`${BASE}/registration/services`, () => HttpResponse.json(_ok(["TWOSLIDES", "OPENROUTER", "CHATGPT"]))),
  http.get(`${BASE}/registration/jobs`,     () => HttpResponse.json(_ok(mockJobs))),
  http.get(`${BASE}/registration/jobs/job-2`, () => HttpResponse.json(_ok(mockJobs[1]))),
  // Wildcard handler for any job ID
  http.get(`${BASE}/registration/jobs/:id`, ({ params }) =>
    HttpResponse.json(_ok({ id: params.id, service: "TWOSLIDES", count: 1, workers: 1, status: "done", created_at: new Date().toISOString(), created_count: 1, processed_count: 1 }))
  ),
  http.post(`${BASE}/registration/jobs`, () => HttpResponse.json(_ok({
    id: "job-new", service: "TWOSLIDES", count: 3, workers: 1,
    status: "running", created_at: new Date().toISOString(), created_count: 0, processed_count: 0,
  }))),
  http.post(`${BASE}/registration/jobs/job-2/cancel`, () => HttpResponse.json(_ok({ cancelled: true }))),
  http.delete(`${BASE}/accounts/:svc/:email`, () => HttpResponse.json(_ok({ deleted: true }))),
  http.patch(`${BASE}/accounts/:svc/:email`,  () => HttpResponse.json(_ok(mockAccounts[0]))),
  http.get(`${BASE}/config/files`,  () => HttpResponse.json(_ok({ files: ["config.yaml", "mail.yaml"] }))),
  http.get(`${BASE}/config/raw`,    () => HttpResponse.json(_ok({ content: "key: value\n", file: "config.yaml" }))),
  http.put(`${BASE}/config/raw`,    () => HttpResponse.json(_ok({ saved: true }))),
];
