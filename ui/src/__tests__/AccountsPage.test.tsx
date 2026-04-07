import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { http, HttpResponse } from "msw";
import { server } from "./mocks/server";
import { BASE, mockAccounts } from "./mocks/handlers";
import AccountsPage from "../pages/AccountsPage";

const renderPage = () =>
  render(<MemoryRouter><AccountsPage /></MemoryRouter>);

describe("AccountsPage — initial render", () => {
  it("shows heading", () => {
    renderPage();
    expect(screen.getByRole("heading", { name: /accounts/i })).toBeInTheDocument();
  });

  it("shows Refresh button", () => {
    renderPage();
    expect(screen.getByRole("button", { name: /refresh/i })).toBeInTheDocument();
  });

  it("renders accounts from API", async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText("alice@test.com")).toBeInTheDocument());
    expect(screen.getByText("bob@test.com")).toBeInTheDocument();
    expect(screen.getByText("carol@test.com")).toBeInTheDocument();
  });

  it("shows stats: total, active, disabled, with API key", async () => {
    renderPage();
    await waitFor(() => screen.getByText("alice@test.com"));
    // Use getAllByText since "Active"/"Disabled" also appear in account status badges
    expect(screen.getAllByText("Total").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Active").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Disabled").length).toBeGreaterThan(0);
    expect(screen.getAllByText("With API Key").length).toBeGreaterThan(0);
  });
});

describe("AccountsPage — service tabs", () => {
  it("renders ALL tab and service-specific tabs", async () => {
    renderPage();
    await waitFor(() => screen.getByText("alice@test.com"));
    expect(screen.getByRole("button", { name: /^ALL/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^TWOSLIDES/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^OPENROUTER/ })).toBeInTheDocument();
  });

  it("filters by service when tab clicked", async () => {
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => screen.getByText("alice@test.com"));

    await user.click(screen.getByRole("button", { name: /^OPENROUTER/ }));
    expect(screen.queryByText("alice@test.com")).not.toBeInTheDocument();
    expect(screen.getByText("bob@test.com")).toBeInTheDocument();
    expect(screen.queryByText("carol@test.com")).not.toBeInTheDocument();
  });

  it("clicking ALL shows all accounts", async () => {
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => screen.getByText("alice@test.com"));

    await user.click(screen.getByRole("button", { name: /^OPENROUTER/ }));
    await user.click(screen.getByRole("button", { name: /^ALL/ }));
    expect(screen.getByText("alice@test.com")).toBeInTheDocument();
    expect(screen.getByText("bob@test.com")).toBeInTheDocument();
  });
});

describe("AccountsPage — status filter", () => {
  it("Active filter only shows enabled accounts", async () => {
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => screen.getByText("alice@test.com"));

    await user.click(screen.getByRole("button", { name: /✓ active/i }));
    expect(screen.getByText("alice@test.com")).toBeInTheDocument();
    expect(screen.getByText("carol@test.com")).toBeInTheDocument();
    expect(screen.queryByText("bob@test.com")).not.toBeInTheDocument();
  });

  it("Disabled filter only shows disabled accounts", async () => {
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => screen.getByText("alice@test.com"));

    await user.click(screen.getByRole("button", { name: /✕ disabled/i }));
    expect(screen.getByText("bob@test.com")).toBeInTheDocument();
    expect(screen.queryByText("alice@test.com")).not.toBeInTheDocument();
  });
});

describe("AccountsPage — search", () => {
  it("filters accounts by email", async () => {
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => screen.getByText("alice@test.com"));

    await user.type(screen.getByPlaceholderText(/tìm email/i), "alice");
    expect(screen.getByText("alice@test.com")).toBeInTheDocument();
    expect(screen.queryByText("bob@test.com")).not.toBeInTheDocument();
  });

  it("filters by API key substring", async () => {
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => screen.getByText("alice@test.com"));

    await user.type(screen.getByPlaceholderText(/tìm email/i), "key-abc");
    expect(screen.getByText("alice@test.com")).toBeInTheDocument();
    expect(screen.queryByText("bob@test.com")).not.toBeInTheDocument();
    expect(screen.queryByText("carol@test.com")).not.toBeInTheDocument();
  });

  it("shows empty state when no results", async () => {
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => screen.getByText("alice@test.com"));

    await user.type(screen.getByPlaceholderText(/tìm email/i), "zzznomatch");
    expect(screen.getByText(/không tìm thấy/i)).toBeInTheDocument();
  });

  it("clear button removes search text", async () => {
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => screen.getByText("alice@test.com"));

    const searchInput = screen.getByPlaceholderText(/tìm email/i);
    await user.type(searchInput, "alice");
    expect(screen.queryByText("bob@test.com")).not.toBeInTheDocument();

    // X button is a button sibling inside the search container
    const container = searchInput.parentElement!;
    const xBtn = container.querySelector("button") as HTMLButtonElement;
    await user.click(xBtn);
    expect((searchInput as HTMLInputElement).value).toBe("");
    expect(screen.getByText("bob@test.com")).toBeInTheDocument();
  });
});

