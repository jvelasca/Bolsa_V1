/**
 * V1.36 — cockpit Mercado fase POSICIÓN (integración UI).
 */

import {
  cleanup,
  render,
  screen,
  within,
  fireEvent,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import type { ReactElement } from "react";
import type { OperationalPlanViewV1, PositionDto } from "@bolsa/shared";
import { OperativaCockpitCard } from "@/features/trading/operativa-cockpit-card";
import type { InstrumentOperationalContextV1 } from "@/features/trading/use-instrument-operational-context";

const useInstrumentOperationalContext = vi.fn();

const portfolioReconStatusFromReport = vi.fn(() => "ok");

vi.mock("@/features/trading/use-instrument-operational-context", () => ({
  useInstrumentOperationalContext: (...args: unknown[]) =>
    useInstrumentOperationalContext(...args),
}));

vi.mock("@/features/operational-console/use-ops-self-eval", () => ({
  useOpsSelfEval: () => ({ data: undefined, isLoading: false }),
  portfolioReconStatusFromReport: (...args: unknown[]) =>
    portfolioReconStatusFromReport(...args),
}));

const useMesaEntriesBlocked = vi.fn(() => ({
  entriesBlocked: false,
  killOn: false,
  vetoed: 0,
  incidentCount: 0,
  incidentsFailed: false,
  paperDExecuteEnv: false,
}));

vi.mock("@/features/mesa/use-mesa-entries-blocked", () => ({
  useMesaEntriesBlocked: (...args: unknown[]) => useMesaEntriesBlocked(...args),
}));

vi.mock("@/features/accounts/use-active-account", () => ({
  useActiveAccount: () => ({
    effectiveAccountId: "acc-1",
    account: { id: "acc-1" },
    isLoading: false,
  }),
}));

vi.mock("@/stores/supervised-f3-queue-store", () => ({
  useSupervisedF3QueueStore: (
    sel: (s: {
      enqueue: () => string;
      setActive: () => void;
      items: unknown[];
    }) => unknown,
  ) => sel({ enqueue: vi.fn(() => "q1"), setActive: vi.fn(), items: [] }),
}));

vi.mock("@/stores/trading-layout-store", () => ({
  useTradingLayoutStore: (
    sel: (s: {
      operationsOpen: boolean;
      toggleOperations: () => void;
    }) => unknown,
  ) => sel({ operationsOpen: false, toggleOperations: vi.fn() }),
}));

vi.mock("@/features/confirm/confirm-drawer", () => ({
  openConfirmDrawer: vi.fn(),
  formatConfirmDrawerCtaLabel: () => "Revisar Confirm",
}));

vi.mock("@/features/trading/demo-book-prefs", () => ({
  loadDemoBookPrefs: () => ({ mode: "semi" }),
  demoBookAllowsEnqueueConfirm: () => true,
}));

vi.mock("@/features/trading/use-demo-book-prefs", () => ({
  useDemoBookPrefs: () => ({ mode: "semi" }),
}));

vi.mock("@/features/trading/demo-book-auto-arm", () => ({
  loadAutoArm: () => ({ armed: false, armedAt: null, confirmPhrase: null }),
}));

afterEach(() => cleanup());

function plan(
  partial: Partial<OperationalPlanViewV1> = {},
): OperationalPlanViewV1 {
  return {
    phase: "position",
    phaseLabel: "Posición activa",
    direction: "long",
    entry: 100,
    stopVigente: 95,
    stopInicial: 95,
    target1: 105,
    target2: 110,
    target1Reached: false,
    target2Reached: false,
    target1Touched: false,
    target1Managed: false,
    target2Touched: false,
    target2Managed: false,
    expectedRR: 2,
    riskR: 1,
    currentPrice: 102,
    unrealizedR: 0.4,
    trailingActive: false,
    trailingPeakMfeR: null,
    trailingPeakPrice: null,
    trailingStopHint: null,
    trailingDistanceR: null,
    exitAuthorityHint: null,
    hasPlan: true,
    emptyCopy: "Sin plan operativo",
    ...partial,
  };
}

function openPosition(
  operationalOverrides: Record<string, unknown> = {},
): PositionDto {
  return {
    id: "p1",
    instrumentId: "inst-aapl",
    symbol: "AAPL",
    name: "Apple",
    quantity: 10,
    avgCost: 100,
    lastPrice: 102,
    marketValue: 1020,
    unrealizedPnl: 20,
    unrealizedPnlPct: 2,
    operational: {
      status: "OPEN",
      direction: "long",
      tradePlanId: "tp-1",
      plannedEntry: 100,
      actualEntry: 100,
      initialStop: 95,
      currentStop: 95,
      target1: 105,
      target2: 110,
      unrealizedR: 0.4,
      ...operationalOverrides,
    },
  };
}

function posicionContext(
  overrides: Partial<InstrumentOperationalContextV1> = {},
): InstrumentOperationalContextV1 {
  return {
    instrumentId: "inst-aapl",
    accountId: "acc-1",
    phase: "posicion",
    plan: plan(),
    showsPlanLevels: true,
    trailing: {
      show: false,
      stopVigente: 95,
      stopSugerido: null,
      applied: false,
      label: "↗ Trailing sugerido",
      stopVigenteLabel: "Stop operativo",
      stopSugeridoLabel: "Stop sugerido",
      statusLabel: null,
    },
    study: null,
    originStudy: null,
    position: openPosition(),
    inEstudio: true,
    inConfirmQueue: false,
    confirmQueueCount: 0,
    orderPendingFill: false,
    submitIntent: null,
    loading: false,
    ...overrides,
  };
}

function renderCockpit(ui: ReactElement) {
  return render(ui);
}

describe("OperativaCockpitCard POSICIÓN V1.40", () => {
  beforeEach(() => {
    portfolioReconStatusFromReport.mockReturnValue("ok");
    useInstrumentOperationalContext.mockReturnValue(posicionContext());
    useMesaEntriesBlocked.mockReturnValue({
      entriesBlocked: false,
      killOn: false,
      vetoed: 0,
      incidentCount: 0,
      incidentsFailed: false,
      paperDExecuteEnv: false,
    });
  });

  it("shows phase Posición and operating summary", () => {
    renderCockpit(
      <OperativaCockpitCard instrumentId="inst-aapl" symbol="AAPL" />,
    );
    const cockpit = screen.getByTestId("operativa-cockpit");
    expect(cockpit.getAttribute("data-phase")).toBe("posicion");
    expect(screen.getByTestId("operativa-cockpit-phase").textContent).toBe(
      "Posición",
    );
    expect(screen.getByTestId("position-operating-summary")).toBeTruthy();
    expect(screen.getByTestId("position-operating-phrase").textContent).toMatch(
      /T1 alcanzado · Mantener/,
    );
    expect(
      screen.getByTestId("position-operating-phrase").textContent,
    ).not.toMatch(/T1_REACHED/);
    expect(
      screen.getByTestId("position-operating-next-event").textContent,
    ).toBe("T1");
    expect(
      screen.getByTestId("position-operating-protection").textContent,
    ).toMatch(/Stop operativo vigente/);
  });

  it("shows OperationalPlanView with Stop operativo label", () => {
    renderCockpit(
      <OperativaCockpitCard instrumentId="inst-aapl" symbol="AAPL" />,
    );
    const planPanel = screen.getByTestId("operativa-cockpit-plan-AAPL");
    expect(within(planPanel).getByText("🛡 Stop operativo")).toBeTruthy();
    expect(screen.queryByText(/Stop vigente/i)).toBeNull();
  });

  it("omits live price and open R from stacked plan (Summary owns estado)", () => {
    renderCockpit(
      <OperativaCockpitCard instrumentId="inst-aapl" symbol="AAPL" />,
    );
    const planPanel = screen.getByTestId("operativa-cockpit-plan-AAPL");
    expect(within(planPanel).queryByText("Actual")).toBeNull();
    expect(within(planPanel).queryByText("R abierto")).toBeNull();
    expect(screen.getByTestId("position-operating-pnl")).toBeTruthy();
  });

  it("shows exit route with Proteger and T1/T2 in posición", () => {
    renderCockpit(
      <OperativaCockpitCard instrumentId="inst-aapl" symbol="AAPL" />,
    );
    expect(screen.getByTestId("exit-route-AAPL")).toBeTruthy();
    expect(screen.getByTestId("exit-route-AAPL-node-stop").textContent).toMatch(
      /Proteger/,
    );
    expect(
      screen.getByTestId("exit-route-AAPL-node-target1").textContent,
    ).toMatch(/T1/);
  });

  it("shows single primary CTA Mantener in posición (no secondary exit buttons)", () => {
    renderCockpit(
      <OperativaCockpitCard instrumentId="inst-aapl" symbol="AAPL" />,
    );
    expect(screen.getByTestId("position-operating-action").textContent).toBe(
      "Mantener",
    );
    expect(
      screen.getByTestId("position-operating-summary").getAttribute("data-cta"),
    ).toBe("maintain");
    expect(screen.getAllByText("Mantener").length).toBeGreaterThanOrEqual(1);
    expect(screen.queryByTestId("position-exit-reduce-AAPL")).toBeNull();
    expect(screen.queryByTestId("position-exit-full-AAPL")).toBeNull();
  });

  it("does not show operating summary in preparada phase", () => {
    useInstrumentOperationalContext.mockReturnValue(
      posicionContext({
        phase: "preparada",
        position: null,
        showsPlanLevels: true,
        study: {
          instrumentId: "inst-aapl",
          symbol: "AAPL",
          hasOperationalPlan: true,
          tradePlanStatus: "ARMED",
          studiedAt: "2026-08-31T09:00:00.000Z",
          entry: 100,
          stop: 94,
          target1: 112,
          target2: 124,
        } as never,
      }),
    );
    renderCockpit(
      <OperativaCockpitCard instrumentId="inst-aapl" symbol="AAPL" />,
    );
    expect(
      screen.getByTestId("operativa-cockpit").getAttribute("data-phase"),
    ).toBe("preparada");
    expect(screen.queryByTestId("position-operating-summary")).toBeNull();
    expect(screen.getByTestId("entry-operating-summary")).toBeTruthy();
    expect(screen.getByTestId("entry-operating-action").textContent).toBe(
      "Preparar operación",
    );
  });

  it("entriesBlocked → Entradas bloqueadas on preparada", () => {
    useMesaEntriesBlocked.mockReturnValue({
      entriesBlocked: true,
      killOn: true,
      vetoed: 0,
      incidentCount: 0,
      incidentsFailed: false,
      paperDExecuteEnv: false,
    });
    useInstrumentOperationalContext.mockReturnValue(
      posicionContext({
        phase: "preparada",
        position: null,
        showsPlanLevels: true,
        study: {
          instrumentId: "inst-aapl",
          symbol: "AAPL",
          hasOperationalPlan: true,
          tradePlanStatus: "ARMED",
          studiedAt: "2026-08-31T09:00:00.000Z",
          entry: 100,
          stop: 94,
          target1: 112,
          target2: 124,
        } as never,
      }),
    );
    renderCockpit(
      <OperativaCockpitCard instrumentId="inst-aapl" symbol="AAPL" />,
    );
    expect(screen.getByTestId("entry-operating-action").textContent).toBe(
      "Entradas bloqueadas",
    );
    expect(screen.getByTestId("entry-operating-phrase").textContent).toMatch(
      /bloqueadas/i,
    );
  });
});

describe("OperativaCockpitCard POV star card V1.60", () => {
  beforeEach(() => {
    portfolioReconStatusFromReport.mockReturnValue("ok");
    useInstrumentOperationalContext.mockReturnValue(posicionContext());
    useMesaEntriesBlocked.mockReturnValue({
      entriesBlocked: false,
      killOn: false,
      vetoed: 0,
      incidentCount: 0,
      incidentsFailed: false,
      paperDExecuteEnv: false,
    });
  });

  it("GP-V160-01/02: T2_READY vs T2_EXECUTED en operativa-cockpit-pov-state", () => {
    useInstrumentOperationalContext.mockReturnValue(
      posicionContext({
        position: openPosition({
          status: "PARTIAL",
          remainingQuantity: 7,
          target1Leg: {
            status: "executed",
            fillId: "tx-t1",
            at: "2026-09-01T11:00:00.000Z",
          },
          target2Leg: {
            status: "triggered",
            at: "2026-09-01T13:00:00.000Z",
          },
        }),
      }),
    );
    renderCockpit(
      <OperativaCockpitCard instrumentId="inst-aapl" symbol="AAPL" />,
    );
    const povState = screen.getByTestId("operativa-cockpit-pov-state");
    expect(povState.getAttribute("data-state")).toBe("T2_READY");
    expect(povState.getAttribute("data-pov-state")).toBe("T2_READY");
    expect(povState.textContent).toMatch(
      /T2 disparado · pendiente de ejecutar/i,
    );
    expect(screen.getByTestId("operativa-cockpit-phase").textContent).toBe(
      "Posición · T2 listo",
    );

    useInstrumentOperationalContext.mockReturnValue(
      posicionContext({
        position: openPosition({
          status: "PARTIAL",
          remainingQuantity: 3,
          target1Leg: {
            status: "executed",
            fillId: "tx-t1",
            at: "2026-09-01T11:00:00.000Z",
          },
          target2Leg: {
            status: "executed",
            fillId: "tx-t2",
            at: "2026-09-01T14:00:00.000Z",
          },
        }),
      }),
    );
    cleanup();
    renderCockpit(
      <OperativaCockpitCard instrumentId="inst-aapl" symbol="AAPL" />,
    );
    const executed = screen.getByTestId("operativa-cockpit-pov-state");
    expect(executed.getAttribute("data-state")).toBe("T2_EXECUTED");
    expect(executed.getAttribute("data-pov-state")).toBe("T2_EXECUTED");
    expect(executed.textContent).toMatch(/T2 ejecutado/i);
    expect(screen.getByTestId("operativa-cockpit-phase").textContent).toBe(
      "Posición · T2 ejecutado",
    );
  });

  it("GP-V160-02: RECONCILIATION_DRIFT copy + recon chip CRITICAL (≠ unavailable)", () => {
    portfolioReconStatusFromReport.mockReturnValue("drift");
    useInstrumentOperationalContext.mockReturnValue(
      posicionContext({
        position: openPosition({
          status: "PROTECTED",
          currentStop: 98,
          revisions: [
            {
              revisionId: "r1",
              at: "2026-09-01T10:00:00.000Z",
              previousStop: 95,
              nextStop: 98,
              previousStatus: "OPEN",
              nextStatus: "PROTECTED",
              origin: "protect",
              reason: "protect",
            },
          ],
        }),
      }),
    );
    renderCockpit(
      <OperativaCockpitCard instrumentId="inst-aapl" symbol="AAPL" />,
    );
    const povState = screen.getByTestId("operativa-cockpit-pov-state");
    expect(povState.getAttribute("data-state")).toBe("RECONCILIATION_DRIFT");
    expect(povState.getAttribute("data-pov-state")).toBe(
      "RECONCILIATION_DRIFT",
    );
    expect(povState.textContent).toMatch(/discrepancia de cartera/i);
    expect(povState.textContent).not.toMatch(/RECONCILIATION_ERROR/);
    const recon = screen.getByTestId("operativa-cockpit-recon");
    expect(recon.getAttribute("data-recon")).toBe("CRITICAL");
    expect(screen.getByTestId("operativa-cockpit-phase").textContent).toBe(
      "Posición · Recon drift",
    );
  });

  it("GP-V160-03/04: stop history colapsable con data-testid", () => {
    useInstrumentOperationalContext.mockReturnValue(
      posicionContext({
        position: openPosition({
          status: "PROTECTED",
          currentStop: 102,
          revisions: [
            {
              revisionId: "r1",
              at: "2026-09-01T10:00:00.000Z",
              previousStop: 95,
              nextStop: 98,
              previousStatus: "OPEN",
              nextStatus: "PROTECTED",
              origin: "protect",
              reason: "protect",
            },
            {
              revisionId: "r2",
              at: "2026-09-01T12:00:00.000Z",
              previousStop: 98,
              nextStop: 102,
              previousStatus: "PROTECTED",
              nextStatus: "PROTECTED",
              origin: "trail",
              reason: "trail",
            },
          ],
        }),
      }),
    );
    renderCockpit(
      <OperativaCockpitCard instrumentId="inst-aapl" symbol="AAPL" />,
    );
    expect(screen.queryByTestId("operativa-cockpit-stop-history")).toBeNull();
    fireEvent.click(
      screen.getByTestId("operativa-cockpit-stop-history-toggle"),
    );
    const history = screen.getByTestId("operativa-cockpit-stop-history");
    expect(history.textContent).toMatch(/Protect/);
    expect(history.textContent).toMatch(/Trail #1/);
    expect(history.textContent).toMatch(/102\.00/);
  });
});

describe("OperativaCockpitCard honesty wiring (V1.41.2)", () => {
  it("passes entriesBlocked, gateStatus and orderPending into builders", () => {
    const src = readFileSync(
      resolve(__dirname, "operativa-cockpit-card.tsx"),
      "utf8",
    );
    expect(src).toMatch(/useMesaEntriesBlocked/);
    expect(src).toMatch(/entriesBlocked,/);
    expect(src).toMatch(/gateStatus: opinion\?\.gateStatus/);
    expect(src).toMatch(/orderPending: context\.orderPendingFill/);
  });

  it("feeds orderPendingFill into summaries for ExecutionState (V1.42 F2)", () => {
    const src = readFileSync(
      resolve(__dirname, "operativa-cockpit-card.tsx"),
      "utf8",
    );
    expect(src).toMatch(/orderPending=\{context\.orderPendingFill\}/);
    expect(src).toMatch(/orderPendingFill=\{context\.orderPendingFill\}/);
    expect(src).toMatch(/orderPending: context\.orderPendingFill/);
  });

  it("feeds submitIntent into summaries + UNKNOWN → Ver operaciones (V1.42 F2b)", () => {
    const src = readFileSync(
      resolve(__dirname, "operativa-cockpit-card.tsx"),
      "utf8",
    );
    expect(src).toMatch(/submitIntent=\{context\.submitIntent\}/);
    expect(src).toMatch(/buildExecutionState|buildPositionOperatingTruth/);
    expect(src).toMatch(/unknownExecution/);
    expect(src).toMatch(/Ver operaciones/);
  });

  it("uses PositionOperatingTruth on open-position path (V1.42 F3)", () => {
    const src = readFileSync(
      resolve(__dirname, "operativa-cockpit-card.tsx"),
      "utf8",
    );
    expect(src).toMatch(/buildPositionOperatingTruth/);
    expect(src).toMatch(/pot=\{positionPot\}/);
  });

  it("chrome DECISIÓN + CONTEXTO→ESTADO→ACCIÓN (V1.42 F5)", () => {
    renderCockpit(
      <OperativaCockpitCard instrumentId="inst-aapl" symbol="AAPL" />,
    );
    const cockpit = screen.getByTestId("operativa-cockpit");
    expect(cockpit.getAttribute("aria-label")).toBe("DECISIÓN · AAPL");
    expect(screen.getByTestId("decision-contexto")).toBeTruthy();
    expect(screen.getByTestId("decision-estado")).toBeTruthy();
    expect(screen.getByTestId("decision-accion")).toBeTruthy();
    const src = readFileSync(
      resolve(__dirname, "operativa-cockpit-card.tsx"),
      "utf8",
    );
    expect(src).toMatch(/primaryCtaKind=\{potExitKind\}/);
    expect(src).toMatch(/Confirm es la única firma/);
    expect(src).toMatch(/Ranking ≠ BUY/);
  });

  it("single primary CTA: disparada + cola Confirm does not dual-propose (V1.42 F5)", () => {
    const src = readFileSync(
      resolve(__dirname, "operativa-cockpit-card.tsx"),
      "utf8",
    );
    expect(src).toMatch(/inConfirmPath/);
    expect(src).toMatch(/showPropose/);
    expect(src).toMatch(/!inConfirmPath/);
  });
});
