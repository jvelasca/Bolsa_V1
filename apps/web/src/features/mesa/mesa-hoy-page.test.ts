import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import {
  buildDailyDeskInbox,
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

  it("ARMED candidate → Preparar operación (no BUY)", () => {
    const next = mapCandidateNextAction(
      {
        symbol: "ARM1",
        status: "ARMED",
        statusLabel: "Preparado",
        gate: "PASS",
        study: {
          hasOperationalPlan: true,
          instrumentId: "inst-arm1",
          symbol: "ARM1",
          tradePlanStatus: "ARMED",
          studiedAt: "2026-08-31T09:00:00.000Z",
          entry: 100,
          stop: 94,
          target1: 112,
          target2: 124,
        } as never,
      },
      false,
    );
    expect(next.kind).toBe("view_thesis");
    expect(next.label).toBe("Preparar operación");
    expect(next.label).not.toMatch(/comprar/i);
  });

  it("TRIGGERED candidate → Revisar y confirmar", () => {
    const next = mapCandidateNextAction(
      {
        symbol: "TRG1",
        status: "TRIGGERED",
        statusLabel: "Propuesto",
        gate: "PASS",
        study: {
          hasOperationalPlan: true,
          instrumentId: "inst-trg1",
          symbol: "TRG1",
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
    expect(next.kind).toBe("review_proposal");
    expect(next.label).toBe("Revisar y confirmar");
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

  it("entriesBlocked → Entradas bloqueadas (not Ver tesis)", () => {
    const next = mapCandidateNextAction(
      {
        symbol: "ARM1",
        status: "ARMED",
        statusLabel: "Preparado",
        gate: "PASS",
        study: {
          hasOperationalPlan: true,
          instrumentId: "inst-arm1",
          symbol: "ARM1",
          tradePlanStatus: "ARMED",
          studiedAt: "2026-08-31T09:00:00.000Z",
          entry: 100,
          stop: 94,
          target1: 112,
          target2: 124,
        } as never,
      },
      true,
    );
    expect(next.kind).toBe("none");
    expect(next.label).toBe("Entradas bloqueadas");
    expect(next.allowsEntry).toBe(false);
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

  it("daily desk folds pending + position attention without BUY", () => {
    const desk = buildDailyDeskInbox({
      positions: [],
      pendingConfirm: 1,
      protectionDiscrepancies: [
        {
          symbol: "AAPL",
          reason: "Discrepancia",
          recommendedAction: "REVISAR PROTECCIÓN",
        },
      ],
    });
    expect(desk.count).toBe(2);
    for (const item of desk.items) {
      expect(item.ctaLabel.toUpperCase()).not.toContain("BUY");
    }
  });
});

describe("Hoy Daily Desk chrome (V1.42 F6)", () => {
  const src = readFileSync(resolve(__dirname, "mesa-hoy-page.tsx"), "utf8");

  it("renders Daily Desk four-bucket inbox (not ranking panels)", () => {
    expect(src).toMatch(/<DailyDeskInbox/);
    expect(src).toMatch(/buildDailyDeskInbox/);
    expect(src).toMatch(/studiesByInstrument/);
    expect(src).toMatch(/confirmQueueInstrumentIds/);
    expect(src).not.toMatch(/<MesaOpportunitiesTeaser/);
    expect(src).not.toMatch(/<MesaWatchList/);
    expect(src).not.toMatch(/<MesaCoberturaKpi/);
    expect(src).not.toMatch(/<MesaProteccionKpi/);
    expect(src).not.toMatch(/<MesaAttentionQueue/);
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

  it("open-position inbox uses POT via Daily Desk (same facts as Mercado)", () => {
    expect(src).toMatch(/buildDailyDeskInbox/);
    expect(src).toMatch(/protectPlanByInstrument/);
    expect(src).not.toMatch(/positionsNeedingAction/);
  });

  it("feeds entriesBlocked from shared hook and pending ids to Daily Desk", () => {
    expect(src).toMatch(/useMesaEntriesBlocked/);
    expect(src).toMatch(/pendingInstrumentIds/);
    expect(src).toMatch(/usePendingOrders/);
  });

  it("shows Datos chip and no session dump nor Spine on the inbox", () => {
    expect(src).toMatch(/<MesaDatosChip/);
    expect(src).not.toMatch(/<MesaSessionStateCard/);
    expect(src).not.toMatch(/<MesaOperationalHeaderStrip/);
    const spineAt = src.indexOf("<DecisionSpineDetailPanel");
    const inboxAt = src.indexOf('data-testid="hoy-inbox"');
    expect(spineAt).toBeGreaterThan(inboxAt);
  });

  it("footer points to ranking without embedding ranking panel", () => {
    expect(src).toMatch(/daily-desk-footer/);
    expect(src).toMatch(/daily-desk-link-oportunidades/);
    expect(src).toMatch(/Hoy no es\s+Mercado/);
  });
});
