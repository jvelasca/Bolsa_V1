import { describe, expect, it } from "vitest";
import { _resetSupervisedF3SyncForTests } from "@/features/trading/supervised-f3-sync";

describe("supervised-f3-sync helpers", () => {
  it("exports reset for tests without throwing", () => {
    expect(() => _resetSupervisedF3SyncForTests()).not.toThrow();
  });
});
