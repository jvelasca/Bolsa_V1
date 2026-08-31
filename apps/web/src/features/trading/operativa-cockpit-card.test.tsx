/**
 * V1.36 — cockpit Mercado fase POSICIÓN (integración UI).
 */

import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ReactElement } from "react";
import type { OperationalPlanViewV1, PositionDto } from "@bolsa/shared";
import { OperativaCockpitCard } from "@/features/trading/operativa-cockpit-card";
import type { InstrumentOperationalContextV1 } from "@/features/trading/use-instrument-operational-context";

const useInstrumentOperationalContext = vi.fn();

vi.mock("@/features/trading/use-instrument-operational-context", () => ({
  useInstrumentOperationalContext: (...args: unknown[]) =>
    useInstrumentOperationalContext(...args),
}));

vi.mock("@/features/operational-console/use-ops-self-eval", () => ({
  useOpsSelfEval: () => ({ data: undefined, isLoading: false }),
  portfolioReconStatusFromReport: () => "ok",
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

function openPosition(): PositionDto {
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
    loading: false,
    ...overrides,
  };
}

function renderCockpit(ui: ReactElement) {
  return render(ui);
}

describe("OperativaCockpitCard POSICIÓN V1.36", () => {
  beforeEach(() => {
    useInstrumentOperationalContext.mockReturnValue(posicionContext());
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
      /Mantén/,
    );
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

  it("shows Mantener badge and exit CTAs in posición", () => {
    renderCockpit(
      <OperativaCockpitCard instrumentId="inst-aapl" symbol="AAPL" />,
    );
    expect(screen.getByText("Mantener")).toBeTruthy();
    expect(screen.getByTestId("position-exit-reduce-AAPL")).toBeTruthy();
    expect(screen.getByTestId("position-exit-full-AAPL")).toBeTruthy();
  });

  it("does not show operating summary in preparada phase", () => {
    useInstrumentOperationalContext.mockReturnValue(
      posicionContext({
        phase: "preparada",
        position: null,
        showsPlanLevels: true,
      }),
    );
    renderCockpit(
      <OperativaCockpitCard instrumentId="inst-aapl" symbol="AAPL" />,
    );
    expect(
      screen.getByTestId("operativa-cockpit").getAttribute("data-phase"),
    ).toBe("preparada");
    expect(screen.queryByTestId("position-operating-summary")).toBeNull();
  });
});
