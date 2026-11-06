/**
 * Gestor de espacios de trabajo (modal del chip superior).
 *
 * Cubre las superficies que el rediseño separa: catálogo, preferencias del
 * servidor, diseño del dispositivo y estados de carga/error.
 */

import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const updateWorkspace = vi.fn(
  async (id: string, body: Record<string, unknown>) => ({
    data: {
      id,
      name: String(body.name ?? "Espacio uno"),
      isDefault: Boolean(body.isDefault),
      document: {},
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
const deleteWorkspace = vi.fn(async (_id: string) => undefined);

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
    getWorkspace: vi.fn(),
    getDefaultWorkspace: vi.fn(),
    deleteWorkspace: (id: string) => deleteWorkspace(id),
    createWorkspace: vi.fn(),
    listInvestorProfiles: vi.fn(async () => ({ data: [] })),
  },
}));

import { WorkspacePickerDialog } from "@/features/workspace/workspace-picker-dialog";
import { DEFAULT_WORKSPACE } from "@/stores/workspace-store-core";
import { useUiStore } from "@/stores/ui-store";
import { useWorkspaceStore } from "@/stores/workspace-store";

const SUMMARIES = [
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
];

function seedStore(overrides: Record<string, unknown> = {}) {
  useWorkspaceStore.setState({
    workspace: {
      ...DEFAULT_WORKSPACE,
      id: "ws-1",
      name: "Espacio uno",
      preferences: { ...DEFAULT_WORKSPACE.preferences, autoSave: true },
    },
    activeWorkspaceId: "ws-1",
    chartPersistBackup: null,
    workspaceSummaries: SUMMARIES,
    hydrated: true,
    isDirty: false,
    isSaving: false,
    recents: ["ws-1"],
    loadError: null,
    ...overrides,
  });
  useUiStore.setState({ workspacePickerOpen: true });
}

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  seedStore();
});

afterEach(() => {
  cleanup();
  useUiStore.setState({ workspacePickerOpen: false });
});

describe("WorkspacePickerDialog — estructura", () => {
  it("lista el catálogo y separa preferencias de servidor y diseño del dispositivo", () => {
    render(<WorkspacePickerDialog />);

    expect(screen.getByRole("dialog")).toBeTruthy();
    expect(screen.getByText("Espacio uno")).toBeTruthy();
    expect(screen.getByText("Espacio dos")).toBeTruthy();
    expect(screen.getByText("Preferencias del espacio activo")).toBeTruthy();
    expect(screen.getByText("Diseño en este dispositivo")).toBeTruthy();
    expect(
      screen.getByRole("button", { name: /restablecer paneles trading/i }),
    ).toBeTruthy();
  });

  it("muestra el estado de la plantilla de gráficos nuevos", () => {
    render(<WorkspacePickerDialog />);
    expect(
      screen.getByText(/sin plantilla: los gráficos nuevos usan los valores/i),
    ).toBeTruthy();
    expect(
      screen.getByRole("button", {
        name: /usar el gráfico activo como plantilla/i,
      }),
    ).toBeTruthy();
  });
});

describe("WorkspacePickerDialog — preferencias", () => {
  it("desactivar el autoguardado se persiste en el servidor", async () => {
    render(<WorkspacePickerDialog />);

    fireEvent.click(
      screen.getByRole("checkbox", { name: /autoguardado al cambiar layout/i }),
    );

    await waitFor(() => expect(updateWorkspace).toHaveBeenCalledTimes(1));
    const [, body] = updateWorkspace.mock.calls[0]!;
    const document = body.document as { preferences: { autoSave: boolean } };
    expect(document.preferences.autoSave).toBe(false);
    expect(
      screen.getByText(/autoguardado desactivado y guardado/i),
    ).toBeTruthy();
  });

  it("marcar preferido escribe isDefault y no el documento", async () => {
    render(<WorkspacePickerDialog />);

    fireEvent.click(
      screen.getByRole("checkbox", { name: /preferido al arrancar/i }),
    );

    await waitFor(() => expect(updateWorkspace).toHaveBeenCalledTimes(1));
    const [id, body] = updateWorkspace.mock.calls[0]!;
    expect(id).toBe("ws-1");
    expect(body).toEqual({ isDefault: true });
  });
});

describe("WorkspacePickerDialog — exportar", () => {
  it("exporta sin marcar el espacio como guardado", () => {
    vi.stubGlobal("URL", {
      createObjectURL: vi.fn(() => "blob:mock"),
      revokeObjectURL: vi.fn(),
    });
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(
      () => undefined,
    );
    seedStore({ isDirty: true });

    render(<WorkspacePickerDialog />);
    fireEvent.click(screen.getByRole("button", { name: /exportar json/i }));

    expect(useWorkspaceStore.getState().isDirty).toBe(true);
    expect(screen.getByText(/exportar no guarda/i)).toBeTruthy();
    expect(updateWorkspace).not.toHaveBeenCalled();
  });
});

describe("WorkspacePickerDialog — errores y teclado", () => {
  it("distingue error de carga de catálogo vacío y ofrece reintentar", async () => {
    seedStore({
      loadError: "Network down",
      workspaceSummaries: [],
      hydrated: true,
    });

    render(<WorkspacePickerDialog />);

    expect(screen.getByRole("alert").textContent).toContain("Network down");
    expect(screen.queryByText(/aún no hay espacios/i)).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: /reintentar/i }));
    await waitFor(() => expect(getWorkspaces).toHaveBeenCalledTimes(1));
  });

  it("Escape en el renombrado cancela solo el renombrado", () => {
    render(<WorkspacePickerDialog />);

    fireEvent.click(
      screen.getByRole("button", { name: "Renombrar Espacio uno" }),
    );
    const input = screen.getByRole("textbox", {
      name: /nuevo nombre para espacio uno/i,
    });
    fireEvent.keyDown(input, { key: "Escape" });

    // El diálogo sigue montado: Escape no debía propagarse al `Dialog`.
    expect(screen.getByRole("dialog")).toBeTruthy();
    expect(useUiStore.getState().workspacePickerOpen).toBe(true);
    expect(screen.queryByRole("textbox")).toBeNull();
  });

  it("el borrado pide confirmación y muestra el error del servidor", async () => {
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);
    deleteWorkspace.mockRejectedValueOnce(
      new Error("No se puede borrar el último espacio"),
    );
    render(<WorkspacePickerDialog />);

    fireEvent.click(
      screen.getByRole("button", { name: "Eliminar Espacio dos" }),
    );

    expect(confirmSpy).toHaveBeenCalled();
    await waitFor(() =>
      expect(screen.getByRole("alert").textContent).toContain(
        "No se puede borrar el último espacio",
      ),
    );
  });
});
