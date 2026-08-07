/**
 * Tests — CORE-R scheduler prefs + due + shell scope.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  CORE_R_SCHEDULER_KEY,
  clampCoreRSchedulerInterval,
  coreRSchedulerDue,
  loadCoreRSchedulerPrefs,
  markCoreRSchedulerTick,
  resolveCoreRSchedulerListId,
  saveCoreRSchedulerPrefs,
} from '@/features/backtests/core-r-scheduler';

describe('core-r-scheduler', () => {
  beforeEach(() => {
    localStorage.removeItem(CORE_R_SCHEDULER_KEY);
  });

  it('defaults disabled · 60 min · shell scope', () => {
    const p = loadCoreRSchedulerPrefs();
    expect(p.enabled).toBe(false);
    expect(p.intervalMinutes).toBe(60);
    expect(p.lastTickAt).toBeNull();
    expect(p.listId).toBeNull();
    expect(p.scope).toBe('shell');
  });

  it('due when enabled and never ticked', () => {
    expect(
      coreRSchedulerDue({
        enabled: true,
        intervalMinutes: 60,
        lastTickAt: null,
        listId: 'L',
        scope: 'shell',
      }),
    ).toBe(true);
  });

  it('not due inside interval; due after', () => {
    const prefs = {
      enabled: true,
      intervalMinutes: 60,
      lastTickAt: new Date(Date.now() - 10 * 60_000).toISOString(),
      listId: 'L',
      scope: 'shell' as const,
    };
    expect(coreRSchedulerDue(prefs)).toBe(false);
    expect(coreRSchedulerDue(prefs, Date.now() + 55 * 60_000)).toBe(true);
  });

  it('persists tick stamp + listId', () => {
    saveCoreRSchedulerPrefs({
      enabled: true,
      intervalMinutes: 30,
      lastTickAt: null,
      listId: 'list-ibex',
      scope: 'shell',
    });
    const next = markCoreRSchedulerTick(loadCoreRSchedulerPrefs());
    expect(next.lastTickAt).toBeTruthy();
    expect(loadCoreRSchedulerPrefs().listId).toBe('list-ibex');
    expect(loadCoreRSchedulerPrefs().lastTickAt).toBe(next.lastTickAt);
  });

  it('prefers Estudio canónica when resolving listId', () => {
    expect(
      resolveCoreRSchedulerListId({
        estudioListId: 'estudio',
        monitorListId: 'ibex35',
        previousListId: 'old',
      }),
    ).toBe('estudio');
    expect(
      resolveCoreRSchedulerListId({
        estudioListId: null,
        estudioPersonalListId: 'est-1',
        monitorListId: 'ibex35',
        previousListId: 'old',
      }),
    ).toBe('est-1');
    expect(
      resolveCoreRSchedulerListId({
        estudioListId: null,
        monitorListId: 'ibex35',
        previousListId: 'old',
      }),
    ).toBe('ibex35');
  });

  it('clamps interval minutes', () => {
    expect(clampCoreRSchedulerInterval(1)).toBe(5);
    expect(clampCoreRSchedulerInterval(90)).toBe(90);
    expect(clampCoreRSchedulerInterval(10_000)).toBe(1440);
  });
});

describe('runCoreRSchedulerTick', () => {
  beforeEach(() => {
    localStorage.removeItem(CORE_R_SCHEDULER_KEY);
    vi.resetModules();
  });

  it('skips when disabled', async () => {
    const { runCoreRSchedulerTick } = await import(
      '@/features/backtests/core-r-scheduler-tick'
    );
    const res = await runCoreRSchedulerTick({ includePnl: false });
    expect(res?.skipped).toBe(true);
    expect(res?.reason).toBe('disabled');
  });

  it('skips when no listId', async () => {
    saveCoreRSchedulerPrefs({
      enabled: true,
      intervalMinutes: 60,
      lastTickAt: null,
      listId: null,
      scope: 'shell',
    });
    const { runCoreRSchedulerTick } = await import(
      '@/features/backtests/core-r-scheduler-tick'
    );
    const res = await runCoreRSchedulerTick({ includePnl: false });
    expect(res?.reason).toBe('no_list');
  });
});
