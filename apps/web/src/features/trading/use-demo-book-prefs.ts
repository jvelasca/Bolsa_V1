/**
 * Preferencias del libro operativo (MANUAL/SEMI/AUTO) reactivas vía `useSyncExternalStore`.
 * Notifica en la misma pestaña al `saveDemoBookPrefs` / `patchDemoBookPrefs`.
 *
 * @see docs/engineering/trading-operativa-panel-2026-08-04.md
 */

import { useSyncExternalStore } from 'react';
import {
  getDemoBookPrefsServerSnapshot,
  getDemoBookPrefsSnapshot,
  subscribeDemoBookPrefs,
  type DemoBookPrefs,
} from '@/features/trading/demo-book-prefs';

export function useDemoBookPrefs(): DemoBookPrefs {
  return useSyncExternalStore(
    subscribeDemoBookPrefs,
    getDemoBookPrefsSnapshot,
    getDemoBookPrefsServerSnapshot,
  );
}
