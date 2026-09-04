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
    expect(screen.getByTestId("journey-next-action")).toBeTruthy();
    expect(screen.getByTestId("next-action-title").textContent).toBe(
      "MANTENER",
    );
    expect(screen.getByTestId("next-action-reasons")).toBeTruthy();
    expect(
      screen
        .getByTestId("operator-protection-line")
        .getAttribute("data-protection-kind"),
    ).toBe("technical");
    expect(screen.getByTestId("journey-remaining").textContent).toMatch(/%/);
    expect(screen.getByTestId("operator-exit-ladder")).toBeTruthy();
    expect(
      screen.getByTestId("exit-ladder-rung-t1").getAttribute("data-reduce-pct"),
    ).toBe("30");
    expect(
      screen.getByTestId("exit-ladder-rung-t2").getAttribute("data-reduce-pct"),
    ).toBe("30");
    expect(screen.getByTestId("exit-ladder-pct-t1").textContent).not.toMatch(
      /25/,
    );
    expect(screen.getByTestId("mission-step-remaining")).toBeTruthy();
    expect(screen.getByTestId("operator-mission-checklist")).toBeTruthy();
    expect(screen.getByTestId("operator-risk-box")).toBeTruthy();
    expect(
      screen.getByTestId("mission-step-t1").getAttribute("data-status"),
    ).toBe("done");
    expect(screen.getByTestId("journey-initial-risk").textContent).toBe("50");
    expect(
      screen
        .getByTestId("position-journey-hud")
        .getAttribute("data-log-has-t2"),
    ).toBe("1");
    expect(screen.getByTestId("journey-auto-posture").textContent).toMatch(
      /ejecución demo off|armado ≠ ejecución/i,
    );
  });

  it("V2.24 — journey HUD exposes cabin levels 1–4", () => {
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

    const hud = screen.getByTestId("position-journey-hud");
    expect(hud.getAttribute("data-cabin-composition")).toBe("4-levels");
    expect(hud.querySelector('[data-testid="cabin-level-1"]')).toBeTruthy();
    expect(hud.querySelector('[data-testid="cabin-level-2"]')).toBeTruthy();
    expect(hud.querySelector('[data-testid="cabin-level-3"]')).toBeTruthy();
    expect(hud.querySelector('[data-testid="cabin-level-4"]')).toBeTruthy();
    expect(
      hud.querySelector('[data-testid="cabin-level-2-label"]')?.textContent,
    ).toMatch(/riesgo/i);
    expect(
      hud.querySelector('[data-testid="cabin-level-3-label"]')?.textContent,
    ).toMatch(/después/i);
    expect(
      screen
        .getByTestId("journey-next-action")
        .closest('[data-cabin-level="1"]'),
    ).toBeTruthy();
    expect(
      screen.getByTestId("operator-risk-box").closest('[data-cabin-level="2"]'),
    ).toBeTruthy();
    expect(
      screen
        .getByTestId("operator-mission-checklist")
        .closest('[data-cabin-level="3"]'),
    ).toBeTruthy();
  });
});
