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
    expect(p.armStateLabel).toBe(PAPER_AUTO_ARM_STATE_ARMED);
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
