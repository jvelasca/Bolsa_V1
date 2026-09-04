/**
 * V2.36 — AUTO timeline uses OperatorPositionPlan ladder (not flat checklist).
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { PositionJourneyReadoutV1 } from "@bolsa/shared";
import { AutoDeskPanel } from "@/features/trading/auto-desk-panel";

vi.mock("@/features/trading/use-demo-book-prefs", () => ({
  useDemoBookPrefs: () => ({ mode: "manual" as const }),
}));

vi.mock("@/features/mesa/use-mesa-entries-blocked", () => ({
  useMesaEntriesBlocked: () => ({
    paperDExecuteEnv: false,
    killOn: false,
  }),
}));

vi.mock("@/features/trading/demo-book-auto-arm", () => ({
  loadAutoArm: () => ({
    armed: false,
    armedAt: null,
    confirmPhrase: null,
  }),
  saveAutoArm: vi.fn(),
}));

vi.mock("@/features/trading/demo-book-prefs", async () => {
  const actual = await vi.importActual<
    typeof import("@/features/trading/demo-book-prefs")
  >("@/features/trading/demo-book-prefs");
  return {
    ...actual,
    patchDemoBookPrefs: vi.fn(),
  };
});

afterEach(() => cleanup());

function journey(): PositionJourneyReadoutV1 {
  return {
    entry: 184.2,
    risk: {
      initialRisk: 400,
      initialStop: 176.8,
      currentProtected: null,
      realizedR: null,
      unrealizedR: 0.4,
      remainingQuantity: 62,
    },
    t1: {
      trigger: 195,
      status: "pending",
      qtyFractionPct: 30,
      executed: false,
    },
    t2: {
      trigger: 205,
      status: "pending",
      qtyFractionPct: 30,
      executed: false,
    },
    trail: {
      active: false,
      activationEligible: false,
      currentStop: 176.8,
      lastRatchet: null,
      trailWidth: null,
    },
    remainingQuantity: 62,
    primaryAction: "MANTENER",
    stageLabel: null,
    stageMachine: null,
    lineagePathLabel: null,
    logHasT2Executed: false,
    logHasTrailApplied: false,
    eventKinds: [],
    autoPosture: null,
    killOn: false,
  };
}

describe("AutoDeskPanel V2.36 timeline", () => {
  it("renders OperatorPositionPlan ladder · no flat checklist items", () => {
    render(
      <AutoDeskPanel
        defaultOpen
        templateId="moderate"
        journey={journey()}
        birthQuantity={62}
      />,
    );
    expect(screen.getByTestId("auto-desk-panel")).toBeTruthy();
    expect(screen.getByTestId("auto-desk-position-plan")).toBeTruthy();
    expect(screen.getByTestId("operator-position-plan")).toBeTruthy();
    expect(screen.getByTestId("operator-mission-checklist")).toBeTruthy();
    expect(screen.getByTestId("exit-ladder-rung-entry")).toBeTruthy();
    expect(screen.getByTestId("exit-ladder-rung-stop")).toBeTruthy();
    expect(screen.getByTestId("exit-ladder-rung-t1")).toBeTruthy();
    expect(screen.getByTestId("exit-ladder-rung-t2")).toBeTruthy();
    expect(screen.getByTestId("exit-ladder-rung-trail")).toBeTruthy();
    expect(screen.getByTestId("auto-desk-plan-amounts")).toBeTruthy();
    expect(screen.getByTestId("auto-desk-honesty")).toBeTruthy();
    expect(screen.getByTestId("auto-desk-autonomy")).toBeTruthy();
    const preview = screen.getByTestId("auto-desk-plan-preview");
    expect(preview.querySelectorAll("ul li[data-done]").length).toBe(0);
    expect(preview.textContent).not.toMatch(/○ Stop inicial/);
  });
});
