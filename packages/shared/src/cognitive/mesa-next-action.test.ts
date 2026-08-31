import { describe, expect, it } from "vitest";
import {
  buildMesaOperationalHeader,
  deriveMesaDataFreshness,
  deriveMesaOperationalStatus,
  mapCandidateNextAction,
  mapMesaNextAction,
  mapPositionNextAction,
  sumPortfolioUnrealizedR,
} from "./mesa-next-action.js";

describe("mapMesaNextAction", () => {
  it("never returns COMPRAR / allowsEntry is always false", () => {
    const next = mapMesaNextAction({
      tradePlanStatus: "TRIGGERED",
      entriesBlocked: false,
    });
    expect(next.label).not.toMatch(/comprar/i);
    expect(next.allowsEntry).toBe(false);
    expect(next.kind).toBe("review_proposal");
  });

  it("WATCH without plan → Vigilar", () => {
    const next = mapMesaNextAction({
      tradePlanStatus: "WATCH",
      hasOperationalPlan: false,
    });
    expect(next.kind).toBe("watch");
    expect(next.label).toBe("Vigilar");
    expect(next.allowsEntry).toBe(false);
  });

  it("ARMED → Ver tesis without Confirm CTA", () => {
    const next = mapMesaNextAction({
      tradePlanStatus: "ARMED",
      hasOperationalPlan: true,
    });
    expect(next.kind).toBe("view_thesis");
    expect(next.kind).not.toBe("review_proposal");
    expect(next.label).toBe("Ver tesis");
    expect(next.allowsEntry).toBe(false);
  });

  it("TRIGGERED → Revisar propuesta", () => {
    const next = mapMesaNextAction({
      tradePlanStatus: "TRIGGERED",
      hasOperationalPlan: true,
    });
    expect(next.kind).toBe("review_proposal");
    expect(next.label).toBe("Revisar propuesta");
    expect(next.allowsEntry).toBe(false);
  });

  it("BLOCKED → none (not operable)", () => {
    const next = mapMesaNextAction({
      tradePlanStatus: "BLOCKED",
      hasOperationalPlan: true,
    });
    expect(next.kind).toBe("none");
    expect(next.allowsEntry).toBe(false);
  });

  it("EXPIRED → none (not operable)", () => {
    const next = mapMesaNextAction({
      tradePlanStatus: "EXPIRED",
      hasOperationalPlan: true,
    });
    expect(next.kind).toBe("none");
    expect(next.allowsEntry).toBe(false);
  });

  it("entries blocked suppresses TRIGGERED proposal", () => {
    const next = mapMesaNextAction({
      tradePlanStatus: "TRIGGERED",
      entriesBlocked: true,
    });
    expect(next.kind).toBe("none");
  });

  it("protect_hint → Proteger", () => {
    const next = mapMesaNextAction({
      protectPlan: {
        status: "protect_hint",
        suggestedProtectStop: 100,
        rMultiple: 1,
      },
    });
    expect(next.kind).toBe("protect");
  });

  it("hold + open position → Mantener", () => {
    const next = mapMesaNextAction({
      hasOpenPosition: true,
      exitSuggestedAction: "hold",
    });
    expect(next.kind).toBe("maintain");
  });
});

