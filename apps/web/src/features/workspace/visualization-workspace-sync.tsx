import { useVisualizationWorkspaceSync } from '@/features/workspace/use-visualization-workspace-sync';

/** Persiste la lista Visualización en el documento del workspace. */
export function VisualizationWorkspaceSync() {
  useVisualizationWorkspaceSync();
  return null;
}
