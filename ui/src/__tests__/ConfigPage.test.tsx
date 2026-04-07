import { describe, it, expect } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { http, HttpResponse } from "msw";
import { server } from "./mocks/server";
import { BASE } from "./mocks/handlers";
import ConfigPage from "../pages/ConfigPage";

const renderPage = () =>
  render(<MemoryRouter><ConfigPage /></MemoryRouter>);

describe("ConfigPage — initial render", () => {
  it("shows heading", () => {
    renderPage();
    expect(screen.getByRole("heading", { name: /config/i })).toBeInTheDocument();
  });

  it("shows Save button", () => {
    renderPage();
    expect(screen.getByRole("button", { name: /save/i })).toBeInTheDocument();
  });

  it("loads file list and renders tabs", async () => {
    renderPage();
    // config.yaml appears in both the file list and the editor header span
    await waitFor(() => expect(screen.getAllByText("config.yaml").length).toBeGreaterThan(0));
    expect(screen.getAllByText("mail.yaml").length).toBeGreaterThan(0);
  });

  it("shows human-readable labels for known files", async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText("Core")).toBeInTheDocument());
  });

  it("renders default file list when API not yet returned", () => {
    server.use(
      http.get(`${BASE}/config/files`, () => new Promise(() => {})) // never resolves
    );
    renderPage();
    // Falls back to Object.keys(FILE_LABELS)
    expect(screen.getByText("Core")).toBeInTheDocument();
  });

  it("loads content of active file into textarea", async () => {
    renderPage();
    await waitFor(() => {
      const textarea = screen.getByRole("textbox") as HTMLTextAreaElement;
      expect(textarea.value).toContain("key: value");
    });
  });
});

describe("ConfigPage — file switching", () => {
  it("clicking a different file loads its content", async () => {
    server.use(
      http.get(`${BASE}/config/raw`, ({ request }) => {
        const url = new URL(request.url);
        const file = url.searchParams.get("file");
        return HttpResponse.json({ content: `# ${file}\n`, file: file ?? "" });
      })
    );
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => screen.getByText("mail.yaml"));

    await user.click(screen.getByText("mail.yaml"));
    await waitFor(() => {
      const textarea = screen.getByRole("textbox") as HTMLTextAreaElement;
      expect(textarea.value).toContain("mail.yaml");
    });
  });

  it("active file has highlighted style", async () => {
    renderPage();
    await waitFor(() => screen.getAllByText("config.yaml"));
    // Find the file-list button (not the editor header span)
    const allEls = screen.getAllByText("config.yaml");
    const btn = allEls.map(el => el.closest("button")).find(b => b !== null);
    expect(btn).not.toBeNull();
    expect(btn!.className).toContain("border-l-brand-500");
  });
});

describe("ConfigPage — save", () => {
  it("shows saving state then success message", async () => {
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => screen.getByRole("textbox"));

    await user.click(screen.getByRole("button", { name: /save/i }));
    await waitFor(() => expect(screen.getByText(/saved|đã lưu/i)).toBeInTheDocument());
  });

  it("sends updated content to API", async () => {
    let savedContent = "";
    server.use(
      http.put(`${BASE}/config/raw`, async ({ request }) => {
        const body = await request.json() as { content: string };
        savedContent = body.content;
        return HttpResponse.json({ ok: true });
      })
    );
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => {
      const ta = screen.getByRole("textbox") as HTMLTextAreaElement;
      expect(ta.value).toBeTruthy();
    });

    const textarea = screen.getByRole("textbox");
    await user.clear(textarea);
    await user.type(textarea, "new_key: new_value");
    await user.click(screen.getByRole("button", { name: /save/i }));

    await waitFor(() => expect(savedContent).toContain("new_key: new_value"));
  });

  it("shows error message on save failure", async () => {
    server.use(
      http.put(`${BASE}/config/raw`, () => HttpResponse.error())
    );
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => screen.getByRole("textbox"));

    await user.click(screen.getByRole("button", { name: /save/i }));
    await waitFor(() => expect(screen.getByText(/lỗi khi lưu/i)).toBeInTheDocument());
  });

  it("Save button is disabled while saving", async () => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    let resolvePromise!: (v: any) => void;
    server.use(
      http.put(`${BASE}/config/raw`, () =>
        new Promise((res) => { resolvePromise = res; })
      )
    );
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => screen.getByRole("textbox"));

    const saveBtn = screen.getByRole("button", { name: /save/i });
    await user.click(saveBtn);
    // while pending — button should be disabled
    expect(saveBtn).toBeDisabled();

    resolvePromise!(HttpResponse.json({ ok: true }) as unknown);
    await waitFor(() => expect(saveBtn).toBeEnabled());
  });
});

describe("ConfigPage — loading state", () => {
  it("Save button is disabled while loading content", async () => {
    server.use(
      http.get(`${BASE}/config/raw`, () => new Promise(() => {})) // never resolves
    );
    renderPage();
    const saveBtn = screen.getByRole("button", { name: /save/i });
    expect(saveBtn).toBeDisabled();
  });
});

describe("ConfigPage — unknown file handling", () => {
  it("shows generic icon and filename label for unknown files", async () => {
    server.use(
      http.get(`${BASE}/config/files`, () =>
        HttpResponse.json({ files: ["config.yaml", "custom.yaml"] })
      ),
      http.get(`${BASE}/config/raw`, ({ request }) => {
        const url = new URL(request.url);
        const file = url.searchParams.get("file") ?? "config.yaml";
        return HttpResponse.json({ content: `# ${file}\n`, file });
      })
    );
    renderPage();
    await waitFor(() => screen.getAllByText("custom.yaml").length > 0);
    // "custom.yaml" has no label in FILE_LABELS → shows filename directly
    expect(screen.getAllByText("custom.yaml").length).toBeGreaterThan(0);
  });
});
