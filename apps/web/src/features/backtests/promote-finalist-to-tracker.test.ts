import { describe, expect, it } from "vitest";
import type { InstrumentStrategyTopSlotV1 } from "@bolsa/shared";
import {
  buildTrackerFromFinalistSlot,
  buildTrackerNameFromFinalist,
  kernelTimeframeFromTop,
  screenersHrefAfterTrackerCreate,
} from "@/features/backtests/promote-finalist-to-tracker";

const slot1: InstrumentStrategyTopSlotV1 = {
  rank: 1,
  label: "SMA crossover 20/50",
  strategyDefinitionId: "strat-abc",
  stars: 4,
  score: 0.82,
  source: "optimized",
  runId: "run-1",
};

describe("promote-finalist-to-tracker", () => {
  it("maps unknown TF to 1d kernel", () => {
    expect(kernelTimeframeFromTop("1h")).toBe("1d");
    expect(kernelTimeframeFromTop("1wk")).toBe("1wk");
  });

  it("builds name with symbol and rank", () => {
    expect(buildTrackerNameFromFinalist({ symbol: "ACS", slot: slot1 })).toBe(
      "Radar · ACS · #1 SMA crossover 20/50",
    );
  });

  it("rejects slot without strategyDefinitionId", () => {
    const res = buildTrackerFromFinalistSlot({
      instrumentId: "inst-1",
      symbol: "ACS",
      timeframe: "1d",
      slot: { ...slot1, strategyDefinitionId: null },
    });
    expect(res.ok).toBe(false);
  });

  it("builds dto with instrument universe and assisted origin", () => {
    const res = buildTrackerFromFinalistSlot({
      instrumentId: "inst-1",
      symbol: "ACS",
      timeframe: "1d",
      slot: slot1,
      topVersion: 3,
      scheduleKind: "on_bar_close",
    });
    expect(res.ok).toBe(true);
    if (!res.ok) return;
    expect(res.dto.strategyDefinitionId).toBe("strat-abc");
    expect(res.dto.universe).toEqual({ instrumentIds: ["inst-1"] });
    expect(res.dto.timeframe).toBe("1d");
    expect(res.dto.origin).toBe("assisted");
    expect(res.dto.schedule?.kind).toBe("on_bar_close");
    expect(res.dto.sourcePrompt).toBe("finalist:inst-1:1d:r1:v3");
  });

  it("prefers listId universe when provided", () => {
    const res = buildTrackerFromFinalistSlot({
      instrumentId: "inst-1",
      timeframe: "1wk",
      slot: slot1,
      listId: "list-ibex",
    });
    expect(res.ok).toBe(true);
    if (!res.ok) return;
    expect(res.dto.universe).toEqual({ listId: "list-ibex" });
    expect(res.dto.timeframe).toBe("1wk");
  });

  it("attaches alarm policy when provided via alarmPolicies", () => {
    const res = buildTrackerFromFinalistSlot({
      instrumentId: "inst-1",
      symbol: "ACS",
      timeframe: "1d",
      slot: slot1,
      alarmPolicies: [
        { id: "p-inform", mode: "inform_only", enabled: true },
        { id: "p-alert", mode: "alert", enabled: true },
      ],
    });
    expect(res.ok).toBe(true);
    if (!res.ok) return;
    expect(res.dto.defaultExecutionPolicyId).toBe("p-alert");
  });
});

describe("screenersHrefAfterTrackerCreate", () => {
  it("returns /screeners when trackerId is missing", () => {
    expect(screenersHrefAfterTrackerCreate()).toBe("/screeners");
    expect(screenersHrefAfterTrackerCreate(undefined)).toBe("/screeners");
    expect(screenersHrefAfterTrackerCreate("")).toBe("/screeners");
  });

  it("builds /screeners?trackerId=<id> for a given id", () => {
    expect(screenersHrefAfterTrackerCreate("tracker-abc-123")).toBe(
      "/screeners?trackerId=tracker-abc-123",
    );
  });

  it("encodes trackerId query param when it contains reserved characters", () => {
    const trackerId = "id&foo=bar";
    const params = new URLSearchParams({ trackerId });
    expect(screenersHrefAfterTrackerCreate(trackerId)).toBe(
      `/screeners?${params.toString()}`,
    );
    expect(screenersHrefAfterTrackerCreate(trackerId)).toBe(
      "/screeners?trackerId=id%26foo%3Dbar",
    );
  });

  it("encodes spaces in trackerId", () => {
    const trackerId = "tracker with spaces";
    const params = new URLSearchParams({ trackerId });
    expect(screenersHrefAfterTrackerCreate(trackerId)).toBe(
      `/screeners?${params.toString()}`,
    );
  });
});
