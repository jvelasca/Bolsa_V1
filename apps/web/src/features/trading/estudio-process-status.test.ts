import { describe, expect, it } from 'vitest';
import {
  formatEstudioProcessTimestamp,
  resolveLaneState,
  resolveEstudioProcessStatus,
  summarizeEstudioProcessLanes,
} from '@/features/trading/estudio-process-status';
import {
  ESTUDIO_LANE_STAMPS_KEY,
  touchEstudioLaneStamp,
} from '@/features/trading/estudio-lane-stamps';
import type { EstudioSupervisionPrefs } from '@/features/trading/estudio-supervision';

const basePrefs = (over: Partial<EstudioSupervisionPrefs> = {}): EstudioSupervisionPrefs => ({
  schemaVersion: 2,
  enabled: true,
  intervalMinutes: 1440,
  vigilanceMinutes: 1440,
  freshnessMinutes: 1440,
  rediscoverMinutes: 30 * 1440,
  rediscoverBudgetPerTick: 5,
  rediscoverCursor: 0,
  lastFreshnessTickAt: null,
  lastRediscoverTickAt: null,
  ...over,
});

describe('estudio-process-status', () => {
  it('resolveLaneState empty / ok / stale / running', () => {
    const now = Date.parse('2026-08-06T12:00:00Z');
    expect(resolveLaneState(null, 1440, false, now)).toBe('empty');
    expect(resolveLaneState('2026-08-06T10:00:00Z', 1440, false, now)).toBe('ok');
    expect(resolveLaneState('2026-08-04T10:00:00Z', 1440, false, now)).toBe('stale');
    expect(resolveLaneState('2026-08-04T10:00:00Z', 1440, true, now)).toBe('running');
  });

  it('resolveEstudioProcessStatus builds three lanes', () => {
    const now = Date.parse('2026-08-06T12:00:00Z');
    const view = resolveEstudioProcessStatus({
      instrumentId: 'inst-1',
      prefs: basePrefs(),
      nowMs: now,
      localFreshnessMap: {
        'inst-1|1d': {
          fingerprint: 'fp',
          lastSearchAt: '2026-08-06T08:00:00Z',
          timeframe: '1d',
        },
      },
      runningLane: 'freshness',
    });
    expect(view.lanes).toHaveLength(3);
    expect(view.lastLabAt).toBe('2026-08-06T08:00:00Z');
    expect(view.lanes.find((l) => l.id === 'freshness')?.state).toBe('running');
    expect(view.lanes.find((l) => l.id === 'vigilance')?.state).toBe('empty');
  });

  it('formatEstudioProcessTimestamp', () => {
    expect(formatEstudioProcessTimestamp(null)).toBe('—');
  });

  it('vigilance ok when local stamp exists (sin cola CORE-R)', () => {
    localStorage.removeItem(ESTUDIO_LANE_STAMPS_KEY);
    touchEstudioLaneStamp('inst-1', 'vigilance', '2026-08-06T11:00:00Z');
    const now = Date.parse('2026-08-06T12:00:00Z');
    const view = resolveEstudioProcessStatus({
      instrumentId: 'inst-1',
      prefs: basePrefs(),
      nowMs: now,
      localFreshnessMap: {},
    });
    expect(view.lanes.find((l) => l.id === 'vigilance')?.state).toBe('ok');
    expect(view.lastCoreRAt).toBe('2026-08-06T11:00:00Z');
    expect(view.lanes.find((l) => l.id === 'vigilance')?.title).toContain(
      'Vigilia: supervisa mandato',
    );
  });

  it('summarizeEstudioProcessLanes short labels', () => {
    localStorage.removeItem(ESTUDIO_LANE_STAMPS_KEY);
    const now = Date.parse('2026-08-06T12:00:00Z');
    const empty = resolveEstudioProcessStatus({
      instrumentId: 'sum-empty',
      prefs: basePrefs(),
      nowMs: now,
      localFreshnessMap: {},
    });
    expect(summarizeEstudioProcessLanes(empty.lanes).text).toBe('sin sync');

    const partial = resolveEstudioProcessStatus({
      instrumentId: 'sum-partial',
      prefs: basePrefs(),
      nowMs: now,
      localFreshnessMap: {
        'sum-partial|1d': {
          fingerprint: 'fp',
          lastSearchAt: '2026-08-06T08:00:00Z',
          timeframe: '1d',
        },
      },
    });
    // Lab ok → F y R al día; vigilia empty → toca V
    expect(summarizeEstudioProcessLanes(partial.lanes).text).toBe('toca V');

    touchEstudioLaneStamp('sum-ok', 'vigilance', '2026-08-06T11:00:00Z');
    const allOk = resolveEstudioProcessStatus({
      instrumentId: 'sum-ok',
      prefs: basePrefs(),
      nowMs: now,
      localFreshnessMap: {
        'sum-ok|1d': {
          fingerprint: 'fp',
          lastSearchAt: '2026-08-06T08:00:00Z',
          timeframe: '1d',
        },
      },
    });
    expect(summarizeEstudioProcessLanes(allOk.lanes)).toMatchObject({
      text: 'al día',
      tone: 'ok',
    });
  });
});
