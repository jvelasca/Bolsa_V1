import { useCallback } from "react";
import { DEFAULT_INDICATOR_TEMPLATE_FAVORITES } from "@bolsa/shared";
import { useWorkspaceStore } from "@/stores/workspace-store";

export function useChartIndicatorTemplateFavorites() {
  const favorites = useWorkspaceStore(
    (s) =>
      s.workspace.chartToolbarGlobal?.indicatorTemplateFavorites ??
      DEFAULT_INDICATOR_TEMPLATE_FAVORITES,
  );
  const toggleInWorkspace = useWorkspaceStore(
    (s) => s.toggleIndicatorTemplateFavorite,
  );

  const toggleFavorite = useCallback(
    (templateId: string) => {
      toggleInWorkspace(templateId);
    },
    [toggleInWorkspace],
  );

  const isFavorite = useCallback(
    (templateId: string) => favorites.includes(templateId),
    [favorites],
  );

  return { favorites, toggleFavorite, isFavorite };
}
