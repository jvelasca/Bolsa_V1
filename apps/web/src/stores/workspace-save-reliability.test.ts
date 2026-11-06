/**
 * Fiabilidad del guardado del workspace: concurrencia optimista (409), reintentos
 * con backoff y carreras entre el PUT y el cierre de pestañas.
 *
 * Regresión de Visualizados: si el usuario cerraba pestañas mientras el PUT
 * estaba en vuelo, el guardado anterior podía dejarlas vivas y el siguiente
 * arranque las resucitaba. Ahora la membresía se compara por CONJUNTO.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ChartTabState } from "@bolsa/shared";
import { DEFAULT_CHART_CONFIG } from "@bolsa/shared";
import { DEFAULT_WORKSPACE } from "@/stores/workspace-store-core";

const { MockApiError } = vi.hoisted(() => {
  class MockApiError extends Error {
    status: number;
    constructor(message: string, status: number) {
      super(message);
      this.status = status;
    }
  }
  return { MockApiError };
});

const updateWorkspace = vi.fn();
const getWorkspace = vi.fn();
const getWorkspaces = vi.fn(async () => ({ data: [] as unknown[] }));
const getDefaultWorkspace = vi.fn();
const deleteWorkspace = vi.fn(async () => undefined);
const updateWorkspaceKeepalive = vi.fn();
const closeWorkspaceCharts = vi.fn();

vi.mock("@/lib/api", () => ({
  ApiError: MockApiError,
  api: {
    updateWorkspace: (id: string, body: Record<string, unknown>) =>
      updateWorkspace(id, body),
    getWorkspace: (id: string) => getWorkspace(id),
    getWorkspaces: () => getWorkspaces(),
    getDefaultWorkspace: () => getDefaultWorkspace(),
    deleteWorkspace: (id: string) => deleteWorkspace(id),
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
import { workspacePayloadByteLength } from "@/stores/workspace-store-core";

type WorkspaceDoc = { charts?: Array<{ instrumentId: string }> };

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

function serverResponse(updatedAt: string, name = "Espacio") {
  return {
    data: {
      id: "ws-1",
      name,
      isDefault: false,
      document: DEFAULT_WORKSPACE,
      dockLayout: null,
      createdAt: "2026-01-01T00:00:00Z",
      updatedAt,
    },
  };
}

function resetStore(charts: ChartTabState[] = [], autoSave = true) {
  useWorkspaceStore.setState({
    workspace: {
      ...DEFAULT_WORKSPACE,
      id: "ws-1",
      name: "Espacio",
      charts,
      activeChartId: charts.at(-1)?.id ?? null,
      updatedAt: "2026-11-02T10:00:00.000Z",
      preferences: { ...DEFAULT_WORKSPACE.preferences, autoSave },
    },
    activeWorkspaceId: "ws-1",
    chartPersistBackup: null,
    chartListMembership: null,
    workspaceSummaries: [],
    hydrated: true,
    isDirty: true,
    isSaving: false,
    serverUpdatedAt: "2026-11-02T10:00:00+00:00",
    pendingClosedChartInstrumentIds: [],
    recents: ["ws-1"],
    loadError: null,
  });
}

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  vi.spyOn(window, "alert").mockImplementation(() => undefined);
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe("saveToServer — concurrencia optimista", () => {
  it("envía expectedUpdatedAt con la revisión que leyó", async () => {
    resetStore();
    updateWorkspace.mockResolvedValue(
      serverResponse("2026-11-02T10:00:05+00:00"),
    );

    await useWorkspaceStore.getState().saveToServer();

    const [, body] = updateWorkspace.mock.calls[0]!;
    expect(body.expectedUpdatedAt).toBe("2026-11-02T10:00:00+00:00");
    expect(useWorkspaceStore.getState().serverUpdatedAt).toBe(
      "2026-11-02T10:00:05+00:00",
    );
    expect(useWorkspaceStore.getState().isDirty).toBe(false);
  });

  it("409 → relee, refusiona y reintenta con la revisión vigente", async () => {
    resetStore([tab("t1", "SAN")]);
    updateWorkspace
      .mockRejectedValueOnce(new MockApiError("workspace_conflict", 409))
      .mockResolvedValueOnce(serverResponse("2026-11-02T10:01:00+00:00"));
    getWorkspace.mockResolvedValue({
      data: {
        id: "ws-1",
        name: "Espacio",
        isDefault: false,
        document: {
          ...DEFAULT_WORKSPACE,
          charts: [tab("s1", "SAN")],
          updatedAt: "2026-11-02T10:00:30.000Z",
        },
        dockLayout: null,
        createdAt: "2026-01-01T00:00:00Z",
        updatedAt: "2026-11-02T10:00:30+00:00",
      },
    });

    const ok = await useWorkspaceStore.getState().saveToServer();

    expect(ok).toBe(true);
    expect(getWorkspace).toHaveBeenCalledWith("ws-1");
    expect(updateWorkspace).toHaveBeenCalledTimes(2);
    const [, retryBody] = updateWorkspace.mock.calls[1]!;
    expect(retryBody.expectedUpdatedAt).toBe("2026-11-02T10:00:30+00:00");
    expect(useWorkspaceStore.getState().isDirty).toBe(false);
  });

  it("fallo de red → no lanza, sigue dirty y programa reintento", async () => {
    vi.useFakeTimers();
    resetStore();
    updateWorkspace.mockRejectedValue(new MockApiError("sin red", 0));

    const ok = await useWorkspaceStore.getState().saveToServer();
    expect(ok).toBe(false);
    expect(useWorkspaceStore.getState().isDirty).toBe(true);
    expect(window.alert).not.toHaveBeenCalled();

    updateWorkspace.mockResolvedValue(
      serverResponse("2026-11-02T10:00:10+00:00"),
    );
    await vi.advanceTimersByTimeAsync(2_000);
    await vi.runOnlyPendingTimersAsync();

    expect(updateWorkspace).toHaveBeenCalledTimes(2);
    expect(useWorkspaceStore.getState().isDirty).toBe(false);
  });
});

describe("saveToServer — cierre de pestañas durante el PUT", () => {
  it("reenvía el cierre que ocurrió con el PUT en vuelo", async () => {
    // autoSave off: el cierre no dispara su propio guardado y la carrera es determinista.
    resetStore([tab("t1", "SAN"), tab("t2", "BBVA")], false);
    let closedDuringSave = false;
    updateWorkspace.mockImplementation(async () => {
      if (!closedDuringSave) {
        closedDuringSave = true;
        // El usuario cierra una pestaña con el PUT en vuelo.
        useWorkspaceStore.getState().closeChartTab("t1");
      }
      return serverResponse("2026-11-02T10:00:20+00:00");
    });

    await useWorkspaceStore.getState().saveToServer();

    // 1º guardado: el documento que había al prepararse (SAN + BBVA).
    // 2º guardado (encolado): la membresía viva ya sin SAN.
    expect(updateWorkspace).toHaveBeenCalledTimes(2);
    const instrumentIdsOf = (callIndex: number) =>
      (
        (
          updateWorkspace.mock.calls[callIndex]?.[1] as {
            document: WorkspaceDoc;
          }
        ).document.charts ?? []
      ).map((item) => item.instrumentId);
    expect(instrumentIdsOf(0)).toEqual(["SAN", "BBVA"]);
    expect(instrumentIdsOf(1)).toEqual(["BBVA"]);
    expect(
      useWorkspaceStore.getState().workspace.charts.map((item) => item.id),
    ).toEqual(["t2"]);
  });

  it("un cambio de CONTENIDO durante el PUT también deja el espacio pendiente", async () => {
    // Regresión: `isDirty` solo comparaba el conjunto de instrumentos, así que
    // cambiar indicadores/tiempo mientras el PUT estaba en vuelo se daba por guardado.
    resetStore([tab("t1", "SAN")], false);
    let editedDuringSave = false;
    updateWorkspace
      .mockImplementationOnce(async () => {
        editedDuringSave = true;
        useWorkspaceStore.getState().updateChartTimeframe("1H");
        return serverResponse("2026-11-02T10:00:20+00:00");
      })
      // El guardado encolado no se resuelve: así la aserción no depende del microtask.
      .mockImplementationOnce(() => new Promise(() => undefined));

    await useWorkspaceStore.getState().saveToServer();

    expect(editedDuringSave).toBe(true);
    expect(updateWorkspace).toHaveBeenCalledTimes(2);
    expect(useWorkspaceStore.getState().isDirty).toBe(true);
  });
});

describe("saveToServer — Visualizados", () => {
  it("deriva visualizationEntries de las pestañas abiertas (sin dump obsoleto)", async () => {
    resetStore([tab("t1", "SAN"), tab("t2", "BBVA")], false);
    useWorkspaceStore.setState((state) => ({
      workspace: {
        ...state.workspace,
        list: {
          ...state.workspace.list,
          visualizationEntries: [
            {
              instrumentId: "SAN",
              symbol: "SAN",
              name: "Santander",
              firstViewedAt: "2026-01-01T00:00:00.000Z",
              lastViewedAt: "2026-01-01T00:00:00.000Z",
              viewCount: 3,
            },
            {
              instrumentId: "OBSOLETO",
              symbol: "OBS",
              name: "Cerrado hace días",
              firstViewedAt: "2026-01-01T00:00:00.000Z",
              lastViewedAt: "2026-01-01T00:00:00.000Z",
              viewCount: 1,
            },
          ],
        },
      },
    }));
    updateWorkspace.mockResolvedValue(
      serverResponse("2026-11-02T10:00:30+00:00"),
    );

    await useWorkspaceStore.getState().saveToServer();

    const [, body] = updateWorkspace.mock.calls[0]!;
    const entries = (
      body as {
        document: {
          list: {
            visualizationEntries: Array<{
              instrumentId: string;
              viewCount: number;
            }>;
          };
        };
      }
    ).document.list.visualizationEntries;

    expect(entries.map((entry) => entry.instrumentId)).toEqual(["SAN", "BBVA"]);
    // La metadata del instrumento que sigue abierto se conserva.
    expect(entries[0]?.viewCount).toBe(3);
  });
});

describe("flushWorkspaceOnUnload — cierre de página", () => {
  it("reenvía la revisión vigente para no pisar a otro cliente", () => {
    resetStore([tab("t1", "SAN")], false);

    useWorkspaceStore.getState().flushWorkspaceOnUnload();

    expect(updateWorkspaceKeepalive).toHaveBeenCalledTimes(1);
    const [, body] = updateWorkspaceKeepalive.mock.calls[0]!;
    expect(body.expectedUpdatedAt).toBe("2026-11-02T10:00:00+00:00");
  });

  it("con cierres pendientes envía solo el endpoint compacto", () => {
    resetStore([tab("t2", "BBVA")], false);
    useWorkspaceStore.setState({
      pendingClosedChartInstrumentIds: ["SAN"],
    });

    useWorkspaceStore.getState().flushWorkspaceOnUnload();

    expect(closeWorkspaceCharts).toHaveBeenCalledTimes(1);
    const [, closeBody] = closeWorkspaceCharts.mock.calls[0]!;
    expect(closeBody.instrumentIds).toEqual(["SAN"]);
    expect(closeBody.expectedUpdatedAt).toBe("2026-11-02T10:00:00+00:00");
    // Reenviar el documento completo en el mismo cierre reabriría la carrera.
    expect(updateWorkspaceKeepalive).not.toHaveBeenCalled();
  });
});

describe("workspacePayloadByteLength", () => {
  it("mide bytes UTF-8, no unidades UTF-16", () => {
    const body = { name: "ñandú", list: "Índice" };
    const encoded = new TextEncoder().encode(JSON.stringify(body)).length;

    expect(workspacePayloadByteLength(body)).toBe(encoded);
    // Documenta el defecto: .length subestimaba el body real del keepalive.
    expect(JSON.stringify(body).length).toBeLessThan(encoded);
  });

  it("devuelve infinito si el body no es serializable", () => {
    const cyclic: Record<string, unknown> = {};
    cyclic.self = cyclic;

    expect(workspacePayloadByteLength(cyclic)).toBe(Number.POSITIVE_INFINITY);
  });
});
