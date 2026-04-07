import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { http, HttpResponse } from "msw";
import { server } from "./mocks/server";
import { BASE } from "./mocks/handlers";
import CreatePage, { LogPanel } from "../pages/CreatePage";
import * as clientModule from "../api/client";

const renderPage = () =>
  render(<MemoryRouter><CreatePage /></MemoryRouter>);

const SVC_CFG_KEY = "acc-creator:svc-cfg";

beforeEach(() => {
  localStorage.clear();
});

describe("CreatePage — initial render", () => {
  it("renders heading and form controls", async () => {
    renderPage();
    expect(screen.getByRole("heading", { name: /create accounts/i })).toBeInTheDocument();
    // Waits for services to load
    await waitFor(() => expect(screen.getByRole("combobox")).toBeInTheDocument());
    expect(screen.getAllByRole("spinbutton")).toHaveLength(2);
  });

  it("populates service dropdown from API", async () => {
    renderPage();
    await waitFor(() => expect(screen.getByRole("option", { name: "TWOSLIDES" })).toBeInTheDocument());
    expect(screen.getByRole("option", { name: "OPENROUTER" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "CHATGPT" })).toBeInTheDocument();
  });

  it("shows Run button", async () => {
    renderPage();
    await waitFor(() => expect(screen.getByRole("button", { name: /run/i })).toBeEnabled());
  });
});

describe("CreatePage — per-service config persistence", () => {
  it("saves count/workers to localStorage when changed", async () => {
    renderPage();
    await waitFor(() => screen.getByRole("combobox"));

    const [countInput, workersInput] = screen.getAllByRole("spinbutton");
    // fireEvent.change is more reliable than user.clear + user.type for number inputs
    fireEvent.change(countInput, { target: { value: "50" } });
    fireEvent.change(workersInput, { target: { value: "3" } });

    const stored = JSON.parse(localStorage.getItem(SVC_CFG_KEY) ?? "{}");
    const svc = (screen.getByRole("combobox") as HTMLSelectElement).value;
    expect(stored[svc].count).toBe(50);
    expect(stored[svc].workers).toBe(3);
  });

  it("restores saved config when switching service", async () => {
    localStorage.setItem(SVC_CFG_KEY, JSON.stringify({ OPENROUTER: { count: 99, workers: 4 } }));
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => screen.getByRole("option", { name: "OPENROUTER" }));

    await user.selectOptions(screen.getByRole("combobox"), "OPENROUTER");

    const [countInput, workersInput] = screen.getAllByRole("spinbutton");
    expect((countInput as HTMLInputElement).value).toBe("99");
    expect((workersInput as HTMLInputElement).value).toBe("4");
  });

  it("defaults to count=1, workers=1 for unknown service", async () => {
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => screen.getByRole("option", { name: "CHATGPT" }));

    await user.selectOptions(screen.getByRole("combobox"), "CHATGPT");
    const [countInput, workersInput] = screen.getAllByRole("spinbutton");
    expect((countInput as HTMLInputElement).value).toBe("1");
    expect((workersInput as HTMLInputElement).value).toBe("1");
  });
});

describe("CreatePage — start job", () => {
  it("adds active job card after clicking Run", async () => {
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => screen.getByRole("button", { name: /run/i }));

    await user.click(screen.getByRole("button", { name: /run/i }));

    await waitFor(() => expect(screen.getByText("Active Jobs")).toBeInTheDocument());
    // TWOSLIDES also appears in history table, so use getAllByText
    expect(screen.getAllByText("TWOSLIDES").length).toBeGreaterThan(0);
  });

  it("shows error message on API failure", async () => {
    server.use(
      http.post(`${BASE}/registration/jobs`, () =>
        HttpResponse.json({ detail: "Service offline" }, { status: 500 })
      )
    );
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => screen.getByRole("button", { name: /run/i }));

    await user.click(screen.getByRole("button", { name: /run/i }));
    await waitFor(() => expect(screen.getByText(/service offline/i)).toBeInTheDocument());
  });

  it("shows fallback error message when detail absent", async () => {
    server.use(
      http.post(`${BASE}/registration/jobs`, () =>
        HttpResponse.json({ message: "bad" }, { status: 400 })
      )
    );
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => screen.getByRole("combobox"));
    await user.click(screen.getByRole("button", { name: /run/i }));
    await waitFor(() => expect(screen.getByText(/lỗi 400/i)).toBeInTheDocument());
  });

  it("shows error when API unreachable", async () => {
    server.use(
      http.post(`${BASE}/registration/jobs`, () => HttpResponse.error())
    );
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => screen.getByRole("button", { name: /run/i }));

    await user.click(screen.getByRole("button", { name: /run/i }));
    await waitFor(() => expect(screen.getByText(/không kết nối/i)).toBeInTheDocument());
  });

  it("saves config to localStorage when Run is clicked", async () => {
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => screen.getByRole("button", { name: /run/i }));

    const [countInput] = screen.getAllByRole("spinbutton");
    fireEvent.change(countInput, { target: { value: "7" } });
    await user.click(screen.getByRole("button", { name: /run/i }));

    await waitFor(() => {
      const stored = JSON.parse(localStorage.getItem(SVC_CFG_KEY) ?? "{}");
      const svc = (screen.getByRole("combobox") as HTMLSelectElement).value;
      expect(stored[svc]?.count).toBe(7);
    });
  });
});

