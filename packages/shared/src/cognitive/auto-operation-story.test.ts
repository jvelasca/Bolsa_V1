/**
 * AUTO UI REFACTOR 1.0 — view model de "operación única".
 *
 * Invariantes: orden fijo de 13 etapas; una etapa sin traza es `NOT_MEASURED` (nunca `0`);
 * los hechos se copian del paso durable con su medición; la explicación OOS se pliega sólo si
 * se aporta.
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
  it("respeta el orden fijo de las 13 etapas", () => {
    const story = buildAutoOperationStory({ cycle: cycle() });
    expect(story.stages.map((stage) => stage.id)).toEqual([
      ...AUTO_OPERATION_STORY_ORDER,
    ]);
  });

  it("copia los pasos durables con su estado y sus hechos", () => {
    const story = buildAutoOperationStory({ cycle: cycle() });
    const byId = new Map(story.stages.map((stage) => [stage.id, stage]));

    expect(byId.get("SIGNAL")?.state).toBe("REACHED");
    expect(byId.get("SIGNAL")?.at).toBe("2026-09-29T20:00:00Z");
    expect(byId.get("DECISION")?.sourceStepId).toBe("TOP_N");
    expect(byId.get("DECISION")?.state).toBe("REACHED");
    expect(byId.get("FILL")?.facts).toEqual([
      { label: "qty", value: "10", measurement: "COMPLETE" },
      { label: "avgPrice", value: "NO MEDIDO", measurement: "UNKNOWN" },
    ]);
  });

  it("una etapa sin traza es NOT_MEASURED y nunca un 0", () => {
    const story = buildAutoOperationStory({ cycle: cycle() });
    const byId = new Map(story.stages.map((stage) => [stage.id, stage]));

    // PROTECTION no viene en el ciclo ⇒ NO MEDIDO (no `reached`, no `0`).
    expect(byId.get("PROTECTION")?.state).toBe("NOT_MEASURED");
    expect(byId.get("PROTECTION")?.measurement).toBe("UNKNOWN");

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
    ).toBe("0.5");
  });

  it("un ciclo ausente deja todas las trazas en NOT_MEASURED", () => {
    const story = buildAutoOperationStory({ cycle: null });
    expect(story.cycleId).toBeNull();
    expect(story.stages).toHaveLength(AUTO_OPERATION_STORY_ORDER.length);
    for (const stage of story.stages) {
      expect(stage.state).toBe("NOT_MEASURED");
      expect(stage.facts).toEqual([]);
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
