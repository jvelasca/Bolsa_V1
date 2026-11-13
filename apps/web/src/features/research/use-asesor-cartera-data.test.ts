/**
 * S3 · Cartera del Asesor — cargador de velas.
 *
 * No existe endpoint batch de OHLCV: el cargador debe acotar concurrencia,
 * reutilizar la caché del gráfico y aislar el fallo de un instrumento. Si esto
 * se rompe, la pestaña Cartera dispara N lecturas simultáneas o se cae entera
 * porque un valor no tiene histórico.
 */

import { describe, expect, it, vi } from "vitest";
import type { OhlcvBarDto } from "@bolsa/shared";
import {
  ASESOR_CARTERA_BARS_CONCURRENCY,
  loadAsesorCarteraBars,
  memoizedStructureForBars,
} from "./use-asesor-cartera-data";

function bar(close: number): OhlcvBarDto {
  return {
    timestamp: "2026-11-12T00:00:00.000Z",
    open: close,
    high: close + 0.1,
    low: close - 0.1,
    close,
    volume: 1_000,
    adjClose: null,
    source: "yahoo",
  };
}

const flush = () => new Promise((resolve) => setTimeout(resolve, 0));

describe("loadAsesorCarteraBars", () => {
  it("nunca supera la concurrencia configurada y sí la aprovecha", async () => {
    const ids = Array.from({ length: 10 }, (_, i) => `inst-${i}`);
    let active = 0;
    let peak = 0;

    const result = await loadAsesorCarteraBars({
      instrumentIds: ids,
      loadBars: async (id) => {
        active += 1;
        peak = Math.max(peak, active);
        await flush();
        active -= 1;
        return [bar(Number(id.split("-")[1]))];
      },
    });

    expect(peak).toBeLessThanOrEqual(ASESOR_CARTERA_BARS_CONCURRENCY);
    expect(peak).toBeGreaterThan(1);
    expect(result.peakConcurrency).toBe(peak);
    expect(result.barsById.size).toBe(10);
    expect(result.failedIds).toEqual([]);
  });

  it("reutiliza la caché existente sin llamar al fetch", async () => {
    const loadBars = vi.fn(async () => [bar(99)]);

    const result = await loadAsesorCarteraBars({
      instrumentIds: ["aaa", "bbb", "ccc"],
      readCached: (id) => (id === "aaa" ? [bar(1), bar(2)] : null),
      loadBars,
    });

    expect(result.cachedIds).toEqual(["aaa"]);
    expect(loadBars).toHaveBeenCalledTimes(2);
    expect(result.barsById.get("aaa")).toHaveLength(2);
    expect(result.barsById.get("bbb")).toHaveLength(1);
  });

  it("aísla el fallo de un instrumento y no tumba la lista", async () => {
    const result = await loadAsesorCarteraBars({
      instrumentIds: ["ok-1", "boom", "ok-2"],
      loadBars: async (id) => {
        if (id === "boom") throw new Error("404");
        return [bar(5)];
      },
    });

    expect(result.failedIds).toEqual(["boom"]);
    expect([...result.barsById.keys()].sort()).toEqual(["ok-1", "ok-2"]);
  });

  it("deduplica ids antes de lanzar fetches", async () => {
    const loadBars = vi.fn(async () => [bar(1)]);
    const result = await loadAsesorCarteraBars({
      instrumentIds: ["aa", "aa", ""],
      loadBars,
    });

    expect(loadBars).toHaveBeenCalledTimes(1);
    expect(loadBars).toHaveBeenCalledWith("aa");
    expect(result.barsById.size).toBe(1);
  });

  it("una caché vacía no cuenta como acierto", async () => {
    const loadBars = vi.fn(async () => [bar(3)]);
    const result = await loadAsesorCarteraBars({
      instrumentIds: ["aa"],
      readCached: () => [],
      loadBars,
    });
    expect(loadBars).toHaveBeenCalledTimes(1);
    expect(result.cachedIds).toEqual([]);
  });
});

describe("memoizedStructureForBars", () => {
  function bars(count: number): OhlcvBarDto[] {
    return Array.from({ length: count }, (_, index) => {
      const close = 10 + Math.sin(index / 5) * 1.5 + index * 0.01;
      return {
        timestamp: new Date(Date.UTC(2025, 0, 1 + index)).toISOString(),
        open: close - 0.05,
        high: close + 0.2,
        low: close - 0.2,
        close,
        volume: 1_000,
        adjClose: null,
        source: "yahoo",
      };
    });
  }

  it("reutiliza el cálculo mientras no cambie la identidad del array", () => {
    const barsArray = bars(220);
    const first = memoizedStructureForBars(barsArray);
    const second = memoizedStructureForBars(barsArray);

    expect(first).not.toBeNull();
    expect(second).toBe(first);
  });

  it("recalcula cuando llega un array nuevo (refetch de velas)", () => {
    const barsArray = bars(220);
    const first = memoizedStructureForBars(barsArray);
    const refreshed = memoizedStructureForBars([...barsArray]);

    expect(first).not.toBeNull();
    expect(refreshed).not.toBeNull();
    expect(refreshed).not.toBe(first);
    expect(refreshed?.status).toBe(first?.status);
  });

  it("sin velas devuelve null sin romper el memo", () => {
    expect(memoizedStructureForBars(undefined)).toBeNull();
    expect(memoizedStructureForBars([])).toBeNull();
  });
});
