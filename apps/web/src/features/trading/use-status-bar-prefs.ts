/**
 * Preferencias de la barra de estado (reactivas vía `useSyncExternalStore`).
 */

import { useSyncExternalStore } from "react";
import {
  getStatusBarPrefsServerSnapshot,
  getStatusBarPrefsSnapshot,
  setShowProviderHealth,
  subscribeStatusBarPrefs,
  toggleStatusItem,
  type StatusBarPrefs,
  type StatusItemId,
} from "@/features/trading/status-bar-prefs";

export function useStatusBarPrefs(): StatusBarPrefs {
  return useSyncExternalStore(
    subscribeStatusBarPrefs,
    getStatusBarPrefsSnapshot,
    getStatusBarPrefsServerSnapshot,
  );
}

export function useToggleStatusItem(): (
  id: StatusItemId,
  visible: boolean,
) => void {
  return (id, visible) => {
    toggleStatusItem(id, visible);
  };
}

export function useSetShowProviderHealth(): (show: boolean) => void {
  return (show) => {
    setShowProviderHealth(show);
  };
}
