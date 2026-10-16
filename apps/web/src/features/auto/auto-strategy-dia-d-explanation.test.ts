/**
 * Explicación P3→P4 — invariantes del read-model puro.
 *
 * Lo que se vigila aquí:
 * - La evidencia DÍA-D es del **VALOR**: nunca se afirma que sea de la estrategia.
 * - La estrategia sólo se da por declarada por el ciclo con clave EXACTA + emparejamiento exacto.
 * - `UNKNOWN ≠ 0`: un contador ausente viaja `null`, jamás `0`.
 * - Sin promoción de capas (reexpedida del agregado) y `CONFIRMED` nunca emitido.
 * - Fail-closed: un fallo de lectura se declara «No disponible»; `loading` no declara ausencia.
 */

import { describe, expect, it } from "vitest";

import type { components } from "@/api/schema";
import type { DiaDCycleVerificationV1Dto } from "@bolsa/shared";
import { ABSENT_DATA_NOT_AVAILABLE } from "@/components/absent-data";
import type { AutoOperationStrategyViewV1 } from "@/features/auto/auto-operation-strategy";
import {
  AUTO_STRATEGY_EXPLANATION_SCOPE_VALUE_LABEL,
  buildAutoStrategyDiaDExplanation,
  autoStrategyExplanationLabel,
  type AutoStrategyDiaDExplanationInput,
} from "./auto-strategy-dia-d-explanation";

type DiaDFeedbackDto = components["schemas"]["DiaDFeedbackDto"];

function strategyView(
  overrides: Partial<AutoOperationStrategyViewV1> = {},
): AutoOperationStrategyViewV1 {
  return {
    symbol: "SAN.MC",
    instrumentId: "inst-1",
    strategyDefinitionId: "def-top1",
    strategyLabel: "SMA cross",
    rank: 1,
    indicators: ["RSI (14)", "SMA 50/200"],
    reasons: ["Estrellas 3/5"],
    match: "same",
    matchLabel: "Coincide con la estrategia del ciclo",
    declaredCyclePresetKey: "sma_crossover",
    declaredCycleStrategyVersion: "v-9",
    executedStrategyDefinitionId: "def-exec",
    executedStrategyLabel: "SMA cross",
    executedStrategyRank: 2,
    verifyTarget: "executed",
    verifyGapReason: null,
    verifyHref: "/backtests?instrumentId=inst-1&verify=1",
    gapReason: null,
    loading: false,
    ...overrides,
  };
}

function artifact(overrides: Partial<DiaDFeedbackDto> = {}): DiaDFeedbackDto {
  return {
    available: true,
    matrixBasis: "entryDay",
    readOnly: true,
    serving: "PRECOMPUTED_ARTIFACT",
    gate: { verdict: "READY", days: 4, episodes: 2, cycles: 32 },
    summary: {
      measuredValues: 2,
      mixed: 0,
      notMeasured: 0,
      oosSupported: 1,
      refuted: 0,
      values: 2,
      errors: { SOFTWARE: 0, OPERATIONAL: 0, DATA: 0, total: 0 },
    },
    values: [
      {
        symbol: "SAN.MC",
        verdict: "OOS_SUPPORTED",
        verdictReason: "positive_expectancy",
        evidenceQuality: "PRELIMINARY",
        expectancyR: 0.5,
        hitRate: 0.67,
        measuredCycles: 6,
        daysCovered: 4,
        windowDays: 6,
        errorTotal: 0,
        limits: {
          minCycles: 5,
          minHitRate: 0.5,
          supportedMinCycles: 20,
          strongMinCycles: 32,
        },
      },
    ],
    cycles: [
      {
        cycleId: "cyc-1",
        symbol: "SAN.MC",
        entryDay: "2026-09-29",
        exitDay: "2026-10-01",
        strategyVersion: "v-9",
        strategyPresetKey: "sma_crossover",
        realizedR: 1.2,
      },
    ],
    ...overrides,
  };
}

