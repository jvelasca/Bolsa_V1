import { useEffect, useRef } from "react";
import { createUnloadFlushGuard } from "@/lib/unload-flush-guard";
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
    // `beforeunload` y `pagehide` llegan los dos en Chromium: el guard evita que el
    // flush (close + keepalive) se envíe por duplicado, y se rearma si la página
    // vuelve a quedar visible (p. ej. restaurada desde bfcache).
    const guard = createUnloadFlushGuard(() => {
      useWorkspaceStore.getState().flushWorkspaceOnUnload();
    });
    const flush = () => guard.run();
    const rearm = () => {
      if (!document.hidden) guard.reset();
    };
    window.addEventListener("beforeunload", flush);
    window.addEventListener("pagehide", flush);
    window.addEventListener("pageshow", rearm);
    document.addEventListener("visibilitychange", rearm);
    return () => {
      window.removeEventListener("beforeunload", flush);
      window.removeEventListener("pagehide", flush);
      window.removeEventListener("pageshow", rearm);
      document.removeEventListener("visibilitychange", rearm);
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
