import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  CHART_PREFILL_TTL_MS,
  clearChartSignedStopPrefill,
  consumeChartSignedStopPrefill,
  isChartSignedStopPrefillExpired,
  peekChartSignedStopPrefill,
  setChartSignedStopPrefill,
} from "@/features/charts/chart-signed-stop-prefill";
import { closeConfirmDrawer } from "@/features/confirm/confirm-drawer";

afterEach(() => {
  clearChartSignedStopPrefill();
  vi.useRealTimers();
});

describe("chart-signed-stop-prefill", () => {
  beforeEach(() => {
    clearChartSignedStopPrefill();
  });

  it("consume clears prefill for matching instrument", () => {
    setChartSignedStopPrefill({ instrumentId: "inst-1", signedStop: 96 });
    expect(consumeChartSignedStopPrefill("inst-1")).toBe(96);
    expect(peekChartSignedStopPrefill()).toBeNull();
  });

  it("returns null for mismatched instrument", () => {
    setChartSignedStopPrefill({ instrumentId: "inst-1", signedStop: 96 });
    expect(consumeChartSignedStopPrefill("inst-2")).toBeNull();
    expect(peekChartSignedStopPrefill()?.signedStop).toBe(96);
  });

  it("expires after TTL", () => {
    vi.useFakeTimers();
    setChartSignedStopPrefill({ instrumentId: "inst-1", signedStop: 96 });
    vi.advanceTimersByTime(CHART_PREFILL_TTL_MS + 1);
    expect(
      isChartSignedStopPrefillExpired({
        at: Date.now() - CHART_PREFILL_TTL_MS - 1,
      }),
    ).toBe(true);
    expect(peekChartSignedStopPrefill()).toBeNull();
    expect(consumeChartSignedStopPrefill("inst-1")).toBeNull();
  });

  it("invalidates when tradePlanId context drifts", () => {
    setChartSignedStopPrefill({
      instrumentId: "inst-1",
      signedStop: 96,
      tradePlanId: "tp-old",
      currentStop: 95,
    });
    expect(
      consumeChartSignedStopPrefill("inst-1", {
        tradePlanId: "tp-new",
        currentStop: 95,
      }),
    ).toBeNull();
    expect(peekChartSignedStopPrefill()).toBeNull();
  });

  it("invalidates when currentStop context drifts", () => {
    setChartSignedStopPrefill({
      instrumentId: "inst-1",
      signedStop: 96,
      tradePlanId: "tp-1",
      currentStop: 95,
    });
    expect(
      consumeChartSignedStopPrefill("inst-1", {
        tradePlanId: "tp-1",
        currentStop: 97,
      }),
    ).toBeNull();
    expect(peekChartSignedStopPrefill()).toBeNull();
  });

  it("closeConfirmDrawer clears prefill", () => {
    setChartSignedStopPrefill({ instrumentId: "inst-1", signedStop: 96 });
    closeConfirmDrawer();
    expect(peekChartSignedStopPrefill()).toBeNull();
  });
});
