/**
 * V2.25 — cabin density · semantic protection · status states.
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import {
  CABIN_INTERACTIVE,
  NextActionHero,
  OperatorCabinStatus,
  OperatorExitLadder,
  OperatorMissionChecklist,
  OperatorProtectionLine,
} from "@/features/trading/operator-cabin-ui";

afterEach(() => cleanup());

describe("operator-cabin-ui V2.25 polish", () => {
  it("protection line uses semantic tone (not emoji-only)", () => {
    const { rerender } = render(
      <OperatorProtectionLine
        protection={{
          kind: "none",
          label: "SIN PROTECCIÓN",
          honesty: "none",
          isTechnical: false,
          stop: null,
        }}
      />,
    );
    const line = screen.getByTestId("operator-protection-line");
    expect(line.className).toMatch(/rose/);
    expect(line.getAttribute("role")).toBe("status");
    expect(line.getAttribute("data-cabin-density")).toBe("v2.25");

    rerender(
      <OperatorProtectionLine
        protection={{
          kind: "emergency",
          label: "Protección de emergencia",
          honesty: "calculated",
          isTechnical: false,
          stop: null,
        }}
      />,
    );
    expect(screen.getByTestId("operator-protection-line").className).toMatch(
      /orange/,
    );

    rerender(
      <OperatorProtectionLine
        protection={{
          kind: "technical",
          label: "Protegida",
          honesty: "confirmed",
          isTechnical: true,
          stop: 100,
        }}
      />,
    );
    expect(screen.getByTestId("operator-protection-line").className).toMatch(
      /emerald/,
    );
    expect(screen.getByTestId("operator-protection-label").textContent).toMatch(
      /CONFIRMADA/,
    );
  });

  it("mission active step has emphasis class", () => {
    render(
      <OperatorMissionChecklist
        steps={[
          { id: "entry", label: "Entrada", status: "done", detail: "100" },
          { id: "t1", label: "T1", status: "active", detail: "120" },
          { id: "t2", label: "T2", status: "pending", detail: "130" },
        ]}
      />,
    );
    expect(screen.getByTestId("mission-step-t1").className).toMatch(/sky/);
    expect(screen.getByTestId("mission-step-entry").className).toMatch(
      /opacity/,
    );
  });

  it("cabin status loading / empty / error", () => {
    const { rerender } = render(
      <OperatorCabinStatus kind="loading">Cargando…</OperatorCabinStatus>,
    );
    expect(
      screen.getByTestId("cabin-status-loading").getAttribute("role"),
    ).toBe("status");

    rerender(<OperatorCabinStatus kind="empty">Sin plan</OperatorCabinStatus>);
    expect(screen.getByTestId("cabin-status-empty").textContent).toBe(
      "Sin plan",
    );

    rerender(<OperatorCabinStatus kind="error">Falló</OperatorCabinStatus>);
    expect(screen.getByTestId("cabin-status-error").getAttribute("role")).toBe(
      "alert",
    );
  });

  it("NEXT ACTION marks density and interactive focus token exists", () => {
    render(
      <NextActionHero
        action={{
          title: "MANTENER",
          tone: "maintain",
          subtitle: null,
          condition: null,
          expires: null,
          ctaHint: null,
          levels: null,
          reasons: null,
          nextChange: null,
        }}
      />,
    );
    expect(
      screen.getByTestId("next-action-hero").getAttribute("data-cabin-density"),
    ).toBe("v2.25");
    expect(CABIN_INTERACTIVE).toMatch(/focus-visible:ring/);
  });

  it("V2.26 exit ladder renders connectors and ExitPolicy %", () => {
    render(
      <OperatorExitLadder
        ladder={{
          profileLabel: "Moderado",
          remainingPct: 40,
          remainingDetail: "40%",
          rungs: [
            {
              id: "entry",
              label: "Entrada",
              detail: "100",
              status: "done",
              reducePct: null,
            },
            {
              id: "stop",
              label: "Stop",
              detail: "95",
              status: "done",
              reducePct: null,
            },
            {
              id: "t1",
              label: "T1",
              detail: "120 · 30%",
              status: "active",
              reducePct: 30,
            },
            {
              id: "t2",
              label: "T2",
              detail: "125 · 30%",
              status: "pending",
              reducePct: 30,
            },
            {
              id: "trail",
              label: "Trailing",
              detail: "Tras T1",
              status: "pending",
              reducePct: null,
            },
          ],
        }}
      />,
    );
    expect(screen.getByTestId("operator-exit-ladder")).toBeTruthy();
    expect(screen.getAllByTestId("exit-ladder-connector").length).toBe(4);
    expect(screen.getByTestId("exit-ladder-pct-t1").textContent).toMatch(/30%/);
    expect(screen.getByTestId("exit-ladder-pct-t2").textContent).not.toMatch(
      /25/,
    );
    expect(screen.getByTestId("exit-ladder-remaining").textContent).toMatch(
      /40%/,
    );
  });
});