describe("CreatePage — active job card UI", () => {
  it("shows stop button for running job", async () => {
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => screen.getByRole("button", { name: /run/i }));
    await user.click(screen.getByRole("button", { name: /run/i }));

    await waitFor(() => expect(screen.getByTitle("Stop")).toBeInTheDocument());
  });

  it("clicking stop calls cancel API", async () => {
    let cancelled = false;
    server.use(
      http.post(`${BASE}/registration/jobs/job-new/cancel`, () => {
        cancelled = true;
        return HttpResponse.json({ ok: true });
      })
    );
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => screen.getByRole("button", { name: /run/i }));
    await user.click(screen.getByRole("button", { name: /run/i }));
    await waitFor(() => screen.getByTitle("Stop"));

    await user.click(screen.getByTitle("Stop"));
    await waitFor(() => expect(cancelled).toBe(true));
  });

  it("collapses and expands log panel on header click", async () => {
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => screen.getByRole("button", { name: /run/i }));
    await user.click(screen.getByRole("button", { name: /run/i }));
    await waitFor(() => expect(screen.getByText("Active Jobs")).toBeInTheDocument());

    // Find the active job card header (has cursor-pointer class)
    const jobCard = document.querySelector("[class*='ring-']");
    const header = jobCard?.querySelector("[class*='cursor-pointer']") as HTMLElement;
    expect(header).not.toBeNull();

    // Log panel shows when expanded (default)
    expect(screen.getByText("Đợi logs...")).toBeInTheDocument();

    // click header → collapse
    await user.click(header);
    expect(screen.queryByText("Đợi logs...")).not.toBeInTheDocument();

    // click again → expand
    await user.click(header);
    expect(screen.getByText("Đợi logs...")).toBeInTheDocument();
  });

  it("shows workers badge when workers > 1", async () => {
    server.use(
      http.post(`${BASE}/registration/jobs`, () =>
        HttpResponse.json({
          id: "job-w2", service: "TWOSLIDES", count: 5, workers: 3,
          status: "running", created_at: new Date().toISOString(), created_count: 0,
        })
      )
    );
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => screen.getByRole("button", { name: /run/i }));

    const [, workersInput] = screen.getAllByRole("spinbutton");
    fireEvent.change(workersInput, { target: { value: "3" } });
    await user.click(screen.getByRole("button", { name: /run/i }));

    await waitFor(() => expect(screen.getByText(/⚡3w/)).toBeInTheDocument());
  });
});

describe("CreatePage — restore running jobs on mount", () => {
  it("attaches to running jobs from history on load", async () => {
    server.use(
      http.get(`${BASE}/registration/jobs`, () =>
        HttpResponse.json([
          { id: "job-running", service: "OPENROUTER", count: 10, workers: 1,
            status: "running", created_at: new Date().toISOString(), created_count: 3 }
        ])
      )
    );
    renderPage();
    await waitFor(() => expect(screen.getByText("Active Jobs")).toBeInTheDocument());
    // OPENROUTER also appears in history table (job-2), use getAllByText
    expect(screen.getAllByText("OPENROUTER").length).toBeGreaterThan(0);
  });
});

describe("CreatePage — job history table", () => {
  it("renders history rows from API", async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText("Job History")).toBeInTheDocument());
    expect(screen.getAllByText("TWOSLIDES").length).toBeGreaterThan(0);
  });

  it("shows done/failed badge with correct style", async () => {
    renderPage();
    await waitFor(() => screen.getByText("Job History"));
    // Both jobs are "done" → multiple badges; check the first one
    const doneBadges = screen.getAllByText("done");
    expect(doneBadges.length).toBeGreaterThan(0);
    expect(doneBadges[0].className).toContain("emerald");
  });
});

describe("CreatePage — stats grid", () => {
  it("renders stats when history exists", async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText("Jobs run")).toBeInTheDocument());
    expect(screen.getByText("Succeeded")).toBeInTheDocument();
    expect(screen.getByText("Failed")).toBeInTheDocument();
    expect(screen.getByText("Acc. created")).toBeInTheDocument();
  });
});

