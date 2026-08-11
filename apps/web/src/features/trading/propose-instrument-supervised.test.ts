/**
 * @vitest-environment node
 */
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api", () => ({
  api: {
    getAccountSummary: vi.fn(),
    proposeRecommendation: vi.fn(),
  },
}));

vi.mock("@/stores/estudio-membership-store", () => ({
  useEstudioMembershipStore: {
    getState: vi.fn(() => ({ contains: () => true })),
  },
}));

vi.mock("@/features/trading/demo-book-prefs", async () => {
  const actual = await vi.importActual<
    typeof import("@/features/trading/demo-book-prefs")
  >("@/features/trading/demo-book-prefs");
  return {
    ...actual,
    loadDemoBookPrefs: vi.fn(() => ({
      mode: "manual",
      maxOpenPositions: 10,
      defaultSizePctOfCash: 10,
    })),
  };
});

import { api } from "@/lib/api";
import { loadDemoBookPrefs } from "@/features/trading/demo-book-prefs";
import { proposeInstrumentSupervised } from "@/features/trading/propose-instrument-supervised";

describe("proposeInstrumentSupervised", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("blocks MANUAL book before hitting API", async () => {
    vi.mocked(loadDemoBookPrefs).mockReturnValue({
      mode: "manual",
      maxOpenPositions: 10,
      defaultSizePctOfCash: 10,
    } as ReturnType<typeof loadDemoBookPrefs>);

    await expect(
      proposeInstrumentSupervised({
        instrumentId: "i1",
        symbol: "SAN",
        accountId: "acc1",
      }),
    ).rejects.toThrow(/MANUAL/);

    expect(api.proposeRecommendation).not.toHaveBeenCalled();
  });
});
