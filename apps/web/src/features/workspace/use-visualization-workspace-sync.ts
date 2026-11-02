import { useEffect, useRef } from "react";

import { reconcileVisualizadosToOpenCharts } from "@/features/trading/lists-tab/use-chart-visualization-sync";
import { useVisualizationStore } from "@/stores/visualization-store";
import { useWorkspaceStore } from "@/stores/workspace-store";

/** Mismos instrumentos (orden incluido): la lista es espejo 1:1 de pestañas. */
function sameInstrumentIds(
  a: ReadonlyArray<{ instrumentId: string }> | undefined,
  b: ReadonlyArray<{ instrumentId: string }> | undefined,
): boolean {
  const left = a ?? [];
  const right = b ?? [];
  if (left.length !== right.length) return false;
  return left.every(
    (entry, index) => entry.instrumentId === right[index]?.instrumentId,
  );
}

/**
 * Persiste Visualizados (= pestañas abiertas) en el workspace.
 * No restaura el dump legacy `visualizationEntries` (pudo ser el Estudio de 100+).
 * SoT al cargar: charts abiertos → reconcile.
 *
 * La reconciliación de arranque NO reescribe el workspace si el conjunto ya
 * coincide: antes marcaba dirty y guardaba en cada carga, y ese guardado
 * reinyectaba las pestañas que el usuario acababa de cerrar.
 */
export function useVisualizationWorkspaceSync() {
  const hydrated = useWorkspaceStore((state) => state.hydrated);
  const workspaceId = useWorkspaceStore((state) => state.activeWorkspaceId);
  const persistedEntries = useWorkspaceStore(
    (state) => state.workspace.list.visualizationEntries,
  );
  const updateListConfig = useWorkspaceStore((state) => state.updateListConfig);
  const save = useWorkspaceStore((state) => state.save);
  const entries = useVisualizationStore((state) => state.entries);

  const hydratedWorkspaceRef = useRef<string | null>(null);
  const skipPersistRef = useRef(false);

  useEffect(() => {
    if (!hydrated || !workspaceId) return;
    if (hydratedWorkspaceRef.current === workspaceId) return;

    hydratedWorkspaceRef.current = workspaceId;
    skipPersistRef.current = true;
    // Ignora dump legacy; alinea a pestañas abiertas del workspace ya hidratado.
    reconcileVisualizadosToOpenCharts();
    const pruned = useVisualizationStore.getState().entries;
    const persisted =
      useWorkspaceStore.getState().workspace.list.visualizationEntries;
    if (!sameInstrumentIds(pruned, persisted)) {
      // Solo si de verdad cambió: persistir el conjunto podado.
      updateListConfig({ visualizationEntries: pruned });
    }
    queueMicrotask(() => {
      skipPersistRef.current = false;
    });
  }, [hydrated, workspaceId, updateListConfig]);

  useEffect(() => {
    if (!hydrated || !workspaceId || skipPersistRef.current) return;

    const persisted = JSON.stringify(persistedEntries ?? []);
    const current = JSON.stringify(entries);
    if (persisted === current) return;

    const timer = window.setTimeout(() => {
      updateListConfig({ visualizationEntries: entries });
      save();
    }, 600);

    return () => window.clearTimeout(timer);
  }, [
    entries,
    hydrated,
    persistedEntries,
    save,
    updateListConfig,
    workspaceId,
  ]);
}
