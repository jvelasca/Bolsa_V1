/**
 * V1.36 — CTAs alineados con PositionDecision.action.
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { PositionDto } from "@bolsa/shared";
import { PositionExitDrawerActions } from "@/features/trading/position-exit-drawer-actions";

vi.mock("@/features/accounts/use-active-account", () => ({
  useActiveAccount: () => ({
    effectiveAccountId: "acc-1",
    account: { id: "acc-1" },
    isLoading: false,
  }),
}));

vi.mock("@/stores/supervised-f3-queue-store", () => ({
  useSupervisedF3QueueStore: (
    sel: (s: { enqueue: () => string; setActive: () => void }) => unknown,
  ) => sel({ enqueue: vi.fn(() => "q1"), setActive: vi.fn() }),
}));

vi.mock("@/features/confirm/confirm-drawer", () => ({
  openConfirmDrawer: vi.fn(),
}));

vi.mock("@/features/trading/demo-book-prefs", () => ({
  loadDemoBookPrefs: () => ({ mode: "semi" }),
  demoBookAllowsEnqueueConfirm: () => true,
}));

afterEach(() => cleanup());

function position(
  partial: Partial<PositionDto> = {},
  exitPlan?: NonNullable<PositionDto["operational"]>["exitPlan"],
): PositionDto {
  return {
    id: "p1",
    instrumentId: "inst-1",
    symbol: "TEST",
    name: "Test",
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
      exitPlan,
    },
    ...partial,
  };
}

describe("PositionExitDrawerActions V1.36 / F7", () => {
  it("emphasizes Mantener on HOLD and hides Reducir/Salir (primaryOnly default)", () => {
    render(
      <PositionExitDrawerActions
        position={position()}
        showMaintain
        portfolioReconStatus="ok"
      />,
    );
    expect(screen.getByText("Mantener").className).toMatch(/ring-primary/);
    expect(screen.queryByTestId("position-exit-reduce-TEST")).toBeNull();
    expect(screen.queryByTestId("position-exit-full-TEST")).toBeNull();
  });

  it("shows Revisar and hides reduce/exit on recon drift", () => {
    render(
      <PositionExitDrawerActions
        position={position()}
        portfolioReconStatus="drift"
      />,
    );
    expect(screen.getByTestId("position-exit-review-TEST")).toBeTruthy();
    expect(screen.queryByTestId("position-exit-reduce-TEST")).toBeNull();
    expect(screen.queryByTestId("position-exit-full-TEST")).toBeNull();
  });

  it("shows only Reducir when primaryCtaKind=reduce", () => {
    render(
      <PositionExitDrawerActions
        position={position(undefined, {
          status: "TRIGGERED",
          suggestedAction: "reduce",
          suggestedQty: 5,
          primaryReason: "TARGET_1",
          policyTemplateId: "moderate",
        })}
        primaryCtaKind="reduce"
        portfolioReconStatus="ok"
      />,
    );
    expect(screen.getByTestId("position-exit-reduce-TEST")).toBeTruthy();
    expect(screen.queryByTestId("position-exit-full-TEST")).toBeNull();
  });

  it("shows only Salir when primaryCtaKind=exit", () => {
    render(
      <PositionExitDrawerActions
        position={position(undefined, {
          status: "TRIGGERED",
          suggestedAction: "full_exit",
          primaryReason: "STRUCTURAL_STOP",
          policyTemplateId: "moderate",
        })}
        primaryCtaKind="exit"
        portfolioReconStatus="ok"
      />,
    );
    expect(screen.getByTestId("position-exit-full-TEST")).toBeTruthy();
    expect(screen.queryByTestId("position-exit-reduce-TEST")).toBeNull();
  });

  it("shows Proteger when exit plan suggests protect", () => {
    render(
      <PositionExitDrawerActions
        position={position(undefined, {
          status: "ARMED",
          suggestedAction: "protect",
          suggestedStop: 98,
          primaryReason: "TRAIL",
          policyTemplateId: "moderate",
        })}
        primaryCtaKind="protect"
        portfolioReconStatus="ok"
      />,
    );
    expect(screen.getByTestId("position-exit-protect-TEST")).toBeTruthy();
  });

  it("V2.40 — Proteger L1 uses CABIN_TOUCH_TARGET (min-h-10)", () => {
    render(
      <PositionExitDrawerActions
        position={position(undefined, {
          status: "ARMED",
          suggestedAction: "protect",
          suggestedStop: 98,
          primaryReason: "TRAIL",
          policyTemplateId: "moderate",
        })}
        primaryCtaKind="protect"
        portfolioReconStatus="ok"
      />,
    );
    expect(screen.getByTestId("position-exit-protect-TEST").className).toMatch(
      /min-h-10/,
    );
  });

  it("V2.08 — secondary Proteger on OPEN_UNPROTECTED while Mantener is primary", () => {
    render(
      <PositionExitDrawerActions
        position={position(
          {
            operational: {
              status: "OPEN",
              direction: "long",
              tradePlanId: "manual-1",
              plannedEntry: 100,
              actualEntry: 100,
              initialStop: null,
              currentStop: null,
              target1: null,
              target2: null,
              operationalView: {
                positionId: "p1",
                instrumentId: "inst-1",
                tradePlanId: "manual-1",
                decisionId: "manual-1",
                lineageCollapsed: false,
                operatingState: "OPEN_UNPROTECTED",
                primaryAction: "MANTENER",
                levels: {
                  entry: 100,
                  currentStop: null,
                  target1: null,
                  target2: null,
                  unrealizedR: null,
                },
                t1: null,
                t2: null,
                stopHistory: [],
                events: [],
                quantity: 10,
                remainingQuantity: 10,
                templateId: null,
                analysisAsOf: null,
              },
            },
          },
          {
            status: "IDLE",
            suggestedAction: "hold",
            primaryReason: null,
            policyTemplateId: "moderate",
          },
        )}
        primaryCtaKind="maintain"
        portfolioReconStatus="ok"
      />,
    );
    expect(screen.getByText("Mantener")).toBeTruthy();
    expect(screen.getByTestId("position-exit-protect-TEST")).toBeTruthy();
  });
});
