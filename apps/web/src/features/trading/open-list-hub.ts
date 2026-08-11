/**
 * Abre el hub de listas (gestión) sin acoplar ui-store ↔ workspace-store.
 */
import { useTradingLayoutStore } from "@/stores/trading-layout-store";
import { useWorkspaceStore } from "@/stores/workspace-store";

/** Menú Ver → Gestionar listas; también desde ui-store.openListHub. */
export function openListHubWorkspaceAction(): void {
  const workspace = useWorkspaceStore.getState();
  workspace.updateListConfig({ watchlistTab: "lists" });
  workspace.requestAutoSave();
  useTradingLayoutStore.getState().ensureListsOpen();
}
