/**
 * V2.36 — AUTO timeline uses OperatorPositionPlan ladder (not flat checklist).
 * V2.39 — AUTO arm honesty: one click does not arm; phrase via tryArmAuto.
 * V2.42 — A3 cabin touch · V2.43 — ARM chrome DESARMADO/ARMADO.
 */

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { PositionJourneyReadoutV1 } from "@bolsa/shared";
import { AutoDeskPanel } from "@/features/trading/auto-desk-panel";
import {
  AUTO_ARM_CONFIRM_PHRASE,
  loadAutoArm,
  tryArmAuto,
} from "@/features/trading/demo-book-auto-arm";
import { loadDemoBookPrefs } from "@/features/trading/demo-book-prefs";

vi.mock("@/features/mesa/use-mesa-entries-blocked", () => ({
  useMesaEntriesBlocked: () => ({
    paperDExecuteEnv: false,
    killOn: false,
  }),
}));

afterEach(() => cleanup());

beforeEach(() => {
  localStorage.clear();
});

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

function renderOpen() {
  return render(
    <AutoDeskPanel
      defaultOpen
      templateId="moderate"
      journey={journey()}
      birthQuantity={62}
    />,
  );
}

describe("AutoDeskPanel V2.36 timeline", () => {
  it("renders OperatorPositionPlan ladder · no flat checklist items", () => {
    renderOpen();
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

describe("AutoDeskPanel V2.39 arm honesty", () => {
  it("one click on Automático opens A3 form and does not arm or set auto", () => {
    renderOpen();
    fireEvent.click(screen.getByTestId("auto-desk-mode-auto"));
    expect(screen.getByTestId("demo-book-auto-arm-form")).toBeTruthy();
    expect(loadAutoArm().armed).toBe(false);
    expect(loadAutoArm().confirmPhrase).toBeNull();
    expect(loadDemoBookPrefs().mode).not.toBe("auto");
  });

  it("wrong phrase fails; exact ACTIVAR AUTO arms via tryArmAuto", () => {
    renderOpen();
    fireEvent.click(screen.getByTestId("auto-desk-mode-auto"));
    fireEvent.change(screen.getByTestId("demo-book-auto-arm-phrase"), {
      target: { value: "activar auto" },
    });
    fireEvent.click(screen.getByTestId("demo-book-auto-arm-confirm"));
    expect(screen.getByTestId("demo-book-auto-arm-error")).toBeTruthy();
    expect(loadAutoArm().armed).toBe(false);
    expect(loadDemoBookPrefs().mode).not.toBe("auto");

    fireEvent.change(screen.getByTestId("demo-book-auto-arm-phrase"), {
      target: { value: AUTO_ARM_CONFIRM_PHRASE },
    });
    fireEvent.click(screen.getByTestId("demo-book-auto-arm-confirm"));
    expect(loadAutoArm().armed).toBe(true);
    expect(loadAutoArm().confirmPhrase).toBe(AUTO_ARM_CONFIRM_PHRASE);
    expect(loadDemoBookPrefs().mode).toBe("auto");
    expect(screen.queryByTestId("demo-book-auto-arm-form")).toBeNull();
  });

  it("already armed allows mode auto without forging phrase again", () => {
    expect(tryArmAuto(AUTO_ARM_CONFIRM_PHRASE).ok).toBe(true);
    renderOpen();
    fireEvent.click(screen.getByTestId("auto-desk-mode-auto"));
    expect(screen.queryByTestId("demo-book-auto-arm-form")).toBeNull();
    expect(loadDemoBookPrefs().mode).toBe("auto");
    expect(loadAutoArm().confirmPhrase).toBe(AUTO_ARM_CONFIRM_PHRASE);
  });

  it("honesty line keeps arm ≠ execute semantics", () => {
    renderOpen();
    expect(screen.getByTestId("auto-desk-honesty").textContent).toMatch(
      /armado ≠ ejecución|arm ≠ execute|Confirm = firma/i,
    );
  });

  it("V2.40 — autonomy mode buttons use CABIN_TOUCH_TARGET (min-h-10)", () => {
    renderOpen();
    for (const mode of ["manual", "semi", "auto"] as const) {
      expect(screen.getByTestId(`auto-desk-mode-${mode}`).className).toMatch(
        /min-h-10/,
      );
    }
  });

  it("V2.42 — A3 confirm/cancel/phrase use CABIN_TOUCH_TARGET (min-h-10)", () => {
    renderOpen();
    fireEvent.click(screen.getByTestId("auto-desk-mode-auto"));
    for (const id of [
      "demo-book-auto-arm-confirm",
      "demo-book-auto-arm-cancel",
      "demo-book-auto-arm-phrase",
    ] as const) {
      expect(screen.getByTestId(id).className).toMatch(/min-h-10/);
      expect(screen.getByTestId(id).className).toMatch(/focus-visible:ring/);
      expect(screen.getByTestId(id).className).not.toMatch(/text-\[10px\]/);
    }
  });

  it("V2.43 — arm-state chrome shows DESARMADO then ARMADO · never operación autorizada", () => {
    renderOpen();
    const state = screen.getByTestId("auto-desk-arm-state");
    expect(state.getAttribute("data-arm")).toBe("disarmed");
    expect(screen.getByTestId("auto-desk-arm-state-label").textContent).toBe(
      "AUTO DESARMADO",
    );
    expect(screen.getByTestId("auto-desk-execution-venue").textContent).toBe(
      "EJECUCIÓN: PAPER",
    );
    expect(screen.getByTestId("auto-desk-arm-permission").textContent).toMatch(
      /permiso de motor/i,
    );
    expect(
      screen.getByTestId("auto-desk-arm-permission").textContent,
    ).not.toMatch(/operaci[oó]n autorizad/i);

    fireEvent.click(screen.getByTestId("auto-desk-mode-auto"));
    expect(screen.getByTestId("demo-book-auto-arm-estado").textContent).toBe(
      "AUTO DESARMADO",
    );
    expect(screen.getByTestId("demo-book-auto-arm-accion").textContent).toMatch(
      /Solicitar armado/,
    );
    expect(
      screen.getByTestId("demo-book-auto-arm-permission").textContent,
    ).not.toMatch(/operaci[oó]n autorizad/i);

    fireEvent.change(screen.getByTestId("demo-book-auto-arm-phrase"), {
      target: { value: AUTO_ARM_CONFIRM_PHRASE },
    });
    fireEvent.click(screen.getByTestId("demo-book-auto-arm-confirm"));
    expect(
      screen.getByTestId("auto-desk-arm-state").getAttribute("data-arm"),
    ).toBe("armed");
    expect(screen.getByTestId("auto-desk-arm-state-label").textContent).toBe(
      "AUTO ARMADO",
    );
  });
});