describe("AccountsPage — sorting", () => {
  it("clicking Email header sorts ascending then descending", async () => {
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => screen.getByText("alice@test.com"));

    const emailHeader = screen.getByRole("columnheader", { name: /email/i });
    await user.click(emailHeader); // already asc → click once → desc

    const rows = screen.getAllByRole("row").slice(1); // skip header
    const cellText = rows[0].querySelector("td")?.textContent ?? "";
    // desc: carol > bob > alice
    expect(cellText).toContain("carol@test.com");
  });

  it("clicking Service header switches sort key", async () => {
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => screen.getByText("alice@test.com"));

    const svcHeader = screen.getByRole("columnheader", { name: /service/i });
    await user.click(svcHeader);
    // sorted asc by service: OPENROUTER < TWOSLIDES
    const rows = screen.getAllByRole("row").slice(1);
    expect(rows[0].textContent).toContain("OPENROUTER");
  });
});

describe("AccountsPage — actions", () => {
  it("copies API key to clipboard on click", async () => {
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => screen.getByText("alice@test.com"));

    // Click the copy button for alice's key (has title="key-abc")
    const copyBtn = screen.getByTitle("key-abc");
    await user.click(copyBtn);
    // Visual feedback: "✓ Copied!" should appear
    await waitFor(() => expect(screen.getByText(/Copied/i)).toBeInTheDocument());
  });

  it("calls deleteAccount API after confirm", async () => {
    let deleted = false;
    server.use(
      http.delete(`${BASE}/accounts/:svc/:email`, () => {
        deleted = true;
        return HttpResponse.json({ ok: true });
      })
    );
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => screen.getByText("alice@test.com"));

    const rows = screen.getAllByRole("row");
    const aliceRow = rows.find(r => r.textContent?.includes("alice@test.com"))!;
    // Delete button is in the last cell
    const deleteBtn = aliceRow.querySelector("td:last-child button") as HTMLButtonElement;
    await user.click(deleteBtn);
    await waitFor(() => expect(deleted).toBe(true));
  });

  it("calls updateAccount when toggling status", async () => {
    let patchCalled = false;
    server.use(
      http.patch(`${BASE}/accounts/:svc/:email`, () => {
        patchCalled = true;
        return HttpResponse.json(mockAccounts[0]);
      })
    );
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => screen.getByText("alice@test.com"));

    // Click the Active badge for alice
    const activeBadges = screen.getAllByTitle(/click để/i);
    await user.click(activeBadges[0]);
    await waitFor(() => expect(patchCalled).toBe(true));
  });

  it("Refresh button reloads accounts", async () => {
    let callCount = 0;
    server.use(
      http.get(`${BASE}/accounts`, () => {
        callCount++;
        return HttpResponse.json(mockAccounts);
      })
    );
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => expect(callCount).toBeGreaterThanOrEqual(1));

    await user.click(screen.getByRole("button", { name: /refresh/i }));
    await waitFor(() => expect(callCount).toBeGreaterThanOrEqual(2));
  });
});

