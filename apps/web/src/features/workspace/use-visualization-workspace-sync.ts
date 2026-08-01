import { useEffect, useRef } from 'react';

import { useVisualizationStore } from '@/stores/visualization-store';
import { useWorkspaceStore } from '@/stores/workspace-store';

/** Sincroniza la lista Visualización entre el store en memoria y `workspace.list`. */
export function useVisualizationWorkspaceSync() {
  const hydrated = useWorkspaceStore((state) => state.hydrated);
  const workspaceId = useWorkspaceStore((state) => state.activeWorkspaceId);
  const persistedEntries = useWorkspaceStore((state) => state.workspace.list.visualizationEntries);
  const updateListConfig = useWorkspaceStore((state) => state.updateListConfig);
  const save = useWorkspaceStore((state) => state.save);
  const entries = useVisualizationStore((state) => state.entries);
  const replaceEntries = useVisualizationStore((state) => state.replaceEntries);

  const hydratedWorkspaceRef = useRef<string | null>(null);
  const skipPersistRef = useRef(false);

  useEffect(() => {
    if (!hydrated || !workspaceId) return;
    if (hydratedWorkspaceRef.current === workspaceId) return;

    hydratedWorkspaceRef.current = workspaceId;
    skipPersistRef.current = true;
    replaceEntries(
      useWorkspaceStore.getState().workspace.list.visualizationEntries ?? [],
    );
    queueMicrotask(() => {
      skipPersistRef.current = false;
    });
  }, [hydrated, replaceEntries, workspaceId]);

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
  }, [entries, hydrated, persistedEntries, save, updateListConfig, workspaceId]);
}