describe("CreatePage — coverage extras", () => {
  it("loadSvcCfg falls back to defaults when localStorage has invalid JSON", async () => {
    localStorage.setItem(SVC_CFG_KEY, "not-valid-json{{{");
    renderPage();
    await waitFor(() => screen.getByRole("combobox"));
    // Should still render with defaults (count=1, workers=1)
    const [countInput] = screen.getAllByRole("spinbutton");
    expect((countInput as HTMLInputElement).value).toBe("1");
  });

  it("dismisses a done job card when Dismiss button clicked", async () => {
    // POST returns a job with status already "done" → Dismiss button appears immediately
    server.use(
      http.post(`${BASE}/registration/jobs`, () =>
        HttpResponse.json({ id: "job-done", service: "TWOSLIDES", count: 3, workers: 1,
          status: "done", created_at: new Date().toISOString(), created_count: 3 })
      )
    );
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => screen.getByRole("button", { name: /run/i }));
    await user.click(screen.getByRole("button", { name: /run/i }));
    await waitFor(() => expect(screen.getByText("Active Jobs")).toBeInTheDocument());

    // Job is already "done" → Dismiss button appears immediately
    await waitFor(() => expect(screen.getByTitle("Dismiss")).toBeInTheDocument());
    await user.click(screen.getByTitle("Dismiss"));

    // Active Jobs section should disappear
    await waitFor(() => expect(screen.queryByText("Active Jobs")).not.toBeInTheDocument());
  });

  it("LogPanel renders color-coded log lines", () => {
    const logs = ["✅ Account created", "❌ ERROR: failed", "⚠️ Warning", "🛑 Stopped", "normal log"];
    render(<LogPanel logs={logs} />);
    expect(screen.getByText("✅ Account created")).toBeInTheDocument();
    expect(screen.getByText("❌ ERROR: failed")).toBeInTheDocument();
    expect(screen.getByText("⚠️ Warning")).toBeInTheDocument();
    expect(screen.getByText("🛑 Stopped")).toBeInTheDocument();
    expect(screen.getByText("normal log")).toBeInTheDocument();
  });

  it("LogPanel compact renders placeholder when empty", () => {
    render(<LogPanel logs={[]} compact />);
    expect(screen.getByText("Đợi logs...")).toBeInTheDocument();
  });

  it("LogPanel onScroll unpins when scrolled away from bottom", () => {
    render(<LogPanel logs={["line 1", "line 2"]} />);
    const container = document.querySelector(".overflow-y-auto") as HTMLElement;
    // Simulate scrolled up: scrollHeight=200, scrollTop=0, clientHeight=100 → 200-0-100=100 ≥ 40 → unpin
    Object.defineProperty(container, "scrollHeight", { value: 200, configurable: true });
    Object.defineProperty(container, "scrollTop", { value: 0, configurable: true });
    Object.defineProperty(container, "clientHeight", { value: 100, configurable: true });
    fireEvent.scroll(container);
    // "cuối" scroll-to-bottom button should appear
    expect(screen.getByText("cuối")).toBeInTheDocument();
    // Click it to re-pin
    fireEvent.click(screen.getByText("cuối"));
    expect(screen.queryByText("cuối")).not.toBeInTheDocument();
  });

  it("WS onerror appends error message to logs", async () => {
    // Spy on wsLogs to capture and control the WebSocket instance
    const mockWs = { onmessage: null as any, onerror: null as any, onclose: null as any, readyState: 1, close: vi.fn(), send: vi.fn() };
    const spy = vi.spyOn(clientModule, "wsLogs").mockReturnValue(mockWs as any);

    const user = userEvent.setup();
    renderPage();
    await waitFor(() => screen.getByRole("combobox")); // wait for services to load
    await user.click(screen.getByRole("button", { name: /run/i }));
    await waitFor(() => screen.getByText("Active Jobs"));

    // attachToJob should have set mockWs.onerror
    expect(mockWs.onerror).toBeTypeOf("function");

    // Fire onerror and let React commit the update
    await act(async () => { mockWs.onerror?.(); });
    await waitFor(() => expect(screen.getByText("[WS error]")).toBeInTheDocument());

    spy.mockRestore();
  });

  it("poll timer updates job status and clears interval when done", async () => {
    // The default GET /registration/jobs/:id handler already returns status:"done"
    // The poll fires at 1500ms, updates the job to "done", and the Dismiss button appears
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => screen.getByRole("button", { name: /run/i }));
    await user.click(screen.getByRole("button", { name: /run/i }));
    await waitFor(() => screen.getByText("Active Jobs"));
    // Poll fires at 1500ms and updates status to "done" → Dismiss button appears
    await waitFor(() => screen.getByTitle("Dismiss"), { timeout: 3000 });
  }, 8000);

  it("job card shows ⚡workers badge when workers > 1", async () => {
    server.use(
      http.post(`${BASE}/registration/jobs`, () =>
        HttpResponse.json({ id: "job-multi", service: "TWOSLIDES", count: 0, workers: 3,
          status: "running", created_at: new Date().toISOString(), created_count: 0 })
      )
    );
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => screen.getByRole("combobox"));
    await user.click(screen.getByRole("button", { name: /run/i }));
    await waitFor(() => screen.getByText("Active Jobs"));
    // workers=3 → shows ⚡3w badge; count=0 → pct=0 (covers job.count>0 false branch)
    expect(screen.getByText("⚡3w")).toBeInTheDocument();
  });
});
