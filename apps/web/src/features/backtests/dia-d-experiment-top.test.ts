/**
 * R6 — el experimento F-D deja de vivir solo en `localStorage`.
 *
 * Fija las dos mitades del contrato de durabilidad:
 *
 * * lo que se guarda refleja el sello del **servidor** (el cliente no inventa
 *   `savedAt`);
 * * lo que llega del servidor **hidrata** la caché —también en un navegador
 *   nuevo— y nunca retrocede a un registro más viejo.
 */

import type { InstrumentStrategyTopSlotV1 } from "@bolsa/shared";
import { beforeEach, describe, expect, it } from "vitest";
import {
  DIA_D_EXPERIMENT_TOP_KEY,
  clearDiaDExperimentTop,
  getDiaDExperimentTop,
  hydrateDiaDExperimentTop,
  saveDiaDExperimentTop,
} from "@/features/backtests/dia-d-experiment-top";

const SLOT: InstrumentStrategyTopSlotV1 = {
  rank: 1,
  label: "SMA 20/50",
  stars: 4,
  score: 1.2,
  source: "optimized",
  runId: "run-1",
};

function serverRow(overrides: Record<string, unknown> = {}) {
  return {
    id: "ev-1",
    instrumentId: "inst-1",
    timeframe: "1d",
    asOfDiaD: "2026-09-15",
    savedAt: "2026-11-16T10:00:00+00:00",
    level: "C",
    slots: [SLOT],
    coachHeadline: "Servidor",
    ...overrides,
  };
}

beforeEach(() => {
  localStorage.clear();
});

describe("saveDiaDExperimentTop", () => {
  it("mirrors the server stamp instead of inventing one", () => {
    const record = saveDiaDExperimentTop({
      instrumentId: "inst-1",
      timeframe: "1d",
      asOfDiaD: "2026-09-15",
      slots: [SLOT],
      savedAt: "2026-11-16T10:00:00+00:00",
    });

    expect(record.savedAt).toBe("2026-11-16T10:00:00+00:00");
    expect(getDiaDExperimentTop("inst-1", "1d", "2026-09-15")?.savedAt).toBe(
      "2026-11-16T10:00:00+00:00",
    );
  });

  it("keeps a client stamp when there is no server record yet", () => {
    const record = saveDiaDExperimentTop({
      instrumentId: "inst-1",
      timeframe: "1d",
      asOfDiaD: "2026-09-15",
      slots: [SLOT],
    });

    expect(record.savedAt).toMatch(/^\d{4}-\d{2}-\d{2}T/);
  });
});

describe("hydrateDiaDExperimentTop", () => {
  it("makes a server-only experiment readable (fresh browser)", () => {
    expect(getDiaDExperimentTop("inst-1", "1d", "2026-09-15")).toBeNull();

    hydrateDiaDExperimentTop(serverRow());

    const record = getDiaDExperimentTop("inst-1", "1d", "2026-09-15");
    expect(record?.slots).toHaveLength(1);
    expect(record?.coachHeadline).toBe("Servidor");
    expect(record?.evidenceId).toBe("ev-1");
    expect(localStorage.getItem(DIA_D_EXPERIMENT_TOP_KEY)).toContain('"ev-1"');
  });

  it("replaces an older local record with the server one", () => {
    saveDiaDExperimentTop({
      instrumentId: "inst-1",
      timeframe: "1d",
      asOfDiaD: "2026-09-15",
      slots: [SLOT],
      coachHeadline: "local viejo",
      savedAt: "2026-11-01T09:00:00+00:00",
    });

    hydrateDiaDExperimentTop(serverRow());

    expect(
      getDiaDExperimentTop("inst-1", "1d", "2026-09-15")?.coachHeadline,
    ).toBe("Servidor");
  });

  it("never overwrites a newer local record with an older server one", () => {
    saveDiaDExperimentTop({
      instrumentId: "inst-1",
      timeframe: "1d",
      asOfDiaD: "2026-09-15",
      slots: [SLOT],
      coachHeadline: "local nuevo",
      savedAt: "2026-11-20T09:00:00+00:00",
    });

    hydrateDiaDExperimentTop(serverRow());

    expect(
      getDiaDExperimentTop("inst-1", "1d", "2026-09-15")?.coachHeadline,
    ).toBe("local nuevo");
  });

  it("keeps the gap declared for a day without experiment", () => {
    hydrateDiaDExperimentTop(serverRow());

    expect(getDiaDExperimentTop("inst-1", "1d", "2026-09-10")).toBeNull();
    clearDiaDExperimentTop("inst-1", "1d", "2026-09-15");
  });
});
