/**
 * Preferencias del espacio de trabajo (WS-*): qué se guarda en el servidor,
 * qué NO debe tocar `saveToServer` y qué se limpia al cambiar de espacio.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { DEFAULT_WORKSPACE } from "@/stores/workspace-store-core";
import { nextCopyName } from "@/stores/workspace-store-core";

const updateWorkspace = vi.fn(
  async (_id: string, body: Record<string, unknown>) => ({
    data: {
      id: _id,
      name: String(body.name ?? "Espacio"),
      isDefault: Boolean(body.isDefault),
      document: DEFAULT_WORKSPACE,
      dockLayout: null,
      createdAt: "2026-01-01T00:00:00Z",
      updatedAt: "2026-01-02T00:00:00Z",
    },
  }),
);
const updateWorkspaceKeepalive = vi.fn();
const getWorkspaces = vi.fn(async () => ({
  data: [
    {
      id: "ws-1",
      name: "Espacio uno",
      isDefault: false,
      updatedAt: "2026-01-02T00:00:00Z",
    },
    {
      id: "ws-2",
      name: "Espacio dos",
      isDefault: true,
      updatedAt: "2026-01-03T00:00:00Z",
    },
  ],
}));
const getWorkspace = vi.fn(async (id: string) => ({
  data: {
    id,
    name: id === "ws-2" ? "Espacio dos" : "Espacio uno",
    isDefault: id === "ws-2",
    document: { ...DEFAULT_WORKSPACE, id, name: id },
    dockLayout: null,
    createdAt: "2026-01-01T00:00:00Z",
    updatedAt: "2026-01-02T00:00:00Z",
  },
}));
const getDefaultWorkspace = vi.fn(async () => getWorkspace("ws-2"));
const deleteWorkspace = vi.fn(async () => undefined);

vi.mock("@/lib/api", () => ({
  ApiError: class ApiError extends Error {},
  api: {
    updateWorkspace: (id: string, body: Record<string, unknown>) =>
      updateWorkspace(id, body),
    updateWorkspaceKeepalive: (
      id: string,
      body: Record<string, unknown>,
    ): void => {
      updateWorkspaceKeepalive(id, body);
    },
    getWorkspaces: () => getWorkspaces(),
    getWorkspace: (id: string) => getWorkspace(id),
    getDefaultWorkspace: () => getDefaultWorkspace(),
    deleteWorkspace: (id: string) => deleteWorkspace(id),
  },
}));

import { useWorkspaceStore } from "@/stores/workspace-store";
import { applyServerWorkspace } from "@/stores/workspace-store-core";

/** Documento con una pestaña abierta (para detectar backups heredados). */
function workspaceWithChart(instrumentId: string) {
  return {
    ...DEFAULT_WORKSPACE,
    id: "ws-1",
    name: "Espacio uno",
    charts: [
      {
        id: `tab-${instrumentId}`,
        instrumentId,
        label: instrumentId,
        timeframe: "1D",
      } as unknown as (typeof DEFAULT_WORKSPACE.charts)[number],
    ],
    activeChartId: `tab-${instrumentId}`,
  };
}

function resetStore() {
  useWorkspaceStore.setState({
    workspace: DEFAULT_WORKSPACE,
    activeWorkspaceId: "ws-1",
    chartPersistBackup: null,
    chartListMembership: null,
    workspaceSummaries: [],
    hydrated: true,
    isDirty: false,
    isSaving: false,
    recents: ["ws-1"],
    loadError: null,
  });
}

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  resetStore();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("saveToServer — WS-D2 (la estrella no salta al guardar)", () => {
  it("no envía isDefault: el preferido solo cambia con setPreferred", async () => {
    await useWorkspaceStore.getState().saveToServer();

    expect(updateWorkspace).toHaveBeenCalledTimes(1);
    const [, body] = updateWorkspace.mock.calls[0]!;
    expect(body).not.toHaveProperty("isDefault");
    expect(body).toHaveProperty("document");
  });

  it("flushWorkspaceOnUnload tampoco envía isDefault", () => {
    useWorkspaceStore.getState().flushWorkspaceOnUnload();

    expect(updateWorkspaceKeepalive).toHaveBeenCalledTimes(1);
    const [, body] = updateWorkspaceKeepalive.mock.calls[0]!;
    expect(body).not.toHaveProperty("isDefault");
  });

  it("setPreferred marca is_default en el servidor y refresca el catálogo", async () => {
    await useWorkspaceStore.getState().setPreferred(true);

    expect(updateWorkspace).toHaveBeenCalledTimes(1);
    const [, body] = updateWorkspace.mock.calls[0]!;
    expect(body).toEqual({ isDefault: true });
    expect(getWorkspaces).toHaveBeenCalled();
    expect(
      useWorkspaceStore.getState().workspace.preferences.openOnStartup,
    ).toBe(true);
  });

  it("applyServerWorkspace toma openOnStartup de is_default", () => {
    const applied = applyServerWorkspace({
      id: "ws-9",
      name: "Nueve",
      isDefault: false,
      document: {
        ...DEFAULT_WORKSPACE,
        preferences: { ...DEFAULT_WORKSPACE.preferences, openOnStartup: true },
      },
      dockLayout: null,
    });
    expect(applied.workspace.preferences.openOnStartup).toBe(false);
  });
});

