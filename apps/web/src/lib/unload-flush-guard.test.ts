import { describe, expect, it, vi } from "vitest";

import { createUnloadFlushGuard } from "@/lib/unload-flush-guard";

describe("createUnloadFlushGuard", () => {
  it("ejecuta el flush una sola vez aunque lleguen beforeunload y pagehide", () => {
    const flush = vi.fn();
    const guard = createUnloadFlushGuard(flush);

    guard.run();
    guard.run();

    expect(flush).toHaveBeenCalledTimes(1);
  });

  it("se rearma cuando la página vuelve a estar visible", () => {
    const flush = vi.fn();
    const guard = createUnloadFlushGuard(flush);

    guard.run();
    guard.reset();
    guard.run();

    expect(flush).toHaveBeenCalledTimes(2);
  });
});
