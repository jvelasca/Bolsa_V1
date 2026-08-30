/**
 * Tests — política B-γ drag stop (G3/G4 gates).
 */

import { describe, expect, it } from "vitest";
import {
  canDragOperationalStop,
  evaluateChartStopDragGeometry,
  isChartStopDragPhase,
  isDraggablePlanLevelKind,
  isPointerNearStopLine,
} from "@/features/charts/chart-stop-drag-policy";

describe("chart-stop-drag-policy", () => {
  it("solo preparada y posicion son fases de drag", () => {
    expect(isChartStopDragPhase("preparada")).toBe(true);
    expect(isChartStopDragPhase("posicion")).toBe(true);
    expect(isChartStopDragPhase("disparada")).toBe(false);
    expect(isChartStopDragPhase("vigilar")).toBe(false);
    expect(isChartStopDragPhase("propuesta")).toBe(false);
  });

  it("canDrag requiere niveles + fase + stop", () => {
    expect(
      canDragOperationalStop({
        phase: "preparada",
        showsPlanLevels: true,
        stopPrice: 95,
      }),
    ).toBe(true);
    expect(
      canDragOperationalStop({
        phase: "disparada",
        showsPlanLevels: true,
        stopPrice: 95,
      }),
    ).toBe(false);
    expect(
      canDragOperationalStop({
        phase: "preparada",
        showsPlanLevels: false,
        stopPrice: 95,
      }),
    ).toBe(false);
    expect(
      canDragOperationalStop({
        phase: "posicion",
        showsPlanLevels: true,
        stopPrice: null,
      }),
    ).toBe(false);
  });

  it("solo stopVigente es draggable", () => {
    expect(isDraggablePlanLevelKind("stopVigente")).toBe(true);
    expect(isDraggablePlanLevelKind("entry")).toBe(false);
    expect(isDraggablePlanLevelKind("target1")).toBe(false);
    expect(isDraggablePlanLevelKind("trailingHint")).toBe(false);
  });

  it("geometría long: stop encima de entry → stop_wrong_side", () => {
    const bad = evaluateChartStopDragGeometry({
      direction: "long",
      entry: 100,
      ghostStop: 105,
      target1: 110,
    });
    expect(bad.ok).toBe(false);
    expect(bad.reason).toBe("stop_wrong_side");

    const good = evaluateChartStopDragGeometry({
      direction: "long",
      entry: 100,
      ghostStop: 95,
      target1: 110,
      target2: 120,
    });
    expect(good.ok).toBe(true);
    expect(good.reason).toBeNull();
    expect(good.riskDistance).toBe(5);
  });

  it("hit-test cerca del stop", () => {
    expect(
      isPointerNearStopLine({ pointerY: 100, stopY: 104, thresholdPx: 8 }),
    ).toBe(true);
    expect(
      isPointerNearStopLine({ pointerY: 100, stopY: 120, thresholdPx: 8 }),
    ).toBe(false);
    expect(isPointerNearStopLine({ pointerY: 100, stopY: null })).toBe(false);
  });
});