function input(
  overrides: Partial<AutoStrategyDiaDExplanationInput> = {},
): AutoStrategyDiaDExplanationInput {
  return {
    strategy: strategyView(),
    cycle: {
      cycleId: "cyc-1",
      strategyPresetKey: "sma_crossover",
      strategyVersion: "v-9",
    },
    accountId: "acc-1",
    artifact: artifact(),
    ...overrides,
  };
}

describe("buildAutoStrategyDiaDExplanation · la evidencia es del VALOR", () => {
  it("declara el alcance del valor y NO atribuye la evidencia a la estrategia", () => {
    const view = buildAutoStrategyDiaDExplanation(input());
    expect(view.valueScopeLabel).toBe(
      AUTO_STRATEGY_EXPLANATION_SCOPE_VALUE_LABEL,
    );
    expect(view.valueScopeLabel).toContain("no de la estrategia");
    expect(view.attributionNote).toContain("por valor");
    expect(view.attributionNote).toContain("NO es atribuible a una estrategia");
  });

  it("expone la fila EXACTA del ciclo como el único alcance atribuible", () => {
    const view = buildAutoStrategyDiaDExplanation(input());
    expect(view.cycleEvidence).toEqual({
      cycleId: "cyc-1",
      symbol: "SAN.MC",
      entryDay: "2026-09-29",
      exitDay: "2026-10-01",
      strategyVersion: "v-9",
      strategyPresetKey: "sma_crossover",
      realizedR: 1.2,
    });
  });

  it("sin la fila del ciclo, la evidencia exacta se declara ausente (no se inventa)", () => {
    const view = buildAutoStrategyDiaDExplanation(
      input({ cycle: { cycleId: "cyc-otro" } }),
    );
    expect(view.cycleEvidence).toBeNull();
  });
});

describe("buildAutoStrategyDiaDExplanation · la estrategia sólo se ata con identidad EXACTA", () => {
  it("afirma la identidad exacta sólo con clave + emparejamiento exacto", () => {
    const view = buildAutoStrategyDiaDExplanation(input());
    expect(view.cyclePresetKey).toBe("sma_crossover");
    expect(view.strategyIsDeclaredByCycle).toBe(true);
  });

  it("con la estrategia declarada DISTINTA al TOP, NO se afirma la atribución", () => {
    const view = buildAutoStrategyDiaDExplanation(
      input({ strategy: strategyView({ match: "differs" }) }),
    );
    expect(view.strategyIsDeclaredByCycle).toBe(false);
  });

  it("sin clave declarada por el ciclo, no se afirma nada", () => {
    const view = buildAutoStrategyDiaDExplanation(
      input({ cycle: { cycleId: "cyc-1" } }),
    );
    expect(view.cyclePresetKey).toBeNull();
    expect(view.strategyIsDeclaredByCycle).toBe(false);
  });

  it("una clave en blanco es un hueco, nunca una identidad", () => {
    const view = buildAutoStrategyDiaDExplanation(
      input({ cycle: { cycleId: "cyc-1", strategyPresetKey: "   " } }),
    );
    expect(view.cyclePresetKey).toBeNull();
    expect(view.strategyIsDeclaredByCycle).toBe(false);
  });
});

