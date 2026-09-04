/**
 * V2.0 — Journey HUD on DecisionSurfaceCompact (position).
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  buildPaperAutoPosture,
  buildPositionJourneyReadout,
  type PositionDto,
  type PositionOperationalViewV1,
} from "@bolsa/shared";
import { DecisionSurfaceCompact } from "@/features/trading/decision-surface-compact";

vi.mock("@/features/trading/use-position-operational-view", async () => {
  const actual = await vi.importActual<
    typeof import("@/features/trading/use-position-operational-view")
  >("@/features/trading/use-position-operational-view");
  return {
    ...actual,
    usePositionOperationalView: () => null,
  };
});

afterEach(() => cleanup());

const view: PositionOperationalViewV1 = {
  positionId: "p1",
  instrumentId: "NVDA",
  tradePlanId: "tp-1",
  decisionId: "dec-1",
  lineageCollapsed: false,
  operatingState: "TRAILING",
  primaryAction: "MANTENER",
  levels: {
    entry: 100,
    currentStop: 110,
    target1: 120,
    target2: 125,
    unrealizedR: 1,
  },
  t1: { status: "executed" },
  t2: { status: "executed" },
  stopHistory: [
    { label: "Initial", stop: 95, origin: "birth" },
    { label: "Trail #1", stop: 110, origin: "trail" },
  ],
  events: [],
  quantity: 10,
  remainingQuantity: 2,
  templateId: "moderate",
};

const position: PositionDto = {
  id: "p1",
  instrumentId: "NVDA",
  symbol: "NVDA",
  name: "NVIDIA",
  quantity: 2,
  avgCost: 100,
  lastPrice: 112,
  marketValue: 224,
  unrealizedPnl: 24,
  unrealizedPnlPct: 12,
  operational: {
    status: "PROTECTED",
    direction: "long",
    tradePlanId: "tp-1",
    plannedEntry: 100,
    actualEntry: 100,
    initialStop: 95,
    currentStop: 110,
    target1: 120,
    target2: 125,
    unrealizedR: 1,
  },
};

describe("DecisionSurfaceCompact journey HUD V2.0", () => {
  it("renders journey readout with initial risk and log T2 after trail", () => {
    const journey = buildPositionJourneyReadout({
      view,
      initialRisk: 50,
      initialStop: 95,
      realizedR: 3,
      direction: "long",
      lifecycle: {
        stage: "trailing",
        lineagePath: "trail",
        events: [
          { kind: "T1_EXECUTED" },
          { kind: "T2_EXECUTED" },
          { kind: "TRAIL_APPLIED" },
        ],
      },
      autoPosture: buildPaperAutoPosture({
        bookMode: "auto",
        autoArmed: true,
        paperDExecuteEnv: false,
      }),
      killOn: false,
    });

    render(
      <DecisionSurfaceCompact
        variant="position"
        position={position}
        symbol="NVDA"
        view={view}
        journey={journey}
      />,
    );

    expect(screen.getByTestId("position-journey-hud")).toBeTruthy();
    expect(screen.getByTestId("journey-initial-risk").textContent).toBe("50");
    expect(
      screen
        .getByTestId("position-journey-hud")
        .getAttribute("data-log-has-t2"),
    ).toBe("1");
    expect(screen.getByTestId("journey-auto-posture").textContent).toMatch(
      /ejecución off/,
    );
    expect(screen.getByTestId("journey-auto-posture").textContent).toMatch(
      /arm ≠ execute/,
    );
  });
});
