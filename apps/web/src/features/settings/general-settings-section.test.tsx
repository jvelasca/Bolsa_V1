/**
 * Configuración → General: bloques por ámbito.
 *
 * - Apariencia y Mercado: preferencias de este dispositivo.
 * - Espacio de trabajo: resumen de solo lectura; editar se hace en el modal.
 */

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api", () => ({
  ApiError: class ApiError extends Error {},
  api: {
    getWorkspaces: vi.fn(async () => ({ data: [] })),
    updateWorkspace: vi.fn(),
    updateWorkspaceKeepalive: vi.fn(),
  },
}));

import { GeneralSettingsSection } from "@/features/settings/general-settings-section";
import { DEFAULT_WORKSPACE } from "@/stores/workspace-store-core";
import { useUiStore } from "@/stores/ui-store";
import { useWorkspaceStore } from "@/stores/workspace-store";

beforeEach(() => {
  localStorage.clear();
  useUiStore.setState({
    uiTheme: "dark",
    uiDensity: "comfortable",
    workspacePickerOpen: false,
  });
  useWorkspaceStore.setState({
    workspace: {
      ...DEFAULT_WORKSPACE,
      name: "Espacio QA",
      preferences: {
        ...DEFAULT_WORKSPACE.preferences,
        autoSave: false,
        openOnStartup: true,
      },
      updatedAt: "2026-10-29T10:00:00Z",
    },
    activeWorkspaceId: "ws-qa",
    workspaceSummaries: [
      {
        id: "ws-qa",
        name: "Espacio QA",
        isDefault: true,
        updatedAt: "2026-10-29T10:00:00Z",
      },
    ],
    hydrated: true,
  });
});

afterEach(() => {
  cleanup();
});

describe("GeneralSettingsSection — ámbitos", () => {
  it("separa Apariencia, Mercado y Espacio de trabajo", () => {
    render(<GeneralSettingsSection compact />);

    expect(screen.getByText("Apariencia")).toBeTruthy();
    expect(screen.getByText("Mercado")).toBeTruthy();
    expect(screen.getByText("Espacio de trabajo")).toBeTruthy();
  });

  it("el diseño de Mercado ya no se edita desde General", () => {
    render(<GeneralSettingsSection compact />);

    expect(screen.queryByLabelText(/diseño de mercado/i)).toBeNull();
    expect(screen.queryByText(/layout mercado/i)).toBeNull();
    expect(screen.queryByText(/restablecer paneles trading/i)).toBeNull();
  });

  it("no duplica los checkboxes del gestor de espacios", () => {
    render(<GeneralSettingsSection compact />);

    expect(screen.queryByRole("checkbox")).toBeNull();
    expect(screen.queryByText(/autoguardado en servidor/i)).toBeNull();
  });
});

describe("GeneralSettingsSection — apariencia", () => {
  it("cambiar el tema lo aplica al documento", () => {
    render(<GeneralSettingsSection compact />);

    fireEvent.change(screen.getByRole("combobox", { name: /^tema/i }), {
      target: { value: "light" },
    });

    expect(useUiStore.getState().uiTheme).toBe("light");
    expect(document.documentElement.dataset.theme).toBe("light");
  });

  it("cambiar la densidad usa etiquetas en español", () => {
    render(<GeneralSettingsSection compact />);

    expect(screen.getByRole("option", { name: "Cómoda" })).toBeTruthy();
    fireEvent.change(
      screen.getByRole("combobox", { name: /densidad de ui/i }),
      {
        target: { value: "compact" },
      },
    );

    expect(useUiStore.getState().uiDensity).toBe("compact");
    expect(document.documentElement.dataset.density).toBe("compact");
  });
});

describe("GeneralSettingsSection — resumen del espacio", () => {
  it("refleja el estado real del espacio activo", () => {
    render(<GeneralSettingsSection compact />);

    expect(screen.getByText("Espacio QA")).toBeTruthy();
    expect(screen.getByText("Desactivado")).toBeTruthy();
    expect(screen.getByText("Sí (reserva)")).toBeTruthy();
  });

  it("abre el gestor desde el resumen", () => {
    render(<GeneralSettingsSection compact />);

    fireEvent.click(
      screen.getByRole("button", { name: /gestionar espacios/i }),
    );

    expect(useUiStore.getState().workspacePickerOpen).toBe(true);
  });
});
