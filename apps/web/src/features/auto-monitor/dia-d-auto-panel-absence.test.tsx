/**
 * P1-01 — DÍA-D · AUTO: los recuentos del artefacto no se rellenan con `0`.
 *
 * Falsable: `summary.divergent ?? 0`, `oos.unmeasuredCount ?? 0` y
 * `limits.length ?? 0` convertían un hueco de medición en «cero divergencias,
 * cero límites», que se lee como «todo comprobado».
 */
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import type { components } from "@/api/schema";
import { DiaDLevelOneSummary } from "@/features/auto-monitor/dia-d-auto-panel";

type DiaDAutoReplayDto = components["schemas"]["DiaDAutoReplayDto"];

afterEach(cleanup);

function buildDetail(
  overrides: Partial<Record<keyof DiaDAutoReplayDto, unknown>>,
): DiaDAutoReplayDto {
  return {
    available: true,
    day: "2026-10-27",
    steps: [],
    summary: null,
    oos: null,
    limits: null,
    meta: {},
    ...overrides,
  } as unknown as DiaDAutoReplayDto;
}

describe("DÍA-D · AUTO (nivel 1)", () => {
  it("sin divergencias, OOS ni límites medidos no pinta ceros", () => {
    render(<DiaDLevelOneSummary detail={buildDetail({})} />);

    expect(screen.queryByText(/\b0 divergencias/)).toBeNull();
    expect(screen.queryByText(/\b0 sin medir/)).toBeNull();
    expect(screen.queryByText(/\b0 límites declarados/)).toBeNull();
    expect(screen.getAllByText(/NO MEDIDO/).length).toBeGreaterThan(0);
  });

  it("con las cifras medidas las pinta tal cual", () => {
    render(
      <DiaDLevelOneSummary
        detail={buildDetail({
          summary: { divergent: 2, notMeasured: 1, verdict: "OK" },
          oos: { closedCount: 3, openCount: 1, unmeasuredCount: 4 },
          limits: [{ id: "L1" }],
        })}
      />,
    );

    expect(screen.getByText(/2 divergencias/)).toBeTruthy();
    expect(screen.getByText(/4 sin medir/)).toBeTruthy();
    expect(screen.getByText(/1 límites declarados/)).toBeTruthy();
  });
});
