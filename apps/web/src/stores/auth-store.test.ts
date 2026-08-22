/**
 * Tests — payload de login multi-user (R12-AUTH F9).
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useAuthStore } from "@/stores/auth-store";

function mockLoginFetch() {
  return vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ data: { authEnabled: true } }),
  });
}

describe("auth-store login payload", () => {
  beforeEach(() => {
    useAuthStore.setState({
      authEnabled: false,
      authenticated: false,
      bootstrapError: null,
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("sends only password when login is omitted (legacy APP_PASSWORD)", async () => {
    const fetchMock = mockLoginFetch();
    vi.stubGlobal("fetch", fetchMock);

    await useAuthStore.getState().login("secret");

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/auth/login"),
      expect.objectContaining({
        method: "POST",
        credentials: "include",
        body: JSON.stringify({ password: "secret" }),
      }),
    );
  });

  it("sends only password when login is blank whitespace", async () => {
    const fetchMock = mockLoginFetch();
    vi.stubGlobal("fetch", fetchMock);

    await useAuthStore.getState().login("secret", "   ");

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/auth/login"),
      expect.objectContaining({
        body: JSON.stringify({ password: "secret" }),
      }),
    );
  });

  it("sends login and password when login is provided", async () => {
    const fetchMock = mockLoginFetch();
    vi.stubGlobal("fetch", fetchMock);

    await useAuthStore.getState().login("secret", "alice");

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/auth/login"),
      expect.objectContaining({
        body: JSON.stringify({ login: "alice", password: "secret" }),
      }),
    );
  });
});
