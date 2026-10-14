/**
 * P4 — payload del enlace «verificación DÍA-D ↔ ciclo AUTO» (puro).
 *
 * Honestidad: sin `cycleId` NO se fabrica el enlace (`null`). Con él se copia la identidad
 * EXACTA declarada por el ciclo y la evidencia ya calculada, sin recalcular nada.
 */

import { describe, expect, it } from "vitest";
import { buildDiaDCycleVerificationPayload } from "@/features/auto-monitor/dia-d-cycle-verification-link";

const evidence = {
  band: "favorable",
  confidence: "HIGH",
  metrics: {
    mode: "auto",
    returnPct: 1.2,
    maxDrawdownPct: -0.5,
    tradeCount: 3,
    finalEquity: 10120,
    autoReturnPct: 1.2,
    returnDeltaVsAutoPct: 0,
    accepted: 0,
    rejected: 0,
  },
} as const;

describe("buildDiaDCycleVerificationPayload", () => {
  it("enlaza con la identidad EXACTA del ciclo y la evidencia ya calculada", () => {
    const payload = buildDiaDCycleVerificationPayload({
      cycleId: "cyc-1",
      instrumentId: "uuid-1",
      symbol: "AAA",
      diaD: "2026-09-30",
      endDate: "2026-10-14",
      mode: "auto",
      strategyDefinitionId: "def-1",
      strategyPresetKey: "sma_crossover",
      strategyVersion: "sv-1",
      evidence,
      researchEvidenceId: "ev-1",
    });

    expect(payload).toEqual({
      cycleId: "cyc-1",
      instrumentId: "uuid-1",
      symbol: "AAA",
      diaD: "2026-09-30",
      endDate: "2026-10-14",
      mode: "auto",
      strategyPresetKey: "sma_crossover",
      strategyVersion: "sv-1",
      strategyDefinitionId: "def-1",
      band: "favorable",
      result: {
        band: "favorable",
        confidence: "HIGH",
        metrics: evidence.metrics,
      },
      researchEvidenceId: "ev-1",
    });
  });

  it("sin `cycleId` (o en blanco) NO fabrica el enlace", () => {
    const base = {
      instrumentId: "uuid-1",
      symbol: "AAA",
      diaD: "2026-09-30",
      endDate: "2026-10-14",
      mode: "auto",
      strategyDefinitionId: "def-1",
      evidence,
    } as const;

    expect(
      buildDiaDCycleVerificationPayload({ ...base, cycleId: null }),
    ).toBeNull();
    expect(
      buildDiaDCycleVerificationPayload({ ...base, cycleId: "   " }),
    ).toBeNull();
  });

  it("copia el hueco declarado (null, no cadena vacía) de la identidad del ciclo", () => {
    const payload = buildDiaDCycleVerificationPayload({
      cycleId: "cyc-1",
      instrumentId: "uuid-1",
      symbol: "AAA",
      diaD: "2026-09-30",
      endDate: "2026-10-14",
      mode: "auto",
      strategyDefinitionId: "def-1",
      evidence,
    });

    expect(payload?.strategyPresetKey).toBeNull();
    expect(payload?.strategyVersion).toBeNull();
    expect(payload?.researchEvidenceId).toBeNull();
  });
});
