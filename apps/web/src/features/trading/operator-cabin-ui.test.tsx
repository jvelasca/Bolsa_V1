/**
 * V2.25 — cabin density · semantic protection · status states.
 * V2.29 — Protection State phases (Planificado / Protegido / …).
 * V2.31 — Premium Visual System (3 tamaños · números · menos cards).
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
  OperatorRiskBox,
} from "@/features/trading/operator-cabin-ui";

afterEach(() => cleanup());

describe("operator-cabin-ui V2.25 polish", () => {
  it("V2.29 protection line uses phase labels (not CALCULADA jargon)", () => {
    const { rerender } = render(
      <OperatorProtectionLine
        protection={{
          kind: "none",
          label: "SIN PROTECCIÓN",
          honesty: "none",
          phase: "none",
          phaseLabel: "Sin protección",
          isTechnical: false,
          stop: null,
          plannedStop: null,
        }}
      />,
    );
    const line = screen.getByTestId("operator-protection-line");
    expect(line.className).toMatch(/rose/);
    expect(line.getAttribute("role")).toBe("status");
    expect(line.getAttribute("data-cabin-density")).toBe("v2.25");
    expect(line.getAttribute("data-protection-phase")).toBe("none");
    expect(screen.getByTestId("operator-protection-label").textContent).toMatch(
      /Sin protección/i,
    );

    rerender(
      <OperatorProtectionLine
        protection={{
          kind: "none",
          label: "SIN PROTECCIÓN",
          honesty: "calculated",
          phase: "planned",
          phaseLabel: "Planificado",
          isTechnical: false,
          stop: null,
          plannedStop: 95,
        }}
      />,
    );
    expect(screen.getByTestId("operator-protection-line").className).toMatch(
      /sky/,
    );
    expect(
      screen
        .getByTestId("operator-protection-line")
        .getAttribute("data-protection-phase"),
    ).toBe("planned");
    expect(screen.getByTestId("operator-protection-label").textContent).toMatch(
      /Planificado/,
    );
    expect(
      screen.getByTestId("operator-protection-label").textContent,
    ).not.toMatch(/CALCULADA|CONFIRMADA/);
    expect(
      screen.getByTestId("operator-protection-plan-vs-exec").textContent,
    ).toMatch(/Plan/);
    expect(
      screen.getByTestId("operator-protection-plan-vs-exec").textContent,
    ).toMatch(/Ejecución pendiente/);

    rerender(
      <OperatorProtectionLine
        protection={{
          kind: "emergency",
          label: "Protección de emergencia",
          honesty: "confirmed",
          phase: "protected",
          phaseLabel: "Protegido",
          isTechnical: false,
          stop: 90,
          plannedStop: null,
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
          phase: "protected",
          phaseLabel: "Protegido",
          isTechnical: true,
          stop: 100,
          plannedStop: 100,
        }}
      />,
    );
    expect(screen.getByTestId("operator-protection-line").className).toMatch(
      /emerald/,
    );
    expect(screen.getByTestId("operator-protection-label").textContent).toMatch(
      /Protegido/,
    );
    expect(
      screen.getByTestId("operator-protection-label").textContent,
    ).not.toMatch(/CONFIRMADA/);
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
    expect(
      screen.getByTestId("next-action-hero").getAttribute("data-cabin-visual"),
    ).toBe("v2.31");
    expect(screen.getByTestId("next-action-title").className).toMatch(
      /cabin-type-hero/,
    );
    expect(CABIN_INTERACTIVE).toMatch(/focus-visible:ring/);
    expect(CABIN_INTERACTIVE).toMatch(/cabin-type-meta/);
  });

  it("V2.31 risk box uses tabular operativa numbers without nested card chrome", () => {
    render(
      <OperatorRiskBox
        box={{
          capital: 10000,
          riskPct: 1,
          maxLoss: 100,
          entry: 100,
          stop: 95,
          lossAtStop: 100,
          rrT1: 2,
          rrT2: 3,
          quantity: 20,
          positionValue: 2000,
          portfolioPct: 20,
          stopDistancePct: 5,
        }}
      />,
    );
    const box = screen.getByTestId("operator-risk-box");
    expect(box.getAttribute("data-cabin-visual")).toBe("v2.31");
    expect(box.className).not.toMatch(/rounded-md/);
    expect(box.className).not.toMatch(/\bborder\b/);
    expect(screen.getByTestId("risk-box-quantity").className).toMatch(
      /tabular-nums/,
    );
    expect(screen.getByTestId("risk-box-quantity").className).toMatch(
      /cabin-type-operativa/,
    );
  });

  it("V2.31 position plan rungs are not decorative cards", () => {
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
    expect(screen.getAllByTestId("exit-ladder-connector").length).toBe(5);
    expect(screen.getByTestId("exit-ladder-pct-t1").textContent).toMatch(/30%/);
    expect(screen.getByTestId("exit-ladder-pct-t2").textContent).not.toMatch(
      /25/,
    );
    expect(screen.getByTestId("exit-ladder-remaining").textContent).toMatch(
      /40%/,
    );
    expect(screen.getByTestId("operator-position-plan").textContent).toMatch(
      /Plan de la posición/i,
    );
    expect(screen.getByTestId("mission-step-remaining").textContent).toMatch(
      /Salida final/,
    );
    const activeRung = screen.getByTestId("mission-step-t1");
    expect(activeRung.className).not.toMatch(/rounded-md/);
    expect(activeRung.className).toMatch(/cabin-type-operativa/);
    expect(activeRung.className).toMatch(/sky/);
    expect(
      screen
        .getByTestId("operator-position-plan")
        .getAttribute("data-cabin-visual"),
    ).toBe("v2.31");
  });
});
