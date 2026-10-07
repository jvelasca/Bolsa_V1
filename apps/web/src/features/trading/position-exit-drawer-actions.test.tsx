/**
 * V1.36 — CTAs alineados con PositionDecision.action.
 */

import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
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

const enqueueMock = vi.hoisted(() => vi.fn(() => "q1"));
const setActiveMock = vi.hoisted(() => vi.fn());
vi.mock("@/stores/supervised-f3-queue-store", () => ({
  useSupervisedF3QueueStore: (
    sel: (s: { enqueue: () => string; setActive: () => void }) => unknown,
  ) => sel({ enqueue: enqueueMock, setActive: setActiveMock }),
}));

vi.mock("@/features/confirm/confirm-drawer", () => ({
  openConfirmDrawer: vi.fn(),
}));

const demoBookState = vi.hoisted(() => ({
  mode: "semi" as "manual" | "semi" | "auto",
}));

vi.mock("@/features/trading/demo-book-prefs", () => ({
  loadDemoBookPrefs: () => ({ mode: demoBookState.mode }),
  demoBookAllowsEnqueueConfirm: (mode: string) => mode === "semi",
}));

vi.mock("@/features/trading/use-demo-book-prefs", () => ({
  useDemoBookPrefs: () => ({ mode: demoBookState.mode }),
}));

const openSellMock = vi.hoisted(() => vi.fn(() => Promise.resolve()));
vi.mock("@/features/trading/open-sell-position-order", () => ({
  openSellOrderForPosition: openSellMock,
}));

afterEach(() => {
  cleanup();
  demoBookState.mode = "semi";
  enqueueMock.mockClear();
  setActiveMock.mockClear();
  openSellMock.mockClear();
});

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

  it("V2.40 / V2.48 — Proteger L1 uses CABIN_TOUCH_TARGET (min-h-11)", () => {
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
      /min-h-11/,
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

  it("V2.88.85+ (H1 UX) — MANUAL + HUMAN_MANUAL abre Vender directo (no encola)", async () => {
    demoBookState.mode = "manual";
    render(
      <PositionExitDrawerActions
        position={position({
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
            exitPlan: {
              status: "TRIGGERED",
              suggestedAction: "reduce",
              suggestedQty: 5,
              primaryReason: "TARGET_1",
              policyTemplateId: "moderate",
            },
          },
        })}
        primaryCtaKind="reduce"
        portfolioReconStatus="ok"
      />,
    );
    fireEvent.click(screen.getByTestId("position-exit-reduce-TEST"));
    await waitFor(() => expect(openSellMock).toHaveBeenCalledTimes(1));
    expect(openSellMock).toHaveBeenCalledWith(
      expect.objectContaining({ instrumentId: "inst-1", quantity: 5 }),
    );
    expect(enqueueMock).not.toHaveBeenCalled();
  });

  it("V2.88.85+ (H1 UX) — MANUAL + posición no manual conserva el bloqueo", () => {
    demoBookState.mode = "manual";
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
    fireEvent.click(screen.getByTestId("position-exit-reduce-TEST"));
    expect(openSellMock).not.toHaveBeenCalled();
    expect(enqueueMock).not.toHaveBeenCalled();
    expect(screen.getByText(/Vender/i)).toBeTruthy();
  });

  it("SEMI sigue encolando Confirm en Reducir (Δ sin regresión)", () => {
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
    fireEvent.click(screen.getByTestId("position-exit-reduce-TEST"));
    expect(enqueueMock).toHaveBeenCalledTimes(1);
    expect(openSellMock).not.toHaveBeenCalled();
  });
});
