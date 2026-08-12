/**
 * Estado del espacio de trabajo de trading — persistido en servidor (`/api/workspaces`).
 *
 * ## Producto (UI)
 * - Cabecera: chip con el nombre → abre el gestor (`WorkspacePickerDialog`).
 * - Arranque: último `activeWorkspaceId` local; si no, espacio `isDefault` (preferido); si no, el primero.
 * - Nuevo = documento en blanco; Duplicar = clona el activo (gráficos/listas/dibujos + dock).
 *
 * ## Persistencia
 * - Servidor: documento (`WorkspaceDocument`). `dockLayout` en API es legado (chrome por dispositivo).
 * - Local: `bolsa-workspace-meta` (`activeWorkspaceId`, `recents`, `chartPersistBackup`).
 * - Preferencias: `autoSave`, `openOnStartup` (→ `isDefault` al guardar).
 *
 * Este fichero es solo la pieza compositiva: las acciones viven en *slices*
 * (workspace-slice-*) y los helpers de módulo en `workspace-store-core`.
 *
 * @see docs/WORKSPACE_PERSISTENCE.md
 * @see apps/web/src/features/workspace/workspace-picker-dialog.tsx
 */
import { create } from "zustand";
import { persist } from "zustand/middleware";
import {
  type WorkspaceState,
  type WorkspaceSet,
  DEFAULT_WORKSPACE,
  chartPersistBackupFrom,
} from "./workspace-store-core";
import { layoutSlice } from "./workspace-slice-layout";
import { chartsSlice } from "./workspace-slice-charts";
import { indicatorsSlice } from "./workspace-slice-indicators";
import { drawingsSlice } from "./workspace-slice-drawings";
import { toolbarSlice } from "./workspace-slice-toolbar";
import { listSlice } from "./workspace-slice-list";
import { accountSlice } from "./workspace-slice-account";
import type { ChartTabState } from "@bolsa/shared";

export const useWorkspaceStore = create<WorkspaceState>()(
  persist(
    (set, get) => {
      const setSlice = set as WorkspaceSet;
      const initial = {
        workspace: DEFAULT_WORKSPACE,
        activeWorkspaceId: null,
        chartPersistBackup: null,
        chartListMembership: null,
        workspaceSummaries: [],
        hydrated: false,
        isDirty: false,
        isSaving: false,
        recents: [],
      };
      return {
        ...initial,
        ...layoutSlice(get, setSlice),
        ...chartsSlice(get, setSlice),
        ...indicatorsSlice(get, setSlice),
        ...drawingsSlice(get, setSlice),
        ...toolbarSlice(get, setSlice),
        ...listSlice(get, setSlice),
        ...accountSlice(get, setSlice),
      } as WorkspaceState;
    },
    {
      name: "bolsa-workspace-meta",
      partialize: (state) => ({
        activeWorkspaceId: state.activeWorkspaceId,
        recents: state.recents,
        chartPersistBackup: chartPersistBackupFrom(state.workspace),
      }),
      merge: (persisted, current) => {
        const p = persisted as Partial<WorkspaceState> | undefined;
        return {
          ...current,
          activeWorkspaceId: p?.activeWorkspaceId ?? null,
          recents: p?.recents ?? [],
          chartPersistBackup: p?.chartPersistBackup ?? null,
        };
      },
    },
  ),
);

export function useActiveChartTab(): ChartTabState | null {
  return useWorkspaceStore((state) => {
    const { charts, activeChartId } = state.workspace;
    return charts.find((tab) => tab.id === activeChartId) ?? charts[0] ?? null;
  });
}
