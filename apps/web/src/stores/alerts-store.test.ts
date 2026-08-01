/**
 * Tests — toasts con acción opcional (CORE-R → Monitor).
 */

import { beforeEach, describe, expect, it } from 'vitest';
import { useAlertsStore } from '@/stores/alerts-store';

describe('alerts-store toast action', () => {
  beforeEach(() => {
    useAlertsStore.setState({ toasts: [] });
  });

  it('stores optional open-monitor action', () => {
    useAlertsStore.getState().pushToast('CORE-R · 2 valores', {
      action: { type: 'open_help_backtesting_monitor', label: 'Abrir Monitor' },
    });
    const t = useAlertsStore.getState().toasts[0];
    expect(t?.message).toMatch(/CORE-R/);
    expect(t?.action?.type).toBe('open_help_backtesting_monitor');
    expect(t?.action?.label).toBe('Abrir Monitor');
  });

  it('defaults action to null', () => {
    useAlertsStore.getState().pushToast('hola');
    expect(useAlertsStore.getState().toasts[0]?.action).toBeNull();
  });
});