describe("buildAutoStrategyDiaDExplanation · capas sin promoción", () => {
  it("reexpide las cuatro capas y NUNCA emite la confirmación reservada", () => {
    const view = buildAutoStrategyDiaDExplanation(input());
    expect(view.evidence.verdict).toBe("NO_CONFIRMED");
    expect(view.evidence.layers.map((layer) => layer.id)).toEqual([
      "window",
      "reconciliation",
      "oos",
      "paper",
    ]);
    // PAPER es hueco estructural por contrato: no hay rama que lo mida.
    const paper = view.evidence.layers.find((layer) => layer.id === "paper");
    expect(paper?.state).toBe("gap");
    expect(view.evidence.summary).toContain("no confirma");
  });

  it("la ventana lista NO promociona: el veredicto global sigue NO CONFIRMADO", () => {
    const view = buildAutoStrategyDiaDExplanation(input());
    const window = view.evidence.layers.find((layer) => layer.id === "window");
    expect(window?.state).toBe("measured");
    expect(window?.verdictToken).toBe("READY");
    // La capa más fuerte medida se reporta, pero NO cierra el veredicto global.
    expect(view.evidence.maxLayerReached).toBe("oos");
    expect(view.evidence.verdict).toBe("NO_CONFIRMED");
    // Y la capa intermedia sigue declarada hueco: no hay promoción en cadena.
    const reconciliation = view.evidence.layers.find(
      (layer) => layer.id === "reconciliation",
    );
    expect(reconciliation?.state).toBe("gap");
  });

  it("la capa de reconciliación se declara hueco si no se aporta el sandbox", () => {
    const view = buildAutoStrategyDiaDExplanation(input());
    const reconciliation = view.evidence.layers.find(
      (layer) => layer.id === "reconciliation",
    );
    expect(reconciliation?.state).toBe("gap");
  });
});

describe("buildAutoStrategyDiaDExplanation · UNKNOWN != 0", () => {
  it("un contador ausente viaja null, jamás 0", () => {
    const view = buildAutoStrategyDiaDExplanation(
      input({
        artifact: artifact({
          values: [
            {
              symbol: "SAN.MC",
              verdict: "NOT_MEASURED",
              evidenceQuality: "NOT_MEASURED",
              measuredCycles: 0,
              daysCovered: 0,
              windowDays: 6,
              errorTotal: 0,
              limits: {
                minCycles: 5,
                minHitRate: 0.5,
                supportedMinCycles: 20,
                strongMinCycles: 32,
              },
            },
          ],
        }),
      }),
    );
    // `0` medido es MEDIDO y viaja como `0`; el hueco (campos ausentes) viaja `null`.
    expect(view.measuredCycles).toBe(0);
    expect(view.expectancyR).toBeNull();
    expect(view.hitRate).toBeNull();
  });

  it("con contadores OOS incompletos la capa se declara hueco (no se afirma el veredicto)", () => {
    const view = buildAutoStrategyDiaDExplanation(
      input({
        artifact: artifact({
          summary: {
            measuredValues: 1,
            mixed: 0,
            notMeasured: 1,
            oosSupported: 1,
            refuted: 0,
            values: 1,
          },
        }),
      }),
    );
    const oos = view.evidence.layers.find((layer) => layer.id === "oos");
    expect(oos?.state).toBe("gap");
  });

  it("el artefacto sin disponibilidad no aporta contadores (huecos, no ceros)", () => {
    const view = buildAutoStrategyDiaDExplanation(
      input({ artifact: artifact({ available: false }) }),
    );
    expect(view.measuredCycles).toBeNull();
    expect(view.expectancyR).toBeNull();
    expect(view.evidence.layers.every((layer) => layer.state === "gap")).toBe(
      true,
    );
  });
});

describe("buildAutoStrategyDiaDExplanation · suelos de muestra declarados", () => {
  it("copia los suelos del artefacto en vez de relajarlos", () => {
    const view = buildAutoStrategyDiaDExplanation(input());
    expect(view.sampleFloors).toEqual({
      minCycles: 5,
      minHitRate: 0.5,
      supportedMinCycles: 20,
      strongMinCycles: 32,
    });
  });

  it("sin límites publicados, los suelos son huecos declarados", () => {
    const view = buildAutoStrategyDiaDExplanation(
      input({
        artifact: artifact({
          values: [
            {
              symbol: "SAN.MC",
              verdict: "NOT_MEASURED",
              evidenceQuality: "NOT_MEASURED",
              measuredCycles: 0,
              daysCovered: 0,
              windowDays: 6,
              errorTotal: 0,
            },
          ],
        }),
      }),
    );
    expect(view.sampleFloors.minCycles).toBeNull();
    expect(view.sampleFloors.strongMinCycles).toBeNull();
  });
});

