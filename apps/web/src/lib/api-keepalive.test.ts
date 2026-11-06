import { afterEach, describe, expect, it, vi } from "vitest";

import { api } from "@/lib/api";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("updateWorkspaceKeepalive", () => {
  it("envía la revisión y el keepalive en el body de despedida", () => {
    const fetchMock = vi.fn(async () => new Response("{}", { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    api.updateWorkspaceKeepalive("ws-1", {
      name: "Espacio",
      expectedUpdatedAt: "2026-11-02T10:00:00+00:00",
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0]! as unknown as [
      string,
      RequestInit,
    ];
    expect(url).toContain("/api/workspaces/ws-1");
    expect(init.keepalive).toBe(true);
    expect(JSON.parse(String(init.body))).toMatchObject({
      name: "Espacio",
      expectedUpdatedAt: "2026-11-02T10:00:00+00:00",
    });
  });
});
