import { useCallback } from "react";
import {
  DEFAULT_CHART_SERIES_TYPE_FAVORITES,
  type ChartSeriesType,
} from "@bolsa/shared";
import { useWorkspaceStore } from "@/stores/workspace-store";

export function useChartSeriesTypeFavorites() {
  const favorites = useWorkspaceStore(
    (s) =>
      s.workspace.chartToolbarGlobal?.seriesTypeFavorites ??
      DEFAULT_CHART_SERIES_TYPE_FAVORITES,
  );
  const toggleInWorkspace = useWorkspaceStore(
    (s) => s.toggleChartSeriesTypeFavorite,
  );

  const toggleFavorite = useCallback(
    (seriesType: ChartSeriesType) => {
      toggleInWorkspace(seriesType);
    },
    [toggleInWorkspace],
  );

  const isFavorite = useCallback(
    (seriesType: ChartSeriesType) => favorites.includes(seriesType),
    [favorites],
  );

  return { favorites, toggleFavorite, isFavorite };
}
