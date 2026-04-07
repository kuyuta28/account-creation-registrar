import "@testing-library/jest-dom";
import { afterAll, afterEach, beforeAll, vi } from "vitest";
import { server } from "./mocks/server";

beforeAll(() => server.listen({ onUnhandledRequest: "warn" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

// MockWebSocket extends EventTarget → supports addEventListener (required by MSW internals)
class MockWebSocket extends EventTarget {
  static lastInstance: MockWebSocket | null = null;
  url: string;
  onmessage: ((e: { data: string }) => void) | null = null;
  onerror:   (() => void) | null = null;
  onclose:   (() => void) | null = null;
  readyState = 1;
  constructor(url: string) { super(); this.url = url; MockWebSocket.lastInstance = this; }
  close() { this.readyState = 3; this.onclose?.(); }
  send(_: string) {}
}
vi.stubGlobal("WebSocket", MockWebSocket);

// scrollIntoView is not implemented in jsdom
window.HTMLElement.prototype.scrollIntoView = vi.fn();

// Mock window.confirm
vi.stubGlobal("confirm", () => true);

// Mock clipboard as a vi spy so toHaveBeenCalledWith works
Object.defineProperty(navigator, "clipboard", {
  writable: true,
  configurable: true,
  value: { writeText: vi.fn().mockResolvedValue(undefined) },
});

