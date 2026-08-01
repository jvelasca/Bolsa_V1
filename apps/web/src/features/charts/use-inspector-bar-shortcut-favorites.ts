import { useCallback } from 'react';
import {
  DEFAULT_CHART_INSPECTOR_BAR_SHORTCUT_FAVORITES,
  type ChartInspectorBarShortcutId,
} from '@bolsa/shared';
import { useWorkspaceStore } from '@/stores/workspace-store';

const EMPTY_INSPECTOR_BAR_SHORTCUT_FAVORITES: ChartInspectorBarShortcutId[] = [];

export function useInspectorBarShortcutFavorites() {
  const favorites = useWorkspaceStore(
    (s) =>
      s.workspace.chartToolbarGlobal?.inspectorBarShortcutFavorites ??
      EMPTY_INSPECTOR_BAR_SHORTCUT_FAVORITES,
  );
  const toggle = useWorkspaceStore((s) => s.toggleInspectorBarShortcutFavorite);
  const toggleFavorite = useCallback(
    (id: ChartInspectorBarShortcutId) => toggle(id),
    [toggle],
  );
  const isFavorite = useCallback(
    (id: ChartInspectorBarShortcutId) => favorites.includes(id),
    [favorites],
  );
  return {
    favorites,
    toggleFavorite,
    isFavorite,
    defaults: DEFAULT_CHART_INSPECTOR_BAR_SHORTCUT_FAVORITES,
  };
}
