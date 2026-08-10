/**
 * Tests — Lista AUTO campaña (avance, pausa, stop, labels, tandas).
 */

import { describe, expect, it } from "vitest";
import {
  LIST_AUTO_BATCH_SIZE,
  LIST_AUTO_HARD_MAX,
  LIST_AUTO_MAX_INSTRUMENTS,
  advanceListAutoAfterSettle,
  confirmListAutoOverCap,
  createListAutoCampaign,
  filterListAutoIdsWithoutFinalists,
  isListAutoComplete,
  listAutoBatchCount,
  listAutoBatchProgressLabel,
  listAutoDoneStatus,
  listAutoOverCapWarning,
  listAutoPausedStatus,
  listAutoPlayTitle,
  listAutoProgressLabel,
  listAutoUniverseHint,
  listModeWizardTitle,
  nextListAutoIndex,
  pauseListAutoCampaign,
  resumeListAutoCampaign,
  shouldStartListAuto,
  sliceListAutoInstrumentIds,
  stopListAutoCampaign,
} from "@/features/backtests/backtest-list-auto";

describe("sliceListAutoInstrumentIds", () => {
  it("keeps full list within hard max (no longer truncates at 40)", () => {
    const ids = Array.from({ length: 50 }, (_, i) => `id-${i}`);
    expect(sliceListAutoInstrumentIds(ids)).toHaveLength(50);
    expect(sliceListAutoInstrumentIds(ids, 5)).toHaveLength(5);
  });

  it("applies hard max", () => {
    const ids = Array.from(
      { length: LIST_AUTO_HARD_MAX + 10 },
      (_, i) => `id-${i}`,
    );
    expect(sliceListAutoInstrumentIds(ids)).toHaveLength(LIST_AUTO_HARD_MAX);
  });
});

describe("listAutoBatchCount / progress", () => {
  it("computes tandas", () => {
    expect(listAutoBatchCount(35)).toBe(1);
    expect(listAutoBatchCount(40)).toBe(1);
    expect(listAutoBatchCount(41)).toBe(2);
    expect(listAutoBatchCount(100)).toBe(3);
    expect(LIST_AUTO_MAX_INSTRUMENTS).toBe(LIST_AUTO_BATCH_SIZE);
  });

  it("labels tanda only when over one batch", () => {
    expect(listAutoBatchProgressLabel({ index: 0, total: 35 })).toBeNull();
    expect(listAutoBatchProgressLabel({ index: 0, total: 50 })).toBe(
      "Tanda 1/2",
    );
    expect(listAutoBatchProgressLabel({ index: 40, total: 50 })).toBe(
      "Tanda 2/2",
    );
  });
});

describe("confirmListAutoOverCap", () => {
  it("skips dialog when under batch size", () => {
    let called = false;
    expect(
      confirmListAutoOverCap(10, {
        confirmFn: () => {
          called = true;
          return false;
        },
      }),
    ).toBe(true);
    expect(called).toBe(false);
  });

  it("asks and respects cancel when over batch", () => {
    expect(confirmListAutoOverCap(50, { confirmFn: () => false })).toBe(false);
    expect(confirmListAutoOverCap(50, { confirmFn: () => true })).toBe(true);
  });

  it("skipConfirm bypasses dialog for N ≤ 200", () => {
    let called = false;
    expect(
      confirmListAutoOverCap(80, {
        skipConfirm: true,
        confirmFn: () => {
          called = true;
          return false;
        },
      }),
    ).toBe(true);
    expect(called).toBe(false);
  });

  it("always confirms when N > 200 even with skipConfirm", () => {
    let called = false;
    expect(
      confirmListAutoOverCap(250, {
        skipConfirm: true,
        confirmFn: () => {
          called = true;
          return true;
        },
      }),
    ).toBe(true);
    expect(called).toBe(true);
  });

  it("hard max confirm mentions safety cap", () => {
    const msg = confirmListAutoOverCap(600, {
      confirmFn: (m) => {
        expect(m).toMatch(/tope de seguridad/);
        expect(m).toMatch(/500/);
        return false;
      },
    });
    expect(msg).toBe(false);
  });
});

describe("listAutoOverCapWarning", () => {
  it("returns null under batch and message with tandas over batch", () => {
    expect(listAutoOverCapWarning(35)).toBeNull();
    expect(listAutoOverCapWarning(500)).toMatch(/500/);
    expect(listAutoOverCapWarning(500)).toMatch(/tandas/i);
    expect(listAutoOverCapWarning(500)).not.toMatch(/primeros/);
  });
});

