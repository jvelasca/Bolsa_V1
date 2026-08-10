/**
 * Tests — bloqueo handoff Lab→Coach si falla guardar Mejor.
 */

import { describe, expect, it } from "vitest";
import { resolveLabReanalyzeGate } from "@/features/backtests/lab-coach-handoff";

describe("resolveLabReanalyzeGate", () => {
  it("blocks when any save failed (even if others ok)", () => {
    const gate = resolveLabReanalyzeGate({
      improvedSaved: 2,
      saveFailures: [{ rank: 2, error: "API 500" }],
      carriedCount: 0,
    });
    expect(gate.allow).toBe(false);
    expect(gate.message).toMatch(/No se puede pasar al Coach/);
    expect(gate.message).toMatch(/#2/);
  });

  it("allows when all improved saved", () => {
    const gate = resolveLabReanalyzeGate({
      improvedSaved: 2,
      saveFailures: [],
      carriedCount: 1,
    });
    expect(gate.allow).toBe(true);
    expect(gate.message).toBeNull();
  });

  it("blocks empty handoff", () => {
    const gate = resolveLabReanalyzeGate({
      improvedSaved: 0,
      saveFailures: [],
      carriedCount: 0,
    });
    expect(gate.allow).toBe(false);
    expect(gate.message).toMatch(/Nada que llevar/);
  });

  it("allows carry-only", () => {
    const gate = resolveLabReanalyzeGate({
      improvedSaved: 0,
      saveFailures: [],
      carriedCount: 2,
    });
    expect(gate.allow).toBe(true);
  });
});