describe("buildAutoStrategyDiaDExplanation · verificación durable (tri-estado)", () => {
  const verification: DiaDCycleVerificationV1Dto = {
    id: "ver-1",
    cycleId: "cyc-1",
    accountId: "acc-1",
    instrumentId: "inst-1",
    symbol: "SAN.MC",
    diaD: "2026-09-29",
    endDate: "2026-10-01",
    mode: "auto",
    createdAt: "2026-10-01T15:00:00Z",
    strategyPresetKey: "sma_crossover",
    strategyVersion: "v-9",
    strategyDefinitionId: null,
    band: null,
    result: null,
    researchEvidenceId: null,
  };

  it("rotula «Verificación vinculada» sólo con el registro durable del ciclo", () => {
    const view = buildAutoStrategyDiaDExplanation(
      input({ verifications: [verification] }),
    );
    expect(view.verification.state).toBe("linked");
    expect(view.verification.stateLabel).toBe("Verificación vinculada");
    expect(view.verification.createdAt).toBe("2026-10-01T15:00:00Z");
    expect(view.verification.gapReason).toBeNull();
  });

  it("sin registro durable declara «Sin verificación» y su motivo", () => {
    const view = buildAutoStrategyDiaDExplanation(input({ verifications: [] }));
    expect(view.verification.state).toBe("not-verified");
    expect(view.verification.stateLabel).toBe("Sin verificación");
    expect(view.verification.gapReason).toContain("todavía no se ha guardado");
  });

  it("sin cycleId se declara «Sin dato todavía» (nunca un falso «sin verificación»)", () => {
    const view = buildAutoStrategyDiaDExplanation(
      input({ cycle: null, verifications: [] }),
    );
    expect(view.verification.state).toBe("unknown");
    expect(view.verification.stateLabel).toBe("Sin dato todavía");
  });

  it("un fallo de lectura NO se describe como ausencia (No disponible)", () => {
    const view = buildAutoStrategyDiaDExplanation(
      input({ verifications: [], verificationsError: true }),
    );
    expect(view.verification.state).toBe("unknown");
    expect(view.verification.stateLabel).toBe(ABSENT_DATA_NOT_AVAILABLE);
    expect(view.verification.gapReason).toContain(ABSENT_DATA_NOT_AVAILABLE);
  });
});

