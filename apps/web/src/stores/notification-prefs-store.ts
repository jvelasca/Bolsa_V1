/**
 * Store UI: preferencias de notificación (toast / email Alarmas).
 * Persistido en localStorage vía notification-prefs helpers.
 */

import { create } from "zustand";
import {
  defaultNotificationPrefs,
  loadNotificationPrefs,
  saveNotificationPrefs,
  type NotificationPrefs,
} from "@/features/config/notification-prefs";

interface NotificationPrefsState extends NotificationPrefs {
  hydrate: () => void;
  setPrefs: (patch: Partial<NotificationPrefs>) => void;
  reset: () => void;
}

export const useNotificationPrefsStore = create<NotificationPrefsState>(
  (set, get) => ({
    ...loadNotificationPrefs(),
    hydrate: () => set({ ...loadNotificationPrefs() }),
    setPrefs: (patch) => {
      const next = saveNotificationPrefs({ ...get(), ...patch });
      set({ ...next });
    },
    reset: () => {
      const next = saveNotificationPrefs(defaultNotificationPrefs());
      set({ ...next });
    },
  }),
);