describe("setAutoSave — WS-D3 (apagarlo también se persiste)", () => {
  it("guarda de inmediato aunque acabe de desactivarse el autoguardado", async () => {
    await useWorkspaceStore.getState().setAutoSave(false);

    expect(updateWorkspace).toHaveBeenCalledTimes(1);
    const [, body] = updateWorkspace.mock.calls[0]!;
    const document = body.document as { preferences: { autoSave: boolean } };
    expect(document.preferences.autoSave).toBe(false);
    expect(useWorkspaceStore.getState().workspace.preferences.autoSave).toBe(
      false,
    );
  });
});

describe("cambiar de espacio — WS-D4 (sin backups heredados)", () => {
  it("switchWorkspace reescribe el backup local con el documento nuevo", async () => {
    useWorkspaceStore.setState({
      workspace: workspaceWithChart("SAN.MC"),
      chartPersistBackup: {
        charts: workspaceWithChart("SAN.MC").charts,
      } as unknown as ReturnType<
        typeof useWorkspaceStore.getState
      >["chartPersistBackup"],
    });

    await useWorkspaceStore.getState().switchWorkspace("ws-2");

    const state = useWorkspaceStore.getState();
    expect(state.activeWorkspaceId).toBe("ws-2");
    expect(state.chartPersistBackup?.charts ?? []).toHaveLength(0);
  });

  it("olvida el espacio borrado en recents y recarga el preferido", async () => {
    useWorkspaceStore.setState({
      activeWorkspaceId: "ws-1",
      recents: ["ws-1", "ws-2"],
    });

    await useWorkspaceStore.getState().deleteWorkspaceById("ws-1");

    const state = useWorkspaceStore.getState();
    expect(state.recents).toEqual(["ws-2"]);
    expect(deleteWorkspace).toHaveBeenCalledWith("ws-1");
    expect(getDefaultWorkspace).toHaveBeenCalled();
  });
});

describe("exportar — WS-D1 (exportar no es guardar)", () => {
  it("mantiene isDirty para que el pull no pise cambios sin guardar", () => {
    const createObjectURL = vi.fn(() => "blob:mock");
    const revokeObjectURL = vi.fn();
    vi.stubGlobal("URL", { createObjectURL, revokeObjectURL });
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(
      () => undefined,
    );
    useWorkspaceStore.setState({ isDirty: true });

    useWorkspaceStore.getState().exportJson();

    expect(createObjectURL).toHaveBeenCalledTimes(1);
    expect(useWorkspaceStore.getState().isDirty).toBe(true);
    expect(updateWorkspace).not.toHaveBeenCalled();
  });
});

describe("nextCopyName — WS-D5 (copias sin nombres repetidos)", () => {
  it("usa (copia) cuando está libre", () => {
    expect(nextCopyName("Mercado", ["Mercado"])).toBe("Mercado (copia)");
  });

  it("incrementa hasta encontrar un nombre libre", () => {
    expect(
      nextCopyName("Mercado", [
        "Mercado",
        "Mercado (copia)",
        "Mercado (copia 2)",
      ]),
    ).toBe("Mercado (copia 3)");
  });

  it("normaliza una copia de copia al nombre raíz", () => {
    expect(nextCopyName("Mercado (copia 4)", ["Mercado (copia 4)"])).toBe(
      "Mercado (copia)",
    );
  });

  it("ignora mayúsculas y espacios sobrantes", () => {
    expect(nextCopyName("Mercado", ["  mercado (COPIA)  "])).toBe(
      "Mercado (copia 2)",
    );
  });
});