describe("filterListAutoIdsWithoutFinalists", () => {
  it("keeps ids without slots and drops those with TOP", async () => {
    const ids = await filterListAutoIdsWithoutFinalists(
      ["a", "b", "c"],
      async (id) => {
        if (id === "b") return { data: { slots: [{ rank: 1 }] } };
        return { data: { slots: [] } };
      },
    );
    expect(ids).toEqual(["a", "c"]);
  });
});

describe("createListAutoCampaign / advance", () => {
  it("creates full queue (50) and advances until complete", () => {
    const ids = Array.from({ length: 50 }, (_, i) => `id-${i}`);
    const c = createListAutoCampaign({
      listId: "L1",
      instrumentIds: ids,
    });
    expect(c.instrumentIds).toHaveLength(50);
    expect(c.paused).toBe(false);
    expect(isListAutoComplete(c)).toBe(false);
    expect(advanceListAutoAfterSettle(c)).toBe("next");
    expect(c.index).toBe(1);
  });

  it("creates capped queue and advances until complete", () => {
    const c = createListAutoCampaign({
      listId: "L1",
      instrumentIds: ["a", "b", "c"],
    });
    expect(c.instrumentIds).toEqual(["a", "b", "c"]);
    expect(c.paused).toBe(false);
    expect(isListAutoComplete(c)).toBe(false);
    expect(advanceListAutoAfterSettle(c)).toBe("next");
    expect(c.index).toBe(1);
    expect(advanceListAutoAfterSettle(c)).toBe("next");
    expect(c.index).toBe(2);
    expect(advanceListAutoAfterSettle(c)).toBe("done");
    expect(isListAutoComplete(c)).toBe(true);
  });

  it("pause defers next start; resume clears flag", () => {
    const c = createListAutoCampaign({
      listId: "L1",
      instrumentIds: ["a", "b", "c"],
    });
    pauseListAutoCampaign(c);
    expect(advanceListAutoAfterSettle(c)).toBe("paused");
    expect(c.index).toBe(1);
    expect(c.paused).toBe(true);
    resumeListAutoCampaign(c);
    expect(c.paused).toBe(false);
    expect(advanceListAutoAfterSettle(c)).toBe("next");
    expect(c.index).toBe(2);
  });

  it("stops when aborted", () => {
    const c = createListAutoCampaign({
      listId: "L1",
      instrumentIds: ["a", "b"],
    });
    stopListAutoCampaign(c);
    expect(advanceListAutoAfterSettle(c)).toBe("aborted");
    expect(nextListAutoIndex(c)).toBeNull();
  });
});

describe("shouldStartListAuto", () => {
  it("requires list mode + full cycle + list with instruments", () => {
    expect(
      shouldStartListAuto({
        universeMode: "list",
        fullCycleOnPlay: true,
        listId: "L1",
        instrumentCount: 3,
      }),
    ).toBe(true);
    expect(
      shouldStartListAuto({
        universeMode: "single",
        fullCycleOnPlay: true,
        listId: "L1",
        instrumentCount: 3,
      }),
    ).toBe(false);
    expect(
      shouldStartListAuto({
        universeMode: "list",
        fullCycleOnPlay: false,
        listId: "L1",
        instrumentCount: 3,
      }),
    ).toBe(false);
  });
});

describe("labels", () => {
  it("formats progress and play title", () => {
    expect(listAutoProgressLabel({ index: 0, total: 35, symbol: "SAN" })).toBe(
      "Lista AUTO 1/35 · SAN",
    );
    expect(listAutoDoneStatus(2)).toMatch(/Lista AUTO ✓ 2/);
    expect(
      listAutoPausedStatus({ index: 2, total: 35, symbol: "GRF" }),
    ).toMatch(/pausa/i);
    expect(
      listAutoPlayTitle({ fullCycleOnPlay: true, listMode: true }),
    ).toMatch(/lista AUTO/i);
    expect(
      listAutoPlayTitle({ fullCycleOnPlay: true, listMode: true }),
    ).toMatch(/tandas/i);
    expect(
      listAutoPlayTitle({ fullCycleOnPlay: true, listMode: false }),
    ).toMatch(/ciclo completo/i);
  });

  it("list auto copy does not ask to pick a strategy", () => {
    expect(listAutoUniverseHint()).toMatch(/No hace falta seleccionar/i);
    expect(listAutoUniverseHint()).toMatch(/Pausa|frescura/i);
    expect(listAutoUniverseHint()).toMatch(/mandato|CORE-R/i);
    expect(listModeWizardTitle(true)).toMatch(/sin elegir estrategia/i);
    expect(listModeWizardTitle(false)).toMatch(/ciclo completo/i);
  });
});
