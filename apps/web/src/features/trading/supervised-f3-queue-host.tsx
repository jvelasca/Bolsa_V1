/**
 * Host SEMI Confirm F3 — hydrate cola desde BD al cambiar cuenta Activa.
 */

import { useEffect } from 'react';
import {
  ensureSupervisedF3Hydrated,
  wireSupervisedF3PushSubscriptions,
} from '@/features/trading/supervised-f3-sync';
import { useActiveAccountStore } from '@/stores/active-account-store';

export function SupervisedF3QueueHost() {
  const activeAccountId = useActiveAccountStore((s) => s.activeAccountId);

  useEffect(() => {
    wireSupervisedF3PushSubscriptions();
  }, []);

  useEffect(() => {
    if (!activeAccountId) return;
    void ensureSupervisedF3Hydrated(activeAccountId);
  }, [activeAccountId]);

  return null;
}
