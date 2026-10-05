/**
 * AUTO UI REFACTOR 1.0 — view model de "operación única".
 *
 * Invariantes: orden fijo de los 14 conceptos del modelo; `SELECTION` (TOP-N) ≠ `DECISION`
 * (no hay traza durable de decisión de cartera ⇒ `NOT_MEASURED`); `EXIT` es DERIVADA de
 * `SETTLEMENT`; `OPPORTUNITY` vive en el bloque `context`; una etapa sin traza es
 * `NOT_MEASURED` (nunca `0`) y los hechos se copian del paso durable con su medición.
 */

import { describe, expect, it } from "vitest";

import type { AutoMonitorCycleV1 } from "./auto-operational-monitor.js";
import {
  AUTO_OPERATION_STORY_ORDER,
  buildAutoOperationStory,
} from "./auto-operation-story.js";

function cycle(): AutoMonitorCycleV1 {
  return {
    cycleId: "cyc-1",
    instrumentId: "AAA",
    strategyVersion: "strat-3",
    direction: "long",
    closed: true,
    closedMeasurement: "COMPLETE",
    steps: [
      {
        id: "SIGNAL",
        state: "reached",
        at: "2026-09-29T20:00:00Z",
        measurement: "COMPLETE",
        facts: [{ key: "rank", value: 1, measurement: "COMPLETE" }],
        note: null,
      },
      {
        id: "TOP_N",
        state: "reached",
        at: "2026-09-29T20:00:01Z",
        measurement: "COMPLETE",
        facts: [{ key: "selected", value: true, measurement: "COMPLETE" }],
        note: null,
      },
      {
        id: "SETTLEMENT",
        state: "reached",
        at: "2026-10-01T15:00:00Z",
        measurement: "COMPLETE",
        facts: [{ key: "closedQty", value: 10, measurement: "COMPLETE" }],
        note: null,
      },
      {
        id: "FILL",
        state: "reached",
        at: "2026-09-30T09:00:00Z",
        measurement: "COMPLETE",
        facts: [
          { key: "qty", value: 10, measurement: "COMPLETE" },
          { key: "avgPrice", value: null, measurement: "UNKNOWN" },
        ],
        note: null,
      },
    ],
    result: { pnl: 250, closedAt: "2026-10-01T15:00:00Z" },
    notes: ["advisory"],
  };
}

