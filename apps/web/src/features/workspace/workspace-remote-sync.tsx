import { useEffect } from "react";
import { useWorkspaceStore } from "@/stores/workspace-store";
const SYNC_INTERVAL_MS = 60_000;

/** Trae cambios del servidor (p. ej. dibujos desde otro PC en la LAN). */
export function WorkspaceRemoteSync() {
  const hydrated = useWorkspaceStore((s) => s.hydrated);
  const sync = useWorkspaceStore((s) => s.syncWorkspaceFromServer);

  useEffect(() => {
    if (!hydrated) return;

    const pull = () => {
      void sync();
    };

    pull();

    const onFocus = () => pull();
    const onVisible = () => {
      if (document.visibilityState === "visible") pull();
    };

    window.addEventListener("focus", onFocus);
    document.addEventListener("visibilitychange", onVisible);
    const timer = window.setInterval(() => {
      if (document.visibilityState === "visible") pull();
    }, SYNC_INTERVAL_MS);

    return () => {
      window.removeEventListener("focus", onFocus);
      document.removeEventListener("visibilitychange", onVisible);
      window.clearInterval(timer);
    };
  }, [hydrated, sync]);

  return null;
}
