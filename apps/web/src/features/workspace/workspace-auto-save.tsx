import { useEffect, useRef } from "react";
import { useWorkspaceStore } from "@/stores/workspace-store";

/** Intenta guardar dibujos al cerrar la pestaña o la aplicación. */
export function WorkspaceAutoSave() {
  const isDirty = useWorkspaceStore((s) => s.isDirty);
  const autoSave = useWorkspaceStore((s) => s.workspace.preferences.autoSave);
  const hydrated = useWorkspaceStore((s) => s.hydrated);
  const workspaceUpdatedAt = useWorkspaceStore((s) => s.workspace.updatedAt);
  const requestAutoSave = useWorkspaceStore((s) => s.requestAutoSave);
  const timerRef = useRef<number | null>(null);

  useEffect(() => {
    const flush = () => {
      useWorkspaceStore.getState().flushWorkspaceOnUnload();
    };
    window.addEventListener("beforeunload", flush);
    window.addEventListener("pagehide", flush);
    return () => {
      window.removeEventListener("beforeunload", flush);
      window.removeEventListener("pagehide", flush);
    };
  }, []);

  useEffect(() => {
    if (!hydrated || !isDirty || !autoSave) return;
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = window.setTimeout(() => {
      timerRef.current = null;
      requestAutoSave();
    }, 50);
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [hydrated, isDirty, autoSave, workspaceUpdatedAt, requestAutoSave]);

  return null;
}
