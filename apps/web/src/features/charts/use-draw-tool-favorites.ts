import type { ChartDrawTool } from '@bolsa/shared';
import {
  IMPLEMENTED_DRAW_TOOLS,
  normalizeDrawToolFavorites,
  toggleDrawToolFavoriteList,
} from '@bolsa/shared';
import { useCallback, useMemo } from 'react';
import { useWorkspaceStore } from '@/stores/workspace-store';

export function useDrawToolFavorites() {
  const rawFavorites = useWorkspaceStore(
    (s) => s.workspace.chartToolbarGlobal?.drawToolFavorites,
  );
  const favorites = useMemo(
    () => normalizeDrawToolFavorites(rawFavorites, IMPLEMENTED_DRAW_TOOLS),
    [rawFavorites],
  );
  const toggle = useWorkspaceStore((s) => s.toggleDrawToolFavorite);

  const toggleFavorite = useCallback((tool: ChartDrawTool) => toggle(tool), [toggle]);
  const isFavorite = useCallback((tool: ChartDrawTool) => favorites.includes(tool), [favorites]);

  return { favorites, toggleFavorite, isFavorite };
}

export { toggleDrawToolFavoriteList };
