/**
 * Tests — debounce del push de mandato a PostgreSQL.
 *
 * Regresión del fallo de CI `42678233823`: `scheduleMandatePush` usaba
 * `window.setTimeout`, así que un push programado justo antes del teardown de un
 * fichero de test lanzaba `ReferenceError: window is not defined` **después** de
 * que el entorno se destruyera. Vitest lo contaba como error no gestionado y
 * tumbaba la suite (exit 1) aunque los 2774 tests pasaban.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api", () => ({
  api: {
    getAccountMandates: vi.fn(async () => ({
      data: { tenures: [], links: [] },
    })),
    syncAccountMandates: vi.fn(async () => ({ data: { ok: true } })),
  },
}));

import { scheduleMandatePush } from "@/features/platform/operating-mandate-sync";
import { api } from "@/lib/api";

describe("operating-mandate-sync · debounce del push", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.clearAllMocks();
  });

  it("programa el push sin depender de `window`", () => {
    vi.stubGlobal("window", undefined);

    expect(() => scheduleMandatePush("acc-1")).not.toThrow();
    expect(vi.getTimerCount()).toBe(1);
  });

  it("agrupa varias mutaciones en un único push tras 400 ms", async () => {
    scheduleMandatePush("acc-1");
    scheduleMandatePush("acc-1");
    expect(vi.getTimerCount()).toBe(1);

    await vi.advanceTimersByTimeAsync(399);
    expect(api.syncAccountMandates).not.toHaveBeenCalled();

    await vi.advanceTimersByTimeAsync(1);
    expect(api.syncAccountMandates).toHaveBeenCalledTimes(1);
    expect(api.syncAccountMandates).toHaveBeenCalledWith(
      "acc-1",
      expect.objectContaining({ tenures: expect.any(Array) }),
    );
  });

  it("ignora cuentas vacías sin programar temporizador", () => {
    scheduleMandatePush(null);
    scheduleMandatePush(undefined);
    scheduleMandatePush("");

    expect(vi.getTimerCount()).toBe(0);
  });
});
