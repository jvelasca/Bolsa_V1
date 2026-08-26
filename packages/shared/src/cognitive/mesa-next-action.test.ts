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

  it("sums portfolio R when available", () => {
    expect(
      sumPortfolioUnrealizedR([
        { operational: { unrealizedR: 1.2 } },
        { operational: { unrealizedR: -0.3 } },
      ]),
    ).toBe(0.9);
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
  it("discrepancy → protect", () => {
    const next = mapPositionNextAction({
      position: { operational: { exitPlan: { suggestedAction: "hold" } } },
      protectionDiscrepancy: true,
    });
    expect(next.kind).toBe("protect");
  });
});
