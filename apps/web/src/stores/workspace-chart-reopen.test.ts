/**
 * W-1 — cerrar y reabrir una pestaña antes del flush de despedida.
 *
 * `pendingClosedChartInstrumentIds` acumula lo cerrado para que el `keepalive`
 * del cierre de navegador pueda podar esas pestañas con un body mínimo. Si el
 * instrumento se reabre y el id sigue en la lista, ese flush poda una pestaña
 * viva en el servidor. Reabrir (por cualquier vía) debe retirar el id.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ChartTabState } from "@bolsa/shared";
import { DEFAULT_CHART_CONFIG } from "@bolsa/shared";
import { DEFAULT_WORKSPACE } from "@/stores/workspace-store-core";

const closeWorkspaceCharts = vi.fn();
const updateWorkspaceKeepalive = vi.fn();

vi.mock("@/lib/api", () => ({
  ApiError: class MockApiError extends Error {},
  api: {
    updateWorkspace: vi.fn(),
    getWorkspace: vi.fn(),
    getWorkspaces: vi.fn(async () => ({ data: [] as unknown[] })),
    getDefaultWorkspace: vi.fn(),
    deleteWorkspace: vi.fn(async () => undefined),
    updateWorkspaceKeepalive: (id: string, body: Record<string, unknown>) =>
      updateWorkspaceKeepalive(id, body),
    closeWorkspaceCharts: (
      id: string,
      body: Record<string, unknown>,
      options?: { keepalive?: boolean },
    ) => closeWorkspaceCharts(id, body, options),
  },
}));

import { useWorkspaceStore } from "@/stores/workspace-store";

function tab(id: string, instrumentId: string): ChartTabState {
  return {
    id,
    instrumentId,
    label: instrumentId,
    timeframe: "1D",
    seriesType: "candles",
    chart: DEFAULT_CHART_CONFIG,
    indicatorInstances: [],
    drawings: [],
  } as ChartTabState;
}

function resetStore(
  charts: ChartTabState[] = [],
  pendingClosedChartInstrumentIds: string[] = [],
) {
  useWorkspaceStore.setState({
    workspace: {
      ...DEFAULT_WORKSPACE,
      id: "ws-1",
      name: "Espacio",
      charts,
      activeChartId: charts.at(-1)?.id ?? null,
      updatedAt: "2026-11-02T10:00:00.000Z",
      // autoSave off: los cierres no disparan su propio PUT y la lista de
      // pendientes se puede observar sin temporizadores de por medio.
      preferences: { ...DEFAULT_WORKSPACE.preferences, autoSave: false },
    },
    activeWorkspaceId: "ws-1",
    chartPersistBackup: null,
    chartListMembership: null,
    workspaceSummaries: [],
    hydrated: true,
    isDirty: false,
    isSaving: false,
    serverUpdatedAt: "2026-11-02T10:00:00+00:00",
    pendingClosedChartInstrumentIds,
    recents: ["ws-1"],
    loadError: null,
  });
}

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
});

describe("W-1 — reabrir una pestaña retira su cierre pendiente", () => {
  it("cerrar y reabrir no deja el id: el flush de despedida no poda una pestaña viva", () => {
    resetStore([tab("t1", "SAN")]);
    const store = useWorkspaceStore.getState();

    store.closeChartTab("t1");
    expect(
      useWorkspaceStore.getState().pendingClosedChartInstrumentIds,
    ).toEqual(["SAN"]);

    useWorkspaceStore.getState().openChartTab("SAN", "SAN");
    expect(
      useWorkspaceStore.getState().pendingClosedChartInstrumentIds,
    ).toEqual([]);

    useWorkspaceStore.getState().flushWorkspaceOnUnload();
    expect(closeWorkspaceCharts).not.toHaveBeenCalled();
    // Sin pendientes, la despedida vuelve a ser el documento completo.
    expect(updateWorkspaceKeepalive).toHaveBeenCalledTimes(1);
  });

  it("reabrir una pestaña que ya existe limpia un pendiente heredado", () => {
    resetStore([tab("t1", "SAN")], ["SAN", "BBVA"]);
    const returnedId = useWorkspaceStore.getState().openChartTab("SAN", "SAN");

    expect(returnedId).toBe("t1");
    // BBVA sigue pendiente: solo se retira lo que vuelve a estar abierto.
    expect(
      useWorkspaceStore.getState().pendingClosedChartInstrumentIds,
    ).toEqual(["BBVA"]);
    // Y no se duplica la pestaña del instrumento reabierto.
    expect(
      useWorkspaceStore.getState().workspace.charts.map((item) => item.id),
    ).toEqual(["t1"]);
  });

  it("focusInstrumentFromList también retira el pendiente del instrumento", () => {
    resetStore([], ["SAN", "BBVA"]);

    useWorkspaceStore.getState().focusInstrumentFromList("l1", "SAN", "SAN");

    expect(
      useWorkspaceStore.getState().pendingClosedChartInstrumentIds,
    ).toEqual(["BBVA"]);
  });

  it("focusInstrumentsFromList retira todos los ids que reabre", () => {
    resetStore([], ["SAN", "BBVA", "ITX"]);

    useWorkspaceStore.getState().focusInstrumentsFromList("l1", [
      { instrumentId: "SAN", label: "SAN" },
      { instrumentId: "BBVA", label: "BBVA" },
    ]);

    // ITX no se ha reabierto: su cierre sigue pendiente.
    expect(
      useWorkspaceStore.getState().pendingClosedChartInstrumentIds,
    ).toEqual(["ITX"]);
    expect(
      useWorkspaceStore
        .getState()
        .workspace.charts.map((item) => item.instrumentId),
    ).toEqual(["SAN", "BBVA"]);
  });

  it("cerrar otra pestaña después de reabrir mantiene solo el cierre real", () => {
    resetStore([tab("t1", "SAN"), tab("t2", "BBVA")]);

    useWorkspaceStore.getState().closeChartTab("t1");
    useWorkspaceStore.getState().openChartTab("SAN", "SAN");
    useWorkspaceStore.getState().closeChartTab("t2");

    expect(
      useWorkspaceStore.getState().pendingClosedChartInstrumentIds,
    ).toEqual(["BBVA"]);

    useWorkspaceStore.getState().flushWorkspaceOnUnload();
    const [, closeBody] = closeWorkspaceCharts.mock.calls[0]!;
    expect(closeBody.instrumentIds).toEqual(["BBVA"]);
  });
});
