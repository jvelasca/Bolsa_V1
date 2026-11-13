/**
 * Fase 4 — errores visibles y guarda de doble clic en las acciones del panel DECISIÓN.
 *
 * El alta en Estudio tarda (2 llamadas + actualización de datos): si la guarda viviera
 * sólo en el `disabled` del botón, un doble clic dentro del mismo tick dispararía dos
 * altas. Aquí se verifica la guarda síncrona y el aviso de error.
 */

import { act, cleanup, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  addToEstudioMembership: vi.fn(),
  runEstudioInstrumentsUpdate: vi.fn(),
}));

vi.mock("@/features/trading/estudio-membership", () => ({
  addToEstudioMembership: mocks.addToEstudioMembership,
}));

vi.mock("@/features/trading/estudio-instruments-update", () => ({
  runEstudioInstrumentsUpdate: mocks.runEstudioInstrumentsUpdate,
}));

import {
  useAddToEstudioAction,
  useRefreshStudyAction,
} from "@/features/trading/use-operativa-study-actions";

const addToEstudioMembership = mocks.addToEstudioMembership;
const runEstudioInstrumentsUpdate = mocks.runEstudioInstrumentsUpdate;

beforeEach(() => {
  addToEstudioMembership.mockReset();
  runEstudioInstrumentsUpdate.mockReset();
});

afterEach(() => cleanup());

describe("useAddToEstudioAction", () => {
  it("un doble clic no crea dos altas", async () => {
    let resolveFirst: ((v: unknown) => void) | null = null;
    addToEstudioMembership.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveFirst = resolve;
        }),
    );
    runEstudioInstrumentsUpdate.mockResolvedValue(undefined);
    const pushToast = vi.fn();
    const upsertMembers = vi.fn();
    const { result } = renderHook(() =>
      useAddToEstudioAction({
        instrumentId: "inst-1",
        symbol: "AAPL",
        pushToast,
        upsertMembers,
      }),
    );

    act(() => {
      result.current.addToEstudio();
      result.current.addToEstudio();
    });
    // El alta arranca con un `import()` dinámico: la guarda síncrona evita que el
    // segundo clic llegue a la API aunque el primer await todavía esté en vuelo.
    await waitFor(() =>
      expect(addToEstudioMembership).toHaveBeenCalledTimes(1),
    );
    expect(result.current.addToEstudioPending).toBe(true);
    expect(addToEstudioMembership).toHaveBeenCalledTimes(1);

    await act(async () => {
      resolveFirst?.({ added: 1, ids: ["inst-1"] });
      await Promise.resolve();
    });

    await waitFor(() =>
      expect(result.current.addToEstudioPending).toBe(false),
    );
    expect(upsertMembers).toHaveBeenCalledTimes(1);
    expect(runEstudioInstrumentsUpdate).toHaveBeenCalledTimes(1);
    expect(pushToast).toHaveBeenCalledWith("AAPL → Estudio · datos al día");
  });

  it("si el alta falla avisa por toast y libera la guarda", async () => {
    addToEstudioMembership.mockRejectedValue(new Error("API caída"));
    const pushToast = vi.fn();
    const { result } = renderHook(() =>
      useAddToEstudioAction({
        instrumentId: "inst-1",
        symbol: "AAPL",
        pushToast,
        upsertMembers: vi.fn(),
      }),
    );

    act(() => result.current.addToEstudio());
    await waitFor(() => expect(result.current.addToEstudioPending).toBe(false));
    expect(pushToast).toHaveBeenCalledWith(
      "AAPL · no se pudo dar de alta en Estudio: API caída",
    );
  });

  it("sin instrumento no llama a la API", () => {
    const { result } = renderHook(() =>
      useAddToEstudioAction({
        instrumentId: null,
        symbol: "AAPL",
        pushToast: vi.fn(),
        upsertMembers: vi.fn(),
      }),
    );
    act(() => result.current.addToEstudio());
    expect(addToEstudioMembership).not.toHaveBeenCalled();
  });
});

describe("useRefreshStudyAction", () => {
  it("un fallo de refresco muestra aviso en vez de rechazar en silencio", async () => {
    runEstudioInstrumentsUpdate.mockRejectedValue(new Error("timeout"));
    const pushToast = vi.fn();
    const invalidate = vi.fn(async () => undefined);
    const { result } = renderHook(() =>
      useRefreshStudyAction({
        instrumentId: "inst-1",
        symbol: "AAPL",
        pushToast,
        invalidate,
      }),
    );

    act(() => result.current.refreshStudy());
    await waitFor(() => expect(result.current.refreshPending).toBe(false));
    expect(pushToast).toHaveBeenCalledWith(
      "AAPL · no se pudo actualizar el estudio: timeout",
    );
    expect(invalidate).not.toHaveBeenCalled();
  });

  it("en éxito invalida estudios y no avisa error", async () => {
    runEstudioInstrumentsUpdate.mockResolvedValue(undefined);
    const pushToast = vi.fn();
    const invalidate = vi.fn(async () => undefined);
    const { result } = renderHook(() =>
      useRefreshStudyAction({
        instrumentId: "inst-1",
        symbol: "AAPL",
        pushToast,
        invalidate,
      }),
    );

    act(() => result.current.refreshStudy());
    await waitFor(() => expect(invalidate).toHaveBeenCalledTimes(1));
    expect(pushToast).not.toHaveBeenCalled();
  });
});
