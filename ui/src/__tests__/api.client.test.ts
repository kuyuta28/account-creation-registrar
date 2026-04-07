import { describe, it, expect } from "vitest";
import { api, wsLogs } from "../api/client";
import { http, HttpResponse } from "msw";
import { server } from "./mocks/server";
import { BASE, mockAccounts, mockJobs } from "./mocks/handlers";

const _ok = <T>(data: T) => ({
  success: true,
  data,
  meta: { request_id: "test", ts: new Date().toISOString() },
});

describe("api.getAccounts", () => {
  it("returns all accounts", async () => {
    const result = await api.getAccounts();
    expect(result).toHaveLength(mockAccounts.length);
    expect(result[0].email).toBe("alice@test.com");
  });

  it("passes service filter as query param", async () => {
    let capturedUrl = "";
    server.use(
      http.get(`${BASE}/accounts`, ({ request }) => {
        capturedUrl = request.url;
        return HttpResponse.json(_ok([mockAccounts[0]]));
      })
    );
    await api.getAccounts("TWOSLIDES");
    expect(capturedUrl).toContain("service=TWOSLIDES");
  });
});

describe("api.deleteAccount", () => {
  it("calls DELETE with encoded service/email", async () => {
    let method = "";
    server.use(
      http.delete(`${BASE}/accounts/:svc/:email`, ({ request }) => {
        method = request.method;
        return HttpResponse.json(_ok({ deleted: true }));
      })
    );
    const result = await api.deleteAccount("TWOSLIDES", "alice@test.com");
    expect(method).toBe("DELETE");
    expect(result.deleted).toBe(true);
  });
});

describe("api.updateAccount", () => {
  it("sends PATCH with body", async () => {
    let body: unknown;
    server.use(
      http.patch(`${BASE}/accounts/:svc/:email`, async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(_ok(mockAccounts[0]));
      })
    );
    await api.updateAccount("TWOSLIDES", "alice@test.com", { disabled: true });
    expect(body).toEqual({ disabled: true });
  });
});

describe("api.getServices", () => {
  it("returns services list", async () => {
    const result = await api.getServices();
    expect(result).toContain("TWOSLIDES");
    expect(result).toContain("OPENROUTER");
  });
});

describe("api.startJob", () => {
  it("POSTs correct payload", async () => {
    let body: unknown;
    server.use(
      http.post(`${BASE}/registration/jobs`, async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(_ok(mockJobs[0]));
      })
    );
    await api.startJob("CHATGPT", 5, 2);
    expect(body).toEqual({ service: "CHATGPT", count: 5, workers: 2 });
  });

  it("defaults workers to 1", async () => {
    let body: unknown;
    server.use(
      http.post(`${BASE}/registration/jobs`, async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(_ok(mockJobs[0]));
      })
    );
    await api.startJob("CHATGPT", 3);
    expect((body as any).workers).toBe(1);
  });
});

describe("api.getJobs / getJob", () => {
  it("getJobs returns list", async () => {
    const result = await api.getJobs();
    expect(result).toHaveLength(mockJobs.length);
  });

  it("getJob returns single job", async () => {
    const result = await api.getJob("job-2");
    expect(result.id).toBe("job-2");
    expect(result.status).toBe("done");
  });
});

describe("api.cancelJob", () => {
  it("POSTs to cancel endpoint", async () => {
    const result = await api.cancelJob("job-2");
    expect(result.cancelled).toBe(true);
  });
});

describe("api.config", () => {
  it("getConfigRaw returns content", async () => {
    const result = await api.getConfigRaw("config.yaml");
    expect(result.content).toBe("key: value\n");
  });

  it("saveConfigRaw sends PUT with content", async () => {
    let body: unknown;
    server.use(
      http.put(`${BASE}/config/raw`, async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(_ok({ saved: true }));
      })
    );
    const result = await api.saveConfigRaw("new: content\n");
    expect((body as any).content).toBe("new: content\n");
    expect(result.saved).toBe(true);
  });

  it("listConfigFiles returns files", async () => {
    const result = await api.listConfigFiles();
    expect(result.files).toContain("config.yaml");
  });
});

describe("wsLogs", () => {
  it("creates WebSocket with correct URL", () => {
    const ws = wsLogs("job-abc");
    expect(ws.url).toContain("job-abc");
    expect(ws.url).toContain("ws://");
  });
});