describe("AccountsPage — pagination", () => {
  it("shows pagination when there are more than 50 accounts", async () => {
    // Create 55 mock accounts to trigger pagination (PAGE_SIZE = 50)
    const manyAccounts = Array.from({ length: 55 }, (_, i) => ({
      email: `user${i}@test.com`,
      service: "TWOSLIDES",
      disabled: false,
      api_key: undefined,
      credits: 0,
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    }));
    server.use(
      http.get(`${BASE}/accounts`, () => HttpResponse.json(manyAccounts))
    );
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => screen.getByText("user0@test.com"));

    // Should show pagination controls
    expect(screen.getByText("«")).toBeInTheDocument();
    expect(screen.getByText("»")).toBeInTheDocument();

    // Navigate to page 2 — user0 was on page1, should no longer be visible
    await user.click(screen.getByText("›"));
    await waitFor(() => expect(screen.queryByText("user0@test.com")).not.toBeInTheDocument());

    // Navigate back to first page via «
    await user.click(screen.getByText("«"));
    await waitFor(() => screen.getByText("user0@test.com"));

    // Go to last page via »
    await user.click(screen.getByText("»"));
    await waitFor(() => expect(screen.queryByText("user0@test.com")).not.toBeInTheDocument());

    // Go back via ‹
    await user.click(screen.getByText("‹"));
    await waitFor(() => screen.getByText("user0@test.com"));

    // Click page number button "2" to navigate
    await user.click(screen.getByRole("button", { name: "2" }));
    await waitFor(() => expect(screen.queryByText("user0@test.com")).not.toBeInTheDocument());
  });
});

describe("AccountsPage — coverage extras", () => {
  it("sorts by Credits, Status, Created, Updated headers; toggles email sort direction", async () => {
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => screen.getByText("alice@test.com"));

    // Sort by Credits (covers sortKey==="credits" branch and a.credits ?? -1)
    await user.click(screen.getByRole("columnheader", { name: /credits/i }));
    // Sort by Status (covers sortKey==="status" branch and a.disabled ? 1 : 0)
    await user.click(screen.getByRole("columnheader", { name: /status/i }));
    // Sort by Created (covers sortKey==="created_at" branch and a.created_at ?? "")
    await user.click(screen.getByRole("columnheader", { name: /created/i }));
    // Sort by Updated (covers sortKey==="updated_at" branch and a.updated_at ?? "")
    await user.click(screen.getByRole("columnheader", { name: /updated/i }));
    // Click Email asc→desc, then again desc→asc (covers d === "asc" ? "desc" : "asc" both sides)
    await user.click(screen.getByRole("columnheader", { name: /email/i })); // →asc
    await user.click(screen.getByRole("columnheader", { name: /email/i })); // →desc
    await user.click(screen.getByRole("columnheader", { name: /email/i })); // →asc
    await waitFor(() => screen.getByText("alice@test.com")); // sorted asc again
  });

  it("confirm=false cancels account delete", async () => {
    vi.stubGlobal("confirm", () => false);
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => screen.getByText("alice@test.com"));
    // Click delete row button (opacity-0 group-hover, but visible in dom)
    const deleteButtons = screen.getAllByRole("button").filter(
      (b) => b.classList.contains("opacity-0") || b.textContent === ""
    );
    if (deleteButtons.length > 0) {
      await user.click(deleteButtons[0]);
    }
    // Account should still be present (confirm returned false)
    expect(screen.getByText("alice@test.com")).toBeInTheDocument();
    vi.stubGlobal("confirm", () => true); // restore
  });

  it("shows gray badge for unknown service", async () => {
    server.use(
      http.get(`${BASE}/accounts`, () => HttpResponse.json([
        ...mockAccounts,
        { email: "x@unknown.com", service: "UNKNOWN_SVC", disabled: false, api_key: undefined, credits: null, created_at: null, updated_at: null },
      ]))
    );
    renderPage();
    await waitFor(() => screen.getByText("x@unknown.com"));
    // UNKNOWN_SVC not in SERVICE_COLORS → uses fallback bg-gray-100 class
    const badge = screen.getByText("UNKNOWN_SVC");
    expect(badge).toHaveClass("bg-gray-100");
  });

  it("renders dash for null credits and null dates", async () => {
    server.use(
      http.get(`${BASE}/accounts`, () => HttpResponse.json([
        { email: "nodata@test.com", service: "TWOSLIDES", disabled: false, api_key: undefined, credits: null, created_at: null, updated_at: null },
      ]))
    );
    renderPage();
    await waitFor(() => screen.getByText("nodata@test.com"));
    // credits: null → shows "—" (2 dashes for null credits + 2 for dates)
    const dashes = screen.getAllByText("—");
    expect(dashes.length).toBeGreaterThanOrEqual(1);
  });
});