describe("buildAutoStrategyDiaDExplanation · sesión LAB (local, no durable)", () => {
  it("declara la sesión LOCAL y su límite sólo con identidad COMPLETA y EXACTA", () => {
    const view = buildAutoStrategyDiaDExplanation(
      input({
        labSession: {
          instrumentId: "inst-1",
          accountId: "acc-1",
          strategyPresetKey: "sma_crossover",
          diaD: "2026-09-29",
          endDate: "2026-10-01",
          mode: "auto",
        },
      }),
    );
    expect(view.lab.active).toBe(true);
    expect(view.lab.label).toContain("2026-09-29");
    expect(view.lab.note).toContain("no es evidencia durable");
  });

  it("una sesión de OTRA estrategia no explica esta operación", () => {
    const view = buildAutoStrategyDiaDExplanation(
      input({
        labSession: {
          instrumentId: "inst-1",
          accountId: "acc-1",
          strategyPresetKey: "otra_estrategia",
          diaD: "2026-09-29",
        },
      }),
    );
    expect(view.lab.active).toBe(false);
    expect(view.lab.label).toContain("no vinculada");
  });

  it("el MISMO preset en OTRO instrumento no explica esta operación", () => {
    const view = buildAutoStrategyDiaDExplanation(
      input({
        labSession: {
          instrumentId: "inst-OTRO",
          accountId: "acc-1",
          strategyPresetKey: "sma_crossover",
          diaD: "2026-09-29",
        },
      }),
    );
    expect(view.lab.active).toBe(false);
    expect(view.lab.label).toContain("no vinculada");
  });

  it("la misma estrategia e instrumento en OTRA cuenta no explica esta operación", () => {
    const view = buildAutoStrategyDiaDExplanation(
      input({
        labSession: {
          instrumentId: "inst-1",
          accountId: "acc-OTRA",
          strategyPresetKey: "sma_crossover",
          diaD: "2026-09-29",
        },
      }),
    );
    expect(view.lab.active).toBe(false);
    expect(view.lab.label).toContain("no vinculada");
  });

  it("sin identidad esperada (ciclo sin clave) NO se atribuye ninguna sesión", () => {
    const view = buildAutoStrategyDiaDExplanation(
      input({
        cycle: { cycleId: "cyc-1" },
        labSession: {
          instrumentId: "inst-1",
          accountId: "acc-1",
          strategyPresetKey: "sma_crossover",
          diaD: "2026-09-29",
        },
      }),
    );
    expect(view.lab.active).toBe(false);
    expect(view.lab.label).toContain("no vinculada");
  });

  it("una sesión sin cuenta NO se atribuye (fail-closed), aunque el resto casa", () => {
    const view = buildAutoStrategyDiaDExplanation(
      input({
        labSession: {
          instrumentId: "inst-1",
          strategyPresetKey: "sma_crossover",
          diaD: "2026-09-29",
        },
      }),
    );
    expect(view.lab.active).toBe(false);
    expect(view.lab.label).toContain("no vinculada");
  });

  it("sin sesión, el hueco se declara", () => {
    const view = buildAutoStrategyDiaDExplanation(input());
    expect(view.lab.active).toBe(false);
    expect(view.lab.diaD).toBeNull();
    expect(view.lab.label).toContain("Sin sesión LAB");
  });
});

describe("buildAutoStrategyDiaDExplanation · fail-closed", () => {
  it("un fallo de lectura del artefacto se declara «No disponible»", () => {
    const view = buildAutoStrategyDiaDExplanation(
      input({ artifact: null, artifactError: true }),
    );
    expect(view.gapReason).toContain(ABSENT_DATA_NOT_AVAILABLE);
  });

  it("en carga, el hueco es TRANSITORIO (no se declara ausencia)", () => {
    const view = buildAutoStrategyDiaDExplanation(
      input({ artifact: null, loading: true }),
    );
    expect(view.gapReason).toBeNull();
    expect(view.loading).toBe(true);
  });

  it("sin instrumento resuelto se declara el hueco", () => {
    const view = buildAutoStrategyDiaDExplanation(
      input({ strategy: strategyView({ instrumentId: null }) }),
    );
    expect(view.gapReason).toContain("no se pudo resolver el instrumento");
  });

  it("sin evidencia publicada para el valor, se declara el hueco", () => {
    const view = buildAutoStrategyDiaDExplanation(
      input({ artifact: artifact({ available: false }) }),
    );
    expect(view.gapReason).toContain("no hay evidencia DÍA-D publicada");
  });

  it("si el valor no figura en la ventana, se declara el hueco", () => {
    const view = buildAutoStrategyDiaDExplanation(
      input({ artifact: artifact({ values: [] }) }),
    );
    expect(view.gapReason).toContain("no figura en la evidencia DÍA-D");
  });

  it("si la estrategia ejecutada no se resuelve, NO se cae al #1: se declara", () => {
    const view = buildAutoStrategyDiaDExplanation(
      input({
        strategy: strategyView({
          executedStrategyDefinitionId: null,
          executedStrategyLabel: null,
          executedStrategyRank: null,
          verifyTarget: null,
          verifyHref: null,
          verifyGapReason:
            "Sin dato todavía: la estrategia ejecutada del ciclo no está entre las estrategias del valor (Finalistas).",
        }),
      }),
    );
    expect(view.executedStrategyDefinitionId).toBeNull();
    expect(view.gapReason).toContain("no está entre las estrategias del valor");
    expect(autoStrategyExplanationLabel(view)).toBe("Sin dato todavía");
  });
});
