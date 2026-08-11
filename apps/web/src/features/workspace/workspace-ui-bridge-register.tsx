import { useEffect } from "react";
import { registerWorkspaceUiBridge } from "@/stores/workspace-ui-bridge";
import { useUiStore } from "@/stores/ui-store";

/** Enlaza ui-store con workspace-store vía bridge (sin import circular). */
export function WorkspaceUiBridgeRegister() {
  useEffect(() => {
    registerWorkspaceUiBridge({
      getOpenDrawingEditorId: () => useUiStore.getState().openDrawingEditorId,
      getChartInspectorActiveShortcutKey: () =>
        useUiStore.getState().chartInspectorActiveShortcutKey,
      setChartInspectorActiveShortcutKey: (key) =>
        useUiStore.getState().setChartInspectorActiveShortcutKey(key),
      setChartInspectorNav: (request) =>
        useUiStore.getState().setChartInspectorNav(request),
      focusDrawing: (drawingId) =>
        useUiStore.getState().focusDrawing(drawingId),
      setOpenDrawingEditorId: (id) =>
        useUiStore.getState().setOpenDrawingEditorId(id),
    });
  }, []);

  return null;
}
