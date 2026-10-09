/**
 * S1 — el Plan de salida del ticket declara T1/T2 con precio de backend;
 * si faltan, declara el hueco («Sin dato todavía») sin inventar.
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { F3ExitPlanBlock } from "@/features/trading/f3-exit-plan-block";
import type { OperativaExitMetaV1 } from "@/features/operations/propose-position-exit";

afterEach(() => cleanup());

function meta(partial: Partial<OperativaExitMetaV1> = {}): OperativaExitMetaV1 {
  return {
    operativaIntent: "exit_hint",
    exitSource: "event",
    plannedQty: 10,
    exitPlan: {
      status: "TRIGGERED",
      suggestedAction: "reduce",
      primaryReason: "TARGET_1",
    },
    ...partial,
  };
}

describe("F3ExitPlanBlock (S1 — objetivo con precio)", () => {
  it("muestra T1 y T2 con su precio cuando el backend los aporta", () => {
    render(
      <F3ExitPlanBlock
        meta={meta({ target1: 110, target2: 120 })}
        signedQty={10}
      />,
    );
    expect(screen.getByTestId("f3-exit-target1").textContent).toMatch(/110/);
    expect(screen.getByTestId("f3-exit-target2").textContent).toMatch(/120/);
  });

  it("declara el hueco cuando T1/T2 no vienen (sin fabricar)", () => {
    render(<F3ExitPlanBlock meta={meta()} signedQty={10} />);
    expect(screen.getByTestId("f3-exit-target1").textContent).toMatch(
      /Sin dato todavía/,
    );
    expect(screen.getByTestId("f3-exit-target2").textContent).toMatch(
      /Sin dato todavía/,
    );
  });
});
