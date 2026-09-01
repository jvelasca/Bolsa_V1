/**
 * V1.63 — Chart Decision Surface HUD tests.
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { InstrumentOperationalContextV1 } from "@/features/trading/use-instrument-operational-context";
import { ChartDecisionSurfaceHud } from "@/features/charts/chart-decision-surface-hud";

const useInstrumentOperationalContext = vi.fn();

vi.mock("@/features/trading/use-instrument-operational-context", () => ({
  useInstrumentOperationalContext: (...args: unknown[]) =>
    useInstrumentOperationalContext(...args),
}));

vi.mock("@/features/operational-console/use-ops-self-eval", () => ({
  useOpsSelfEval: () => ({ data: undefined, isLoading: false }),
  portfolioReconStatusFromReport: () => "ok",
}));

vi.mock("@/features/mesa/use-mesa-entries-blocked", () => ({
  useMesaEntriesBlocked: () => ({
    entriesBlocked: false,
    killOn: false,
    vetoed: 0,
    incidentCount: 0,
    incidentsFailed: false,
    paperDExecuteEnv: false,
  }),
}));

vi.mock("@/features/trading/use-demo-book-prefs", () => ({
  useDemoBookPrefs: () => ({ mode: "semi" }),
}));

vi.mock("@/features/trading/demo-book-auto-arm", () => ({
  loadAutoArm: () => ({ armed: false, armedAt: null, confirmPhrase: null }),
}));

afterEach(() => cleanup());

function preparadaContext(): InstrumentOperationalContextV1 {
  return {
    instrumentId: "inst-aapl",
    accountId: "acc-1",
    phase: "preparada",
    plan: {
      phase: "entry",
      phaseLabel: "Entrada preparada",
      direction: "long",
      entry: 100,
      stopVigente: 94,
      stopInicial: 94,
      target1: 112,
      target2: 124,
      target1Reached: false,
      target2Reached: false,
      target1Touched: false,
      target1Managed: false,
      target2Touched: false,
      target2Managed: false,
      expectedRR: 2,
      riskR: 1,
      currentPrice: 99,
      unrealizedR: null,
      trailingActive: false,
      trailingPeakMfeR: null,
      trailingPeakPrice: null,
      trailingStopHint: null,
      trailingDistanceR: null,
      exitAuthorityHint: null,
      hasPlan: true,
      emptyCopy: "Sin plan",
    },
    showsPlanLevels: true,
    trailing: {
      show: false,
      stopVigente: 94,
      stopSugerido: null,
      applied: false,
      label: "↗ Trailing sugerido",
      stopVigenteLabel: "Stop operativo",
      stopSugeridoLabel: "Stop sugerido",
      statusLabel: null,
    },
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
    originStudy: null,
    position: null,
    inEstudio: true,
    inConfirmQueue: false,
    confirmQueueCount: 0,
    orderPendingFill: false,
    submitIntent: null,
    loading: false,
  };
}

describe("ChartDecisionSurfaceHud (V1.63)", () => {
  beforeEach(() => {
    useInstrumentOperationalContext.mockReturnValue(preparadaContext());
  });

  it("GP-V163-04: renders HUD with entry fixture preparada", () => {
    render(<ChartDecisionSurfaceHud instrumentId="inst-aapl" symbol="AAPL" />);
    expect(screen.getByTestId("chart-decision-surface-hud")).toBeTruthy();
    expect(screen.getByTestId("entry-decision-headline").textContent).toBe(
      "Entrada preparada",
    );
    expect(screen.getByTestId("operativa-cockpit-entry-action")).toBeTruthy();
    expect(screen.queryByRole("button", { name: /comprar/i })).toBeNull();
  });
});