describe("mapCandidateNextAction", () => {
  it("TRIGGERED operable → Revisar propuesta", () => {
    const next = mapCandidateNextAction(
      {
        symbol: "AAPL",
        status: "TRIGGERED",
        statusLabel: "Listo",
        gate: "PASS",
        study: { hasOperationalPlan: true } as never,
      },
      false,
    );
    expect(next.kind).toBe("review_proposal");
    expect(next.label).toBe("Revisar propuesta");
  });

  it("ARMED → Ver tesis, not Confirm path", () => {
    const next = mapCandidateNextAction(
      {
        symbol: "MSFT",
        status: "ARMED",
        statusLabel: "Preparado",
        gate: "PASS",
        study: { hasOperationalPlan: true } as never,
      },
      false,
    );
    expect(next.kind).toBe("view_thesis");
    expect(next.kind).not.toBe("review_proposal");
  });

  it("EXPIRED → watch/none not review_proposal", () => {
    const next = mapCandidateNextAction(
      {
        symbol: "X",
        status: "EXPIRED",
        statusLabel: "Caducado",
        gate: "PASS",
        study: null,
      },
      false,
    );
    expect(next.kind).not.toBe("review_proposal");
  });

  it("entriesBlocked → Entradas bloqueadas even without study", () => {
    const next = mapCandidateNextAction(
      {
        symbol: "X",
        status: "WATCH",
        statusLabel: "Vigilar",
        gate: "PASS",
        study: null,
      },
      true,
    );
    expect(next.kind).toBe("none");
    expect(next.label).toBe("Entradas bloqueadas");
    expect(next.allowsEntry).toBe(false);
  });

  it("orderPendingFill with operable study → Ver operaciones", () => {
    const next = mapCandidateNextAction(
      {
        symbol: "AAPL",
        status: "TRIGGERED",
        statusLabel: "Listo",
        gate: "PASS",
        orderPendingFill: true,
        study: {
          hasOperationalPlan: true,
          instrumentId: "inst-aapl",
          symbol: "AAPL",
          tradePlanStatus: "TRIGGERED",
          studiedAt: "2026-08-31T09:00:00.000Z",
          entry: 100,
          stop: 94,
          target1: 112,
          target2: 124,
        } as never,
      },
      false,
    );
    expect(next.label).toBe("Ver operaciones");
  });

  it("inConfirmQueue with operable study → Revisar y confirmar", () => {
    const next = mapCandidateNextAction(
      {
        symbol: "AAPL",
        status: "TRIGGERED",
        statusLabel: "Listo",
        gate: "PASS",
        inConfirmQueue: true,
        study: {
          hasOperationalPlan: true,
          instrumentId: "inst-aapl",
          symbol: "AAPL",
          tradePlanStatus: "TRIGGERED",
          studiedAt: "2026-08-31T09:00:00.000Z",
          entry: 100,
          stop: 94,
          target1: 112,
          target2: 124,
        } as never,
      },
      false,
    );
    expect(next.label).toBe("Revisar y confirmar");
  });
});

describe("buildMesaOperationalHeader", () => {
  it("fail-closed on board query failure", () => {
    const h = buildMesaOperationalHeader({
      boardQueryFailed: true,
      incidentsQueryFailed: false,
    });
    expect(h.operationalStatus).toBe("attention");
    expect(h.dataFreshness.state).toBe("error");
  });

  it("fail-closed on incidents query failure (not zero incidents)", () => {
    const h = buildMesaOperationalHeader({
      boardQueryFailed: false,
      incidentsQueryFailed: true,
      incidentCount: 0,
    });
    expect(h.operationalStatus).toBe("attention");
    expect(h.operationalStatusLabel).toBe("Atención");
    expect(h.dataFreshness.state).toBe("error");
    expect(h.dataFreshness.label).toBe("No consultado");
  });

  it("fail-closed on portfolio query failure", () => {
    const h = buildMesaOperationalHeader({
      boardQueryFailed: false,
      incidentsQueryFailed: false,
      portfolioQueryFailed: true,
    });
    expect(h.operationalStatus).toBe("attention");
    expect(h.dataFreshness.state).toBe("error");
  });

  it("empty portfolio marks data freshness as no probe", () => {
    const h = buildMesaOperationalHeader({
      positions: [],
      noFreshnessProbe: true,
    });
    expect(h.dataFreshness.label).toMatch(/sin posiciones/i);
    expect(h.dataFreshness.state).toBe("stale");
  });

  it("multi-position partial probe is not green fresh", () => {
    const last = new Date("2026-08-26T11:30:00Z").toISOString();
    const h = buildMesaOperationalHeader({
      lastBarDate: last,
      freshnessPartialSample: { probed: 1, total: 4 },
    });
    expect(h.dataFreshness.state).not.toBe("fresh");
    expect(h.dataFreshness.label).toMatch(/muestra parcial \(1\/4\)/i);
  });

  it("sums portfolio R when available", () => {
    const h = buildMesaOperationalHeader({
      positions: [
        {
          avgCost: 100,
          quantity: 1,
          operational: { unrealizedR: 1.2, currentStop: 95, direction: "long" },
          study: { stop: 95, riskAmount: 100 },
        },
        {
          avgCost: 50,
          quantity: 1,
          operational: {
            unrealizedR: -0.3,
            currentStop: 48,
            direction: "long",
          },
          study: { stop: 48, riskAmount: 50 },
        },
      ],
    });
    expect(h.portfolioPnLR).toBe(0.9);
    expect(h.portfolioOpenRiskR).not.toBeNull();
    expect(h.totalRiskR).toBe(h.portfolioPnLR);
  });

  it("F8: default mode SEMI; AUTO armed + env off → posture honesty", () => {
    const semi = buildMesaOperationalHeader({});
    expect(semi.modeLabel).toBe("SEMI");
    expect(semi.modeDetail).toMatch(/Humano confirma/);

    const autoOff = buildMesaOperationalHeader({
      bookMode: "auto",
      autoArmed: true,
      paperDExecuteEnv: false,
    });
    expect(autoOff.modeLabel).toBe("AUTO");
    expect(autoOff.modeDetail).toMatch(/ejecución off|arm ≠ execute/i);
    expect(autoOff.paperDExecuteEnv).toBe(false);

    const autoOn = buildMesaOperationalHeader({
      bookMode: "auto",
      autoArmed: true,
      paperDExecuteEnv: true,
    });
    expect(autoOn.modeLabel).toBe("AUTO");
    expect(autoOn.modeDetail).not.toMatch(/Humano confirma/);
    expect(autoOn.paperDExecuteEnv).toBe(true);
  });
});

