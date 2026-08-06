/**
 * Hidrata membresía Estudio (visualization-store) desde lista API canónica.
 * Montar una vez en PlatformShell.
 */

import { useEffect, useRef } from 'react';
import { hydrateEstudioMembershipFromApi } from '@/features/trading/estudio-membership';

export function EstudioApiSync() {
  const ran = useRef(false);
  useEffect(() => {
    if (ran.current) return;
    ran.current = true;
    void hydrateEstudioMembershipFromApi();
  }, []);
  return null;
}
