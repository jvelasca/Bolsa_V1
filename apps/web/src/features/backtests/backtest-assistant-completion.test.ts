import { describe, expect, it } from "vitest";
import {
  canAutoRunStep,
  emptyAssistantProgress,
  isAssistantStepComplete,
  resolveAssistantActiveStep,
  withUniverseDone,
} from "@/features/backtests/backtest-assistant-completion";
import { defaultAssistantPrefs } from "@/features/backtests/backtest-assistant-prefs";
import { buildAssistantStepPlan } from "@/features/backtests/backtest-assistant-plan";

describe("assistant session progress", () => {
  it("starts at universe with no checks", () => {
    const p = emptyAssistantProgress();
    expect(resolveAssistantActiveStep(p, null)).toBe("universe");
    expect(isAssistantStepComplete("universe", p)).toBe(false);
    expect(isAssistantStepComplete("semifinal", p)).toBe(false);
    expect(isAssistantStepComplete("lab", p)).toBe(false);
    expect(isAssistantStepComplete("finalists", p)).toBe(false);
  });

  it("only marks universe done after flag — not later steps", () => {
    const p = { ...emptyAssistantProgress(), universeDone: true };
    expect(isAssistantStepComplete("universe", p)).toBe(true);
    expect(isAssistantStepComplete("semifinal", p)).toBe(false);
    expect(isAssistantStepComplete("lab", p)).toBe(false);
    expect(resolveAssistantActiveStep(p, null)).toBe("semifinal");
  });

  it("unlocks semifinal only after universe ✓", () => {
    expect(canAutoRunStep("semifinal", emptyAssistantProgress(), true)).toBe(
      false,
    );
    expect(
      canAutoRunStep(
        "semifinal",
        { ...emptyAssistantProgress(), universeDone: true },
        true,
      ),
    ).toBe(true);
  });

  it("withUniverseDone unlocks semifinal in the same tick (no 2º Play)", () => {
    const stale = emptyAssistantProgress();
    // Bug histórico: setState({ universeDone }) + canAutoRunStep(stale) → bloqueo.
    expect(canAutoRunStep("semifinal", stale, true)).toBe(false);
    expect(canAutoRunStep("semifinal", withUniverseDone(stale), true)).toBe(
      true,
    );
  });

  it("advances active step one by one", () => {
    let p = emptyAssistantProgress();
    expect(resolveAssistantActiveStep(p, null)).toBe("universe");
    p = { ...p, universeDone: true };
    expect(resolveAssistantActiveStep(p, null)).toBe("semifinal");
    p = { ...p, semifinalDone: true };
    expect(resolveAssistantActiveStep(p, null)).toBe("lab");
    p = { ...p, labDone: true };
    expect(resolveAssistantActiveStep(p, null)).toBe("finalists");
  });
});

describe("buildAssistantStepPlan", () => {
  it("titles include ordinal 1/4", () => {
    const plan = buildAssistantStepPlan(
      "universe",
      defaultAssistantPrefs(),
      emptyAssistantProgress(),
      true,
      "click",
    );
    expect(plan.title).toMatch(/1\/4/);
    expect(plan.canExecute).toBe(true);
  });

  it("blocks semifinal without universe done", () => {
    const plan = buildAssistantStepPlan(
      "semifinal",
      defaultAssistantPrefs(),
      emptyAssistantProgress(),
      true,
      "advance",
    );
    expect(plan.canExecute).toBe(false);
    expect(plan.blockedReason).toMatch(/anterior/i);
  });
});
