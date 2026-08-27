import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import {
  buildMesaOperationalHeader,
  buildMesaProtectionState,
  buildMesaSessionState,
  filterMesaAttentionItems,
  mapCandidateNextAction,
  mapMesaNextAction,
  mesaEntriesBlocked,
} from "@bolsa/shared";

describe("mesa-hoy-page invariants", () => {
  it("incident state blocks entries before candidates can show ready", () => {
    expect(
      mesaEntriesBlocked({
        incidents: [
          {
            incidentId: "i1",
            accountId: "a",
            kind: "live_drift",
            status: "open",
            snapshot: null,
            openedAt: "",
            reviewedAt: null,
            reviewedBy: null,
            resolvedAt: null,
            resolvedBy: null,
            resolutionNote: null,
            clearedAt: null,
          },
        ],
      }),
    ).toBe(true);
    const session = buildMesaSessionState(null, {
      entriesBlocked: true,
      incidentCount: 1,
    });
    expect(session.tone).toBe("blocked");
    expect(session.detail).toContain("BLOQUEADAS");
  });

  it("no operations today headline when zero ready and no pending confirm", () => {
    const session = buildMesaSessionState(
      {
        buckets: {
          pendingConfirm: 0,
          vetoed: 0,
          deferred: 0,
          autoWaiting: 0,
        },
        decisionSessions: [],
        semiF3Queue: [],
      } as never,
      { entriesBlocked: false },
    );
    expect(session.headline).toBe("Hoy no hay operaciones recomendadas");
  });

  it("protection discrepancy appears in attention queue", () => {
    const items = filterMesaAttentionItems([], 5, [
      {
        symbol: "AAPL",
        reason: "Discrepancia de protección",
        recommendedAction: "REVISAR PROTECCIÓN",
      },
    ]);
    expect(items).toHaveLength(1);
    expect(items[0]?.symbol).toBe("AAPL");
    expect(items[0]?.recommendedAction).toBe("REVISAR PROTECCIÓN");
  });

  it("ARMED candidate has Ver tesis, not Confirm CTA", () => {
    const next = mapCandidateNextAction(
      {
        symbol: "ARM1",
        status: "ARMED",
        statusLabel: "Preparado",
        gate: "PASS",
        study: { hasOperationalPlan: true } as never,
      },
      false,
    );
    expect(next.kind).toBe("view_thesis");
    expect(next.label).not.toMatch(/comprar/i);
    expect(next.kind).not.toBe("review_proposal");
  });

  it("TRIGGERED candidate → Revisar propuesta", () => {
    const next = mapCandidateNextAction(
      {
        symbol: "TRG1",
        status: "TRIGGERED",
        statusLabel: "Propuesto",
        gate: "PASS",
        study: { hasOperationalPlan: true } as never,
      },
      false,
    );
    expect(next.kind).toBe("review_proposal");
    expect(next.label).toBe("Revisar propuesta");
  });

  it("EXPIRED candidate is not operable", () => {
    const next = mapCandidateNextAction(
      {
        symbol: "EXP1",
        status: "EXPIRED",
        statusLabel: "Descartado",
        gate: "PASS",
        study: null,
      },
      false,
    );
    expect(next.kind).not.toBe("review_proposal");
    expect(next.allowsEntry).toBe(false);
  });

  it("kill switch blocks entries", () => {
    expect(mesaEntriesBlocked({ killSwitchEffective: true })).toBe(true);
    const session = buildMesaSessionState(null, {
      entriesBlocked: true,
      killSwitchEffective: true,
    });
    expect(session.tone).toBe("blocked");
  });

  it("WATCH without plan shows — protection layers", () => {
    const protection = buildMesaProtectionState({});
    expect(protection.plan.formatted).toBe("—");
    expect(protection.summaryLabel).toBe("Sin protección");
  });

  it("protect_hint maps to Proteger, not Confirmada", () => {
    const next = mapMesaNextAction({
      protectPlan: { status: "protect_hint" },
    });
    expect(next.kind).toBe("protect");
    expect(next.label).toBe("Proteger");
    const protection = buildMesaProtectionState({
      protectPlan: { status: "protect_hint", suggestedProtectStop: 95 },
    });
    expect(protection.summaryLabel).not.toBe("Confirmada");
  });

  it("OPEN hold position → Mantener", () => {
    const next = mapMesaNextAction({
      hasOpenPosition: true,
      exitSuggestedAction: "hold",
    });
    expect(next.kind).toBe("maintain");
    expect(next.label).toBe("Mantener");
  });

  it("incidents query error is fail-closed", () => {
    const header = buildMesaOperationalHeader({
      incidentsQueryFailed: true,
      incidentCount: 0,
    });
    expect(header.operationalStatus).toBe("attention");
    expect(header.dataFreshness.state).toBe("error");
    expect(header.operationalStatusLabel).not.toBe("Normal");
  });

  it("fail-closed on portfolio query failure", () => {
    const header = buildMesaOperationalHeader({
      portfolioQueryFailed: true,
      incidentCount: 0,
    });
    expect(header.operationalStatus).toBe("attention");
    expect(header.dataFreshness.state).toBe("error");
    expect(header.operationalStatusLabel).not.toBe("Normal");
  });

  it("candidate next action never says COMPRAR", () => {
    for (const status of [
      "TRIGGERED",
      "ARMED",
      "WATCH",
      "BLOCKED",
      "EXPIRED",
    ] as const) {
      const next = mapCandidateNextAction(
        {
          symbol: "X",
          status,
          statusLabel: status,
          gate: "PASS",
          study: { hasOperationalPlan: true } as never,
        },
        false,
      );
      expect(next.label).not.toMatch(/comprar/i);
      expect(next.allowsEntry).toBe(false);
    }
  });

  it("attention extra items have a stable id per symbol", () => {
    const items = filterMesaAttentionItems([], 5, [
      {
        symbol: "NVDA",
        reason: "Discrepancia de protección",
        recommendedAction: "REVISAR PROTECCIÓN",
      },
    ]);
    expect(items[0]?.id).toBe("discrepancy-NVDA");
  });
});

