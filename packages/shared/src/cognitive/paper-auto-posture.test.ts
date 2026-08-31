import { describe, expect, it } from "vitest";
import {
  PAPER_AUTO_ARMED_EXEC_OFF,
  PAPER_AUTO_ARMED_EXEC_ON,
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
  });

  it("MANUAL never pretends AUTO or Confirm queue", () => {
    const p = buildPaperAutoPosture({ bookMode: "manual" });
    expect(p.modeLabel).toBe("MANUAL");
    expect(p.requiresHumanConfirm).toBe(false);
    expect(p.executeEligible).toBe(false);
    expect(p.statusBadge).toBeNull();
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
  });
});
