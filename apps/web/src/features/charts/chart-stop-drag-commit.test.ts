/**
 * Tests — commit G4 chart stop → Confirm.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { commitChartStopDrag } from "@/features/charts/chart-stop-drag-commit";
import {
  clearChartSignedStopPrefill,
  peekChartSignedStopPrefill,
} from "@/features/charts/chart-signed-stop-prefill";
import { BOLSA_CONFIRM_DRAWER_EVENT } from "@/features/confirm/confirm-drawer";
import type { PositionDto } from "@bolsa/shared";

vi.mock("@/features/trading/demo-book-prefs", () => ({
  loadDemoBookPrefs: () => ({ mode: "semi", countryPrefer: "home" }),
  demoBookAllowsEnqueueConfirm: () => true,
}));

afterEach(() => {
  clearChartSignedStopPrefill();
});

function positionStub(): PositionDto {
  return {
    id: "p1",
    instrumentId: "inst-1",
    symbol: "AAA",
    name: "AAA SA",
    quantity: 10,
    avgCost: 100,
    lastPrice: 104,
    marketValue: 1040,
    unrealizedPnl: 40,
    unrealizedPnlPct: 0.04,
    operational: {
      tradePlanId: "tp-1",
      direction: "long",
      currentStop: 95,
      target1: 110,
      target2: 120,
      status: "OPEN",
    },
  };
}

describe("commitChartStopDrag", () => {
  beforeEach(() => {
    clearChartSignedStopPrefill();
  });

  it("geometría inválida no abre Confirm ni prefill", () => {
    const seen: unknown[] = [];
    const onEv = (e: Event) => seen.push((e as CustomEvent).detail);
    window.addEventListener(BOLSA_CONFIRM_DRAWER_EVENT, onEv);
    const enqueue = vi.fn();
    try {
      const result = commitChartStopDrag({
        phase: "preparada",
        showsPlanLevels: true,
        direction: "long",
        entry: 100,
        ghostStop: 105,
        instrumentId: "inst-1",
        accountId: "acc-1",
        position: null,
        deps: {
          enqueue,
          setActive: vi.fn(),
          findQueueItemIdForInstrument: () => null,
        },
      });
      expect(result.ok).toBe(false);
      expect(seen).toEqual([]);
      expect(peekChartSignedStopPrefill()).toBeNull();
      expect(enqueue).not.toHaveBeenCalled();
    } finally {
      window.removeEventListener(BOLSA_CONFIRM_DRAWER_EVENT, onEv);
    }
  });

  it("disparada no permite commit", () => {
    const result = commitChartStopDrag({
      phase: "disparada",
      showsPlanLevels: true,
      direction: "long",
      entry: 100,
      ghostStop: 95,
      instrumentId: "inst-1",
      accountId: "acc-1",
      position: null,
      deps: {
        enqueue: vi.fn(),
        setActive: vi.fn(),
        findQueueItemIdForInstrument: () => null,
      },
    });
    expect(result).toEqual({ ok: false, reason: "drag_not_allowed" });
  });

  it("preparada válida: prefill + abre Confirm", () => {
    const seen: unknown[] = [];
    const onEv = (e: Event) => seen.push((e as CustomEvent).detail);
    window.addEventListener(BOLSA_CONFIRM_DRAWER_EVENT, onEv);
    const setActive = vi.fn();
    try {
      const result = commitChartStopDrag({
        phase: "preparada",
        showsPlanLevels: true,
        direction: "long",
        entry: 100,
        ghostStop: 94,
        target1: 110,
        instrumentId: "inst-1",
        accountId: "acc-1",
        position: null,
        deps: {
          enqueue: vi.fn(),
          setActive,
          findQueueItemIdForInstrument: () => "q-existing",
        },
      });
      expect(result).toEqual({
        ok: true,
        signedStop: 94,
        enqueuedProtect: false,
      });
      expect(setActive).toHaveBeenCalledWith("q-existing");
      expect(peekChartSignedStopPrefill()).toEqual({
        instrumentId: "inst-1",
        signedStop: 94,
      });
      expect(seen[0]).toMatchObject({
        open: true,
        signedStop: 94,
        instrumentId: "inst-1",
      });
    } finally {
      window.removeEventListener(BOLSA_CONFIRM_DRAWER_EVENT, onEv);
    }
  });

  it("posicion válida encola protect con stop override", () => {
    const enqueue = vi.fn().mockReturnValue("q-protect");
    const setActive = vi.fn();
    const result = commitChartStopDrag({
      phase: "posicion",
      showsPlanLevels: true,
      direction: "long",
      entry: 100,
      ghostStop: 96,
      target1: 110,
      instrumentId: "inst-1",
      accountId: "acc-1",
      position: positionStub(),
      symbol: "AAA",
      deps: {
        enqueue,
        setActive,
        findQueueItemIdForInstrument: () => null,
      },
    });
    expect(result.ok).toBe(true);
    if (result.ok) expect(result.enqueuedProtect).toBe(true);
    expect(enqueue).toHaveBeenCalled();
    const payload = enqueue.mock.calls[0][0];
    expect(payload.decisionPackage?.suggestedStop).toBe(96);
    expect(setActive).toHaveBeenCalledWith("q-protect");
  });
});
