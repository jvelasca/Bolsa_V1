/**
 * Tests — fingerprint / reuse / merge Universo + Finalistas + Mis estrategias.
 */

import { describe, expect, it } from 'vitest';
import {
  buildCoachBatteryFingerprint,
  canReuseCoachLote,
  finalistMatrixRowIds,
  mergeUniverseTargetIds,
} from '@/features/backtests/backtest-coach-lote';

describe('buildCoachBatteryFingerprint', () => {
  it('is stable regardless of target id order', () => {
    const a = buildCoachBatteryFingerprint({
      contextFingerprint: 'inst|1y',
      targetRowIds: ['preset:b', 'preset:a'],
    });
    const b = buildCoachBatteryFingerprint({
      contextFingerprint: 'inst|1y',
      targetRowIds: ['preset:a', 'preset:b'],
    });
    expect(a).toBe(b);
    expect(a).toContain('preset:a,preset:b');
  });

  it('changes when context or set changes', () => {
    const base = buildCoachBatteryFingerprint({
      contextFingerprint: 'inst|1y',
      targetRowIds: ['preset:a'],
    });
    expect(
      buildCoachBatteryFingerprint({
        contextFingerprint: 'inst|6m',
        targetRowIds: ['preset:a'],
      }),
    ).not.toBe(base);
    expect(
      buildCoachBatteryFingerprint({
        contextFingerprint: 'inst|1y',
        targetRowIds: ['preset:a', 'preset:b'],
      }),
    ).not.toBe(base);
  });
});

describe('canReuseCoachLote', () => {
  const rows = [
    { rowId: 'preset:a', status: 'ok', runId: 'r1' },
    { rowId: 'preset:b', status: 'ok', runId: 'r2' },
    { rowId: 'preset:c', status: 'idle' },
  ];
  const fp = buildCoachBatteryFingerprint({
    contextFingerprint: 'inst|1y',
    targetRowIds: ['preset:a', 'preset:b'],
  });

  it('reuses when fingerprint matches and targets are ok', () => {
    expect(
      canReuseCoachLote({
        preferReuse: true,
        fingerprint: fp,
        lastFingerprint: fp,
        rows,
        targetRowIds: ['preset:a', 'preset:b'],
      }),
    ).toEqual({ reuse: true, reason: 'ok' });
  });

  it('does not reuse incomplete or force', () => {
    expect(
      canReuseCoachLote({
        preferReuse: true,
        fingerprint: fp,
        lastFingerprint: fp,
        rows,
        targetRowIds: ['preset:a', 'preset:c'],
      }).reason,
    ).toBe('incomplete_ok');
    expect(
      canReuseCoachLote({
        preferReuse: true,
        fingerprint: fp,
        lastFingerprint: fp,
        rows,
        targetRowIds: ['preset:a', 'preset:b'],
        forceResim: true,
      }).reason,
    ).toBe('force');
  });
});

describe('mergeUniverseTargetIds', () => {
  it('returns presets only by default', () => {
    expect(
      mergeUniverseTargetIds({
        presetIds: ['preset:a', 'preset:b'],
        savedRowIds: ['saved:1'],
        includeMine: false,
      }),
    ).toEqual(['preset:a', 'preset:b']);
  });

  it('unions Finalistas del valor when enabled', () => {
    expect(
      mergeUniverseTargetIds({
        presetIds: ['preset:a'],
        finalistRowIds: ['saved:top1', 'saved:top2'],
        includeFinalists: true,
        savedRowIds: ['saved:mine'],
        includeMine: false,
      }),
    ).toEqual(['preset:a', 'saved:top1', 'saved:top2']);
  });

  it('appends Mis estrategias when enabled, capped', () => {
    const merged = mergeUniverseTargetIds({
      presetIds: ['preset:a'],
      savedRowIds: ['saved:1', 'saved:2', 'preset:a'],
      includeMine: true,
      max: 2,
    });
    expect(merged).toEqual(['preset:a', 'saved:1']);
  });
});

describe('finalistMatrixRowIds', () => {
  it('maps strategyDefinitionId to saved: rowIds', () => {
    expect(
      finalistMatrixRowIds([
        { strategyDefinitionId: 'abc' },
        { strategyDefinitionId: 'abc' },
        { strategyDefinitionId: null },
        { strategyDefinitionId: 'def' },
      ]),
    ).toEqual(['saved:abc', 'saved:def']);
  });
});
