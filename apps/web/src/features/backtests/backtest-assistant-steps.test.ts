import { describe, expect, it } from "vitest";
import {
  inferAssistantStep,
  assistantStepIndex,
} from "@/features/backtests/backtest-assistant-steps";

describe("inferAssistantStep (legacy hub heuristic)", () => {
  it("still maps hub tabs", () => {
    expect(
      inferAssistantStep({
        hasInstrument: true,
        exploreOkCount: 0,
        exploreRunning: false,
        hasCoachRecs: false,
        optimizeJobsPending: false,
        hasActiveTop: false,
        hubTab: "jobs",
      }),
    ).toBe("lab");
  });
});

describe("assistantStepIndex", () => {
  it("orders steps 0..3", () => {
    expect(assistantStepIndex("universe")).toBe(0);
    expect(assistantStepIndex("finalists")).toBe(3);
  });
});
