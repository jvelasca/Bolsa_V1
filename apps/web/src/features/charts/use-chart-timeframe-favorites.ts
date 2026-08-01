import { useCallback } from 'react';
import {
  DEFAULT_CHART_TIMEFRAME_FAVORITES,
  toggleChartTimeframeFavoriteList,
  type ChartTimeframe,
} from '@bolsa/shared';
import { useWorkspaceStore } from '@/stores/workspace-store';

export function useChartTimeframeFavorites() {
  const favorites = useWorkspaceStore(
    (s) =>
      s.workspace.chartToolbarGlobal?.timeframeFavorites ?? DEFAULT_CHART_TIMEFRAME_FAVORITES,
  );
  const toggleInWorkspace = useWorkspaceStore((s) => s.toggleChartTimeframeFavorite);

  const toggleFavorite = useCallback(
    (timeframe: ChartTimeframe) => {
      toggleInWorkspace(timeframe);
    },
    [toggleInWorkspace],
  );

  const isFavorite = useCallback(
    (timeframe: ChartTimeframe) => favorites.includes(timeframe),
    [favorites],
  );

  return { favorites, toggleFavorite, isFavorite };
}

export { toggleChartTimeframeFavoriteList };
