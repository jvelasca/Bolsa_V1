import { useCallback } from "react";
import {
  CHART_CURSOR_BAR_ANCHOR,
  CHART_INSTRUMENT_BAR_ANCHOR,
  DEFAULT_CHART_CURSOR_FIELD_FAVORITES,
  DEFAULT_CHART_INSTRUMENT_FIELD_FAVORITES,
  type ChartCursorBarField,
  type ChartInstrumentBarField,
} from "@bolsa/shared";
import { useWorkspaceStore } from "@/stores/workspace-store";

export function useChartInstrumentFieldFavorites() {
  const favorites = useWorkspaceStore(
    (s) =>
      s.workspace.chartToolbarGlobal?.instrumentFieldFavorites ??
      DEFAULT_CHART_INSTRUMENT_FIELD_FAVORITES,
  );
  const toggle = useWorkspaceStore((s) => s.toggleInstrumentFieldFavorite);
  const toggleFavorite = useCallback(
    (field: ChartInstrumentBarField) => toggle(field),
    [toggle],
  );
  const isFavorite = useCallback(
    (field: ChartInstrumentBarField) => favorites.includes(field),
    [favorites],
  );
  return {
    favorites,
    toggleFavorite,
    isFavorite,
    anchor: CHART_INSTRUMENT_BAR_ANCHOR,
  };
}

export function useChartCursorFieldFavorites() {
  const favorites = useWorkspaceStore(
    (s) =>
      s.workspace.chartToolbarGlobal?.cursorFieldFavorites ??
      DEFAULT_CHART_CURSOR_FIELD_FAVORITES,
  );
  const toggle = useWorkspaceStore((s) => s.toggleCursorFieldFavorite);
  const toggleFavorite = useCallback(
    (field: ChartCursorBarField) => toggle(field),
    [toggle],
  );
  const isFavorite = useCallback(
    (field: ChartCursorBarField) => favorites.includes(field),
    [favorites],
  );
  return {
    favorites,
    toggleFavorite,
    isFavorite,
    anchor: CHART_CURSOR_BAR_ANCHOR,
  };
}