describe("deriveMesaDataFreshness", () => {
  it("unknown when no lastBarDate", () => {
    expect(deriveMesaDataFreshness({}).state).toBe("unknown");
  });

  it("fresh when recent", () => {
    const now = new Date("2026-08-26T12:00:00Z");
    const last = new Date("2026-08-26T11:30:00Z").toISOString();
    expect(deriveMesaDataFreshness({ lastBarDate: last, now }).state).toBe(
      "fresh",
    );
  });

  it("stale when beyond 5d threshold", () => {
    const now = new Date("2026-08-26T12:00:00Z");
    const last = new Date("2026-08-01T12:00:00Z").toISOString();
    expect(deriveMesaDataFreshness({ lastBarDate: last, now }).state).toBe(
      "stale",
    );
  });
});

describe("deriveMesaOperationalStatus", () => {
  it("blocked on kill", () => {
    expect(deriveMesaOperationalStatus({ killSwitchEffective: true })).toBe(
      "blocked",
    );
  });

  it("blocked on open incidents", () => {
    expect(deriveMesaOperationalStatus({ incidentCount: 1 })).toBe("blocked");
  });

  it("attention on query failure", () => {
    expect(deriveMesaOperationalStatus({ queryFailed: true })).toBe(
      "attention",
    );
  });
});

describe("mapPositionNextAction", () => {
  it("discrepancy alone → protect", () => {
    const next = mapPositionNextAction({
      position: { operational: { exitPlan: { suggestedAction: "hold" } } },
      protectionDiscrepancy: true,
    });
    expect(next.kind).toBe("protect");
  });
});

describe("mapMesaNextAction §A.8 EXIT vs protectionDiscrepancy", () => {
  it("full_exit + discrepancy → exit (not protect)", () => {
    const next = mapMesaNextAction({
      hasOpenPosition: true,
      exitSuggestedAction: "full_exit",
      protectionDiscrepancy: true,
    });
    expect(next.kind).toBe("exit");
    expect(next.label).toBe("Salir");
    expect(next.allowsEntry).toBe(false);
  });

  it("reduce + discrepancy → reduce (not protect)", () => {
    const next = mapMesaNextAction({
      hasOpenPosition: true,
      exitSuggestedAction: "reduce",
      protectionDiscrepancy: true,
    });
    expect(next.kind).toBe("reduce");
    expect(next.label).toBe("Reducir");
  });

  it("discrepancy alone → protect", () => {
    const next = mapMesaNextAction({
      hasOpenPosition: true,
      exitSuggestedAction: "hold",
      protectionDiscrepancy: true,
    });
    expect(next.kind).toBe("protect");
  });

  it("full_exit alone → exit", () => {
    const next = mapMesaNextAction({
      hasOpenPosition: true,
      exitSuggestedAction: "full_exit",
      protectionDiscrepancy: false,
    });
    expect(next.kind).toBe("exit");
  });
});
