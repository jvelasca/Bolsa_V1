import { describe, expect, it } from "vitest";
import type { MesaCandidateRowV1 } from "./mesa-hoy-model.js";
import type { DecisionJournalStudyViewV1 } from "./decision-journal-study.js";
import {
  projectMesaWhatIf,
  scoreMesaCandidateOperable,
  sortMesaCandidatesOperable,
} from "./mesa-operable-ranking.js";

function study(
  partial: Partial<DecisionJournalStudyViewV1> = {},
): DecisionJournalStudyViewV1 {
  return {
    sessionId: "s1",
    accountId: "a",
    instrumentId: "i1",
    symbol: "AAPL",
    name: "Apple",
    studiedAt: "2026-08-26T10:00:00Z",
    status: "active",
    opinion: "bullish",
    strength: 8,
    vigencia: "valid",
    hasOperationalPlan: true,
    entry: 100,
    stop: 95,
    target1: 110,
    target2: null,
    expectedRR: 2,
    riskAmount: 500,
    tradePlanStatus: "TRIGGERED",
    invalidation: [],
    ...partial,
  } as DecisionJournalStudyViewV1;
}

function row(
  partial: Partial<MesaCandidateRowV1> & Pick<MesaCandidateRowV1, "symbol">,
): MesaCandidateRowV1 {
  return {
    status: "TRIGGERED",
    statusLabel: "Listo",
    gate: "PASS",
    instrumentId: "i1",
    study: study({ symbol: partial.symbol }),
    ...partial,
  };
}

describe("scoreMesaCandidateOperable", () => {
  it("TRIGGERED + plan → operable when entries open", () => {
    const score = scoreMesaCandidateOperable(row({ symbol: "AAPL" }), false);
    expect(score.operable).toBe(true);
    expect(score.blockReasons).toEqual([]);
    expect(score.symbol).toBe("AAPL");
    expect(score.qualityScore).toBe(8);
  });

  it("collects blockReasons: entries blocked, status, plan, veto", () => {
    const blocked = scoreMesaCandidateOperable(
      row({
        symbol: "MSFT",
        status: "BLOCKED",
        statusLabel: "Bloqueado",
        gate: "VETO",
        study: study({ hasOperationalPlan: false, strength: 5 }),
      }),
      true,
    );
    expect(blocked.operable).toBe(false);
    expect(blocked.blockReasons).toEqual([
      "Entradas bloqueadas",
      "Gate bloqueado",
      "Sin plan operativo",
      "Veto de apertura",
    ]);
  });

  it("EXPIRED → Plan caducado, not operable", () => {
    const score = scoreMesaCandidateOperable(
      row({ symbol: "TSLA", status: "EXPIRED", statusLabel: "Caducado" }),
      false,
    );
    expect(score.operable).toBe(false);
    expect(score.blockReasons).toContain("Plan caducado");
  });

  it("ARMED with plan is not operable (only TRIGGERED)", () => {
    const score = scoreMesaCandidateOperable(
      row({ symbol: "NVDA", status: "ARMED", statusLabel: "Armado" }),
      false,
    );
    expect(score.operable).toBe(false);
    expect(score.blockReasons).toEqual([]);
  });

  it("operationalScore favors TRIGGERED over ARMED", () => {
    const triggered = scoreMesaCandidateOperable(
      row({ symbol: "A", status: "TRIGGERED", statusLabel: "Listo" }),
      false,
    );
    const armed = scoreMesaCandidateOperable(
      row({ symbol: "B", status: "ARMED", statusLabel: "Armado" }),
      false,
    );
    expect(triggered.operationalScore).toBeGreaterThan(armed.operationalScore);
  });

  it("entriesBlocked penalizes operationalScore", () => {
    const open = scoreMesaCandidateOperable(row({ symbol: "AAPL" }), false);
    const blocked = scoreMesaCandidateOperable(row({ symbol: "AAPL" }), true);
    expect(blocked.operationalScore).toBe(open.operationalScore - 50);
    expect(blocked.operable).toBe(false);
  });
});

describe("sortMesaCandidatesOperable", () => {
  it("operable rows first, then by operationalScore desc", () => {
    const rows = [
      row({ symbol: "LOW", status: "WATCH", statusLabel: "Vigilar" }),
      row({ symbol: "OP1", status: "TRIGGERED", statusLabel: "Listo" }),
      row({
        symbol: "OP2",
        status: "TRIGGERED",
        statusLabel: "Listo",
        study: study({ strength: 9, expectedRR: 3 }),
      }),
      row({ symbol: "ARM", status: "ARMED", statusLabel: "Armado" }),
    ];
    const sorted = sortMesaCandidatesOperable(rows, false);
    expect(sorted.map((r) => r.symbol)).toEqual(["OP2", "OP1", "ARM", "LOW"]);
    expect(sorted[0]?.operableScore.operable).toBe(true);
    expect(sorted[1]?.operableScore.operable).toBe(true);
    expect(sorted[2]?.operableScore.operable).toBe(false);
  });

  it("preserves row fields and attaches operableScore", () => {
    const input = row({ symbol: "X", gate: "PASS" });
    const [out] = sortMesaCandidatesOperable([input], false);
    expect(out?.symbol).toBe("X");
    expect(out?.gate).toBe("PASS");
    expect(out?.operableScore.symbol).toBe("X");
  });
});

describe("projectMesaWhatIf", () => {
  it("sums portfolio and candidate risk R", () => {
    const p = projectMesaWhatIf({
      symbol: "AAPL",
      portfolioRiskR: 1.5,
      candidateRiskR: 0.75,
    });
    expect(p.currentRiskR).toBe(1.5);
    expect(p.projectedRiskR).toBe(2.25);
    expect(p.riskDeltaR).toBe(0.75);
  });

  it("uses candidateRiskR alone when portfolio unknown", () => {
    const p = projectMesaWhatIf({
      symbol: "MSFT",
      candidateRiskR: 1.2,
    });
    expect(p.currentRiskR).toBeNull();
    expect(p.projectedRiskR).toBe(1.2);
    expect(p.riskDeltaR).toBe(1.2);
  });

  it("computes exposure from equity, cash, notional", () => {
    const p = projectMesaWhatIf({
      symbol: "AAPL",
      equity: 100_000,
      cash: 40_000,
      candidateNotional: 10_000,
    });
    expect(p.currentExposurePct).toBe(60);
    expect(p.projectedExposurePct).toBe(70);
    expect(p.warnings).toEqual([]);
  });

  it("warns on high exposure and aggregated risk", () => {
    const exposure = projectMesaWhatIf({
      symbol: "A",
      equity: 50_000,
      cash: 5_000,
      candidateNotional: 50_000,
    });
    expect(exposure.warnings).toContain("Exposición proyectada > 100%");

    const risk = projectMesaWhatIf({
      symbol: "B",
      portfolioRiskR: 4,
      candidateRiskR: 2,
    });
    expect(risk.warnings).toContain("Riesgo agregado elevado (>5R)");
  });

  it("returns nulls when inputs insufficient", () => {
    const p = projectMesaWhatIf({ symbol: "X" });
    expect(p.currentRiskR).toBeNull();
    expect(p.projectedRiskR).toBeNull();
    expect(p.currentExposurePct).toBeNull();
    expect(p.projectedExposurePct).toBeNull();
    expect(p.riskDeltaR).toBeNull();
    expect(p.warnings).toEqual([]);
  });
});
