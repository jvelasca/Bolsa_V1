import { describe, expect, it } from "vitest";
import {
  PAPER_AUTO_ARM_PERMISSION_LINE,
  PAPER_AUTO_ARM_STATE_ARMED,
  PAPER_AUTO_ARM_STATE_DISARMED,
  PAPER_AUTO_ARMED_EXEC_OFF,
  PAPER_AUTO_ARMED_EXEC_ON,
  PAPER_AUTO_EXECUTION_VENUE,
  PAPER_AUTO_SPINE,
  PAPER_SEMI_SPINE,
  buildPaperAutoPosture,
} from "./paper-auto-posture.js";

describe("buildPaperAutoPosture", () => {
  it("SEMI default requires human Confirm; AUTO off", () => {
    const p = buildPaperAutoPosture({});
    expect(p.modeLabel).toBe("SEMI");
    expect(p.requiresHumanConfirm).toBe(true);
    expect(p.executeEligible).toBe(false);
    expect(p.autoActive).toBe(false);
    expect(p.statusBadge).toBeNull();
    expect(p.spineLine).toBe(PAPER_SEMI_SPINE);
    expect(p.modeDetail).toMatch(/Humano confirma/);
    expect(p.modeDetail).toMatch(/AUTO off/);
    expect(p.armStateLabel).toBe(PAPER_AUTO_ARM_STATE_DISARMED);
    expect(p.executionVenueLabel).toBe(PAPER_AUTO_EXECUTION_VENUE);
  });

  it("MANUAL never pretends AUTO or Confirm queue", () => {
    const p = buildPaperAutoPosture({ bookMode: "manual" });
    expect(p.modeLabel).toBe("MANUAL");
    expect(p.requiresHumanConfirm).toBe(false);
    expect(p.executeEligible).toBe(false);
    expect(p.statusBadge).toBeNull();
    expect(p.armStateLabel).toBe(PAPER_AUTO_ARM_STATE_DISARMED);
  });

  it("AUTO without arm coerces honesty to SEMI posture", () => {
    const p = buildPaperAutoPosture({
      bookMode: "auto",
      autoArmed: false,
      paperDExecuteEnv: true,
    });
    expect(p.autoActive).toBe(false);
    expect(p.modeLabel).toBe("SEMI");
    expect(p.requiresHumanConfirm).toBe(true);
    expect(p.executeEligible).toBe(false);
    expect(p.armStateLabel).toBe(PAPER_AUTO_ARM_STATE_DISARMED);
  });

  it("AUTO armed + PAPER_D_EXECUTE off → armado · ejecución off", () => {
    const p = buildPaperAutoPosture({
      bookMode: "auto",
      autoArmed: true,
      paperDExecuteEnv: false,
    });
    expect(p.autoActive).toBe(true);
    expect(p.modeLabel).toBe("AUTO");
    expect(p.requiresHumanConfirm).toBe(false);
    expect(p.executeEligible).toBe(false);
    expect(p.statusBadge).toBe(PAPER_AUTO_ARMED_EXEC_OFF);
    expect(p.spineLine).toBe(PAPER_AUTO_SPINE);
    expect(p.modeDetail).toMatch(/arm ≠ execute/);
    expect(p.modeDetail).not.toMatch(/LIVE broker/);
    expect(p.armStateLabel).toBe(PAPER_AUTO_ARM_STATE_ARMED);
    expect(p.executionVenueLabel).toBe(PAPER_AUTO_EXECUTION_VENUE);
    expect(p.statusBadge).not.toMatch(/ejecución on/i);
  });

  it("AUTO armed + PAPER_D_EXECUTE on → same spine minus firma", () => {
    const p = buildPaperAutoPosture({
      bookMode: "auto",
      autoArmed: true,
      paperDExecuteEnv: true,
    });
    expect(p.autoActive).toBe(true);
    expect(p.requiresHumanConfirm).toBe(false);
    expect(p.executeEligible).toBe(true);
    expect(p.statusBadge).toBe(PAPER_AUTO_ARMED_EXEC_ON);
    expect(p.spineLine).toBe(PAPER_AUTO_SPINE);
    expect(p.modeDetail).toMatch(/paper/);
    expect(p.modeDetail).not.toMatch(/Humano confirma/);
    expect(p.armStateLabel).toBe(PAPER_AUTO_ARM_STATE_ARMED);
  });

  it("SEMI ignores PAPER_D_EXECUTE for executeEligible", () => {
    const p = buildPaperAutoPosture({
      bookMode: "semi",
      autoArmed: true,
      paperDExecuteEnv: true,
    });
    expect(p.requiresHumanConfirm).toBe(true);
    expect(p.executeEligible).toBe(false);
    expect(p.statusBadge).toBeNull();
    expect(p.autoArmed).toBe(true);
    expect(p.autoActive).toBe(false);
    expect(p.armStateLabel).toBe(PAPER_AUTO_ARM_STATE_DISARMED);
  });

  it("V2.46 — MANUAL with stale arm latch never shows AUTO ARMADO", () => {
    const p = buildPaperAutoPosture({
      bookMode: "manual",
      autoArmed: true,
      paperDExecuteEnv: true,
    });
    expect(p.autoArmed).toBe(true);
    expect(p.autoActive).toBe(false);
    expect(p.modeLabel).toBe("MANUAL");
    expect(p.armStateLabel).toBe(PAPER_AUTO_ARM_STATE_DISARMED);
    expect(p.executeEligible).toBe(false);
  });

  it("V2.46 — AUTO state matrix: chrome ARMADO only when autoActive", () => {
    const rows: Array<{
      name: string;
      bookMode: "manual" | "semi" | "auto";
      autoArmed: boolean;
      paperDExecuteEnv: boolean;
      modeLabel: string;
      autoActive: boolean;
      armState:
        | typeof PAPER_AUTO_ARM_STATE_ARMED
        | typeof PAPER_AUTO_ARM_STATE_DISARMED;
      executeEligible: boolean;
      statusBadge: string | null;
    }> = [
      {
        name: "MANUAL",
        bookMode: "manual",
        autoArmed: false,
        paperDExecuteEnv: false,
        modeLabel: "MANUAL",
        autoActive: false,
        armState: PAPER_AUTO_ARM_STATE_DISARMED,
        executeEligible: false,
        statusBadge: null,
      },
      {
        name: "SEMI",
        bookMode: "semi",
        autoArmed: false,
        paperDExecuteEnv: false,
        modeLabel: "SEMI",
        autoActive: false,
        armState: PAPER_AUTO_ARM_STATE_DISARMED,
        executeEligible: false,
        statusBadge: null,
      },
      {
        name: "AUTO DESARMADO",
        bookMode: "auto",
        autoArmed: false,
        paperDExecuteEnv: false,
        modeLabel: "SEMI",
        autoActive: false,
        armState: PAPER_AUTO_ARM_STATE_DISARMED,
        executeEligible: false,
        statusBadge: null,
      },
      {
        name: "AUTO ARMADO · PAPER EXEC OFF",
        bookMode: "auto",
        autoArmed: true,
        paperDExecuteEnv: false,
        modeLabel: "AUTO",
        autoActive: true,
        armState: PAPER_AUTO_ARM_STATE_ARMED,
        executeEligible: false,
        statusBadge: PAPER_AUTO_ARMED_EXEC_OFF,
      },
      {
        name: "AUTO ARMADO · PAPER EXEC ON",
        bookMode: "auto",
        autoArmed: true,
        paperDExecuteEnv: true,
        modeLabel: "AUTO",
        autoActive: true,
        armState: PAPER_AUTO_ARM_STATE_ARMED,
        executeEligible: true,
        statusBadge: PAPER_AUTO_ARMED_EXEC_ON,
      },
    ];
    for (const row of rows) {
      const p = buildPaperAutoPosture({
        bookMode: row.bookMode,
        autoArmed: row.autoArmed,
        paperDExecuteEnv: row.paperDExecuteEnv,
      });
      expect(p.modeLabel, row.name).toBe(row.modeLabel);
      expect(p.autoActive, row.name).toBe(row.autoActive);
      expect(p.armStateLabel, row.name).toBe(row.armState);
      expect(p.executeEligible, row.name).toBe(row.executeEligible);
      expect(p.statusBadge, row.name).toBe(row.statusBadge);
      if (p.modeLabel === "MANUAL" || p.modeLabel === "SEMI") {
        expect(p.armStateLabel, row.name).toBe(PAPER_AUTO_ARM_STATE_DISARMED);
      }
      if (p.armStateLabel === PAPER_AUTO_ARM_STATE_ARMED) {
        expect(p.autoActive, row.name).toBe(true);
        expect(p.bookMode, row.name).toBe("auto");
      }
    }
  });

  it("V2.43 — arm chrome never claims operación autorizada", () => {
    for (const input of [
      {},
      { bookMode: "auto" as const, autoArmed: true, paperDExecuteEnv: false },
      { bookMode: "auto" as const, autoArmed: true, paperDExecuteEnv: true },
    ]) {
      const p = buildPaperAutoPosture(input);
      expect(p.armPermissionLine).toBe(PAPER_AUTO_ARM_PERMISSION_LINE);
      expect(p.armPermissionLine).not.toMatch(/operaci[oó]n autorizad/i);
      expect(p.armStateLabel).not.toMatch(/operaci[oó]n autorizad/i);
      expect(p.executionVenueLabel).toBe(PAPER_AUTO_EXECUTION_VENUE);
      // ARMADO ≠ executeEligible (permission of motor ≠ order auth)
      if (
        p.armStateLabel === PAPER_AUTO_ARM_STATE_ARMED &&
        !p.paperDExecuteEnv
      ) {
        expect(p.executeEligible).toBe(false);
      }
    }
  });
});