describe("buildAutoOperationStory", () => {
  it("respeta el orden fijo de los catorce conceptos del modelo", () => {
    const story = buildAutoOperationStory({ cycle: cycle() });
    expect(story.stages.map((stage) => stage.id)).toEqual([
      ...AUTO_OPERATION_STORY_ORDER,
    ]);
    expect(story.stages).toHaveLength(14);
    // `index` es la posición real: la UI no re-ordena.
    expect(story.stages.map((stage) => stage.index)).toEqual([
      ...AUTO_OPERATION_STORY_ORDER.keys(),
    ]);
  });

  it("clasifica cada etapa por `kind` y `group`", () => {
    const story = buildAutoOperationStory({ cycle: cycle() });
    const byId = new Map(story.stages.map((stage) => [stage.id, stage]));

    expect(byId.get("OPPORTUNITY")?.kind).toBe("CONTEXT");
    expect(byId.get("OPPORTUNITY")?.group).toBe("CONTEXT");
    expect(byId.get("POSITION")?.kind).toBe("DERIVED");
    expect(byId.get("EXIT")?.kind).toBe("DERIVED");
    expect(byId.get("EXPLANATION")?.kind).toBe("EXPLANATION");
    expect(byId.get("SIGNAL")?.kind).toBe("FACT");
    expect(byId.get("EXIT")?.group).toBe("OPERATION");

    // Sólo OPPORTUNITY es contexto; el resto son hechos de la operación.
    const contextStages = story.stages.filter(
      (stage) => stage.group === "CONTEXT",
    );
    expect(contextStages.map((stage) => stage.id)).toEqual(["OPPORTUNITY"]);
  });

  it("copia los pasos durables con su estado y sus hechos", () => {
    const story = buildAutoOperationStory({ cycle: cycle() });
    const byId = new Map(story.stages.map((stage) => [stage.id, stage]));

    expect(byId.get("SIGNAL")?.state).toBe("REACHED");
    expect(byId.get("SIGNAL")?.at).toBe("2026-09-29T20:00:00Z");
    expect(byId.get("FILL")?.facts).toEqual([
      { label: "qty", value: 10, measurement: "COMPLETE" },
      { label: "avgPrice", value: null, measurement: "UNKNOWN" },
    ]);
  });

  it("separa SELECTION (TOP-N) de DECISION (no medible)", () => {
    const story = buildAutoOperationStory({ cycle: cycle() });
    const byId = new Map(story.stages.map((stage) => [stage.id, stage]));

    // Selección = TOP-N, con su hecho durable.
    expect(byId.get("SELECTION")?.sourceStepId).toBe("TOP_N");
    expect(byId.get("SELECTION")?.label).toBe("Selección · TOP-N");
    expect(byId.get("SELECTION")?.state).toBe("REACHED");

    // Decisión de cartera NO se iguala a TOP_N: no hay traza durable por ciclo.
    expect(byId.get("DECISION")?.sourceStepId).toBeNull();
    expect(byId.get("DECISION")?.state).toBe("NOT_MEASURED");
    expect(byId.get("DECISION")?.note).toContain(
      "no hay traza durable de decisión de cartera",
    );
  });

  it("pliega EXIT en SETTLEMENT sin duplicar el hecho financiero", () => {
    const story = buildAutoOperationStory({ cycle: cycle() });
    const byId = new Map(story.stages.map((stage) => [stage.id, stage]));

    expect(byId.get("SETTLEMENT")?.kind).toBe("FACT");
    expect(byId.get("SETTLEMENT")?.state).toBe("REACHED");
    // La intención de salida queda como NOTA de la liquidación (una sola fila REACHED).
    expect(byId.get("SETTLEMENT")?.note).toContain("liquidación");

    expect(byId.get("EXIT")?.kind).toBe("DERIVED");
    expect(byId.get("EXIT")?.sourceStepId).toBe("SETTLEMENT");
    // Se pliega: sin traza durable propia de salida no se pinta como evento independiente.
    expect(byId.get("EXIT")?.foldedInto).toBe("SETTLEMENT");
    // Y NO copia los hechos financieros de la liquidación.
    expect(byId.get("EXIT")?.facts).toEqual([]);
    expect(byId.get("EXIT")?.note).toContain("liquidación");
  });

  it("despliega EXIT como fila propia si existe una traza durable de salida", () => {
    const withExit = cycle();
    withExit.steps = [
      ...withExit.steps,
      {
        id: "EXIT",
        state: "reached",
        at: "2026-10-01T14:00:00Z",
        measurement: "COMPLETE",
        facts: [{ key: "reason", value: "STOP", measurement: "COMPLETE" }],
        note: null,
      },
    ];
    const story = buildAutoOperationStory({ cycle: withExit });
    const exit = story.stages.find((stage) => stage.id === "EXIT");

    expect(exit?.foldedInto).toBeNull();
    expect(exit?.facts).toEqual([
      { label: "reason", value: "STOP", measurement: "COMPLETE" },
    ]);
  });

  it("expone OPPORTUNITY y el resto del universo en el bloque context", () => {
    const story = buildAutoOperationStory({ cycle: cycle() });
    const context = new Map(story.context.map((item) => [item.id, item]));

    expect(context.get("INSTRUMENT")?.value).toBe("AAA");
    expect(context.get("INSTRUMENT")?.measurement).toBe("COMPLETE");
    expect(context.get("STRATEGY")?.value).toBe("strat-3");
    expect(context.get("DIRECTION")?.value).toBe("long");

    // El universo PIT / régimen / ranking NO se materializan por ciclo ⇒ NO MEDIDO.
    expect(context.get("PIT_UNIVERSE")?.measurement).toBe("UNKNOWN");
    expect(context.get("PIT_UNIVERSE")?.value).toBe("NO MEDIDO");
    expect(context.get("PIT_UNIVERSE")?.note).toContain("watch PIT");
    expect(context.get("REGIME")?.measurement).toBe("UNKNOWN");
    expect(context.get("RANKING")?.measurement).toBe("UNKNOWN");
  });

  it("una etapa sin traza es NOT_MEASURED y nunca un 0", () => {
    const story = buildAutoOperationStory({ cycle: cycle() });
    const byId = new Map(story.stages.map((stage) => [stage.id, stage]));

    // PROTECTION no viene en el ciclo ⇒ NO MEDIDO (no `reached`, no `0`).
    expect(byId.get("PROTECTION")?.state).toBe("NOT_MEASURED");
    expect(byId.get("PROTECTION")?.measurement).toBe("UNKNOWN");
    expect(byId.get("PROTECTION")?.facts).toEqual([]);

    // OPPORTUNITY es contextual: siempre NO MEDIDO con su nota declarada.
    expect(byId.get("OPPORTUNITY")?.state).toBe("NOT_MEASURED");
    expect(byId.get("OPPORTUNITY")?.note).toContain("watch PIT");

    // EXPLANATION sin input también se declara.
    expect(byId.get("EXPLANATION")?.state).toBe("NOT_MEASURED");
  });

  it("pliega la explicación OOS cuando se aporta", () => {
    const story = buildAutoOperationStory({
      cycle: cycle(),
      explanation: {
        verdict: "OOS_SUPPORTED",
        verdictReason: "positive_expectancy",
        evidenceQuality: "PRELIMINARY",
        expectancyR: 0.5,
        hitRate: 0.67,
        measuredCycles: 6,
        errorTotal: 0,
      },
    });
    const explanation = story.stages.find(
      (stage) => stage.id === "EXPLANATION",
    );
    expect(explanation?.state).toBe("REACHED");
    expect(
      explanation?.facts.find((fact) => fact.label === "veredicto")?.value,
    ).toBe("OOS_SUPPORTED");
    expect(
      explanation?.facts.find((fact) => fact.label === "R medio")?.value,
    ).toBe(0.5);
    // `0` medido es MEDIDO y viaja como `0` (no se confunde con un hueco).
    expect(explanation?.facts.find((fact) => fact.label === "errores")).toEqual(
      { label: "errores", value: 0, measurement: "COMPLETE" },
    );
  });

  it("expone la identidad de la explicación y declara NO MEDIDO lo no material", () => {
    const story = buildAutoOperationStory({
      cycle: cycle(),
      explanation: {
        verdict: "OOS_SUPPORTED",
        evidenceQuality: "PRELIMINARY",
        identity: {
          cycleId: "cyc-1",
          instrument: "AAA",
          strategyVersion: "strat-3",
          direction: "long",
          entryDay: "2026-09-29",
          timeframe: null,
          regime: null,
        },
      },
    });
    const explanation = story.stages.find(
      (stage) => stage.id === "EXPLANATION",
    );
    const byLabel = new Map(
      (explanation?.facts ?? []).map((fact) => [fact.label, fact]),
    );

    expect(byLabel.get("cycleId")).toEqual({
      label: "cycleId",
      value: "cyc-1",
      measurement: "COMPLETE",
    });
    expect(byLabel.get("estrategia")?.value).toBe("strat-3");
    expect(byLabel.get("día entrada")?.value).toBe("2026-09-29");
    // Ejes que el artefacto DÍA-D no materializa ⇒ NO MEDIDO (null + UNKNOWN), nunca inventados.
    expect(byLabel.get("timeframe")).toEqual({
      label: "timeframe",
      value: null,
      measurement: "UNKNOWN",
    });
    expect(byLabel.get("régimen")?.measurement).toBe("UNKNOWN");
    expect(explanation?.note).toContain("instrumento");
  });

  it("un ciclo ausente deja todas las trazas en NOT_MEASURED", () => {
    const story = buildAutoOperationStory({ cycle: null });
    expect(story.cycleId).toBeNull();
    expect(story.stages).toHaveLength(14);
    for (const stage of story.stages) {
      expect(stage.state).toBe("NOT_MEASURED");
      expect(stage.facts).toEqual([]);
    }
    // El contexto tampoco se inventa: todo NO MEDIDO salvo la declaración.
    for (const item of story.context) {
      expect(item.value).toBe("NO MEDIDO");
      expect(item.measurement).toBe("UNKNOWN");
    }
  });

  it("expone el resultado del ciclo sin re-derivarlo", () => {
    const story = buildAutoOperationStory({ cycle: cycle() });
    expect(story.result).toEqual({
      pnl: 250,
      closedAt: "2026-10-01T15:00:00Z",
      measurement: "COMPLETE",
    });
  });
});
