import { describe, expect, it } from 'vitest';
import {
  formatScanHitAlarmToast,
  isAlarmSafeMode,
  pickAlarmPolicyId,
} from '@/features/screeners/tracker-alarms';
import type { ScanHitDto } from '@bolsa/shared';

const hit: ScanHitDto = {
  instrumentId: 'i1',
  symbol: 'ACS',
  name: 'ACS',
  signal: {
    id: 's1',
    instrumentId: 'i1',
    timestamp: '2026-07-31T00:00:00Z',
    kind: 'entry_long',
    strategyDefinitionId: 'st',
    strategyVersion: 1,
    barIndex: 10,
    price: 42.5,
  },
};

describe('tracker-alarms', () => {
  it('formats entry toast', () => {
    expect(formatScanHitAlarmToast(hit)).toContain('ACS');
    expect(formatScanHitAlarmToast(hit)).toContain('Entrada long');
    expect(formatScanHitAlarmToast(hit)).toContain('42.50');
  });

  it('only inform/alert are safe', () => {
    expect(isAlarmSafeMode('inform_only')).toBe(true);
    expect(isAlarmSafeMode('alert')).toBe(true);
    expect(isAlarmSafeMode('paper_auto')).toBe(false);
  });

  it('prefers alert policy', () => {
    expect(
      pickAlarmPolicyId([
        { id: 'a', mode: 'inform_only', enabled: true },
        { id: 'b', mode: 'alert', enabled: true },
        { id: 'c', mode: 'paper_auto', enabled: true },
      ]),
    ).toBe('b');
  });
});