describe("Hoy inbox chrome (V1.23 Fase 4)", () => {
  const src = readFileSync(resolve(__dirname, "mesa-hoy-page.tsx"), "utf8");

  it("renders the four inbox blocks in order", () => {
    const order = [
      "Requiere acción",
      "Oportunidades",
      "Vigilar",
      "Sin acción",
    ].map((title) => src.indexOf(`title="${title}"`));
    expect(order.every((i) => i >= 0)).toBe(true);
    expect([...order].sort((a, b) => a - b)).toEqual(order);
  });

  it("drops the L2 tab bar and the Confirmar tab from the chrome", () => {
    expect(src).not.toMatch(/HOY_VIEW_TABS/);
    expect(src).not.toMatch(/data-testid="hoy-view-tabs"/);
    expect(src).not.toMatch(/HOY_VIEW\.confirmar/);
    expect(src).not.toMatch(/<ConfirmPage/);
  });

  it("keeps ?view= deep links behind Ver detalles", () => {
    expect(src).toMatch(/<MesaHoyDetailsMenu \/>/);
    expect(src).toMatch(/view === HOY_VIEW\.oportunidades/);
    expect(src).toMatch(/view === HOY_VIEW\.decisiones/);
    expect(src).toMatch(/view === HOY_VIEW\.journal/);
    expect(src).toMatch(/view === HOY_VIEW\.posiciones/);
  });

  it("signs from the drawer or /confirm, not from a Hoy tab", () => {
    expect(src).toMatch(/openConfirmDrawer\(\)/);
    expect(src).toMatch(/CONFIRM_PATH/);
  });

  it("shows the Datos freshness chip and no session dump nor Spine on the inbox", () => {
    expect(src).toMatch(/<MesaDatosChip/);
    expect(src).not.toMatch(/<MesaSessionStateCard/);
    expect(src).not.toMatch(/<MesaOperationalHeaderStrip/);
    const spineAt = src.indexOf("<DecisionSpineDetailPanel");
    const inboxAt = src.indexOf('data-testid="hoy-inbox"');
    expect(spineAt).toBeGreaterThan(inboxAt);
  });
});
