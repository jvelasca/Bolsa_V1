import { describe, expect, it } from 'vitest';
import {
  fullCyclePlayTitle,
  isLabZoneTerminal,
  instrumentTopIsDurable,
  labEmptyZonesStatus,
  labNoImproveStatus,
  labWatchdogStatus,
  resolveFullCycleSaveDecision,
  shouldAutoHandoffLab,
  shouldWaitBeforeFinalistsAutoSave,
  universeEmptyStatus,
  coachNeedsHumanAck,
} from '@/features/backtests/backtest-assistant-full-cycle';

describe('instrumentTopIsDurable', () => {
  it('is false when top is missing or slots lack known strategies', () => {
    expect(instrumentTopIsDurable(null, new Set(['a']))).toBe(false);
    expect(
      instrumentTopIsDurable(
        { slots: [{ strategyDefinitionId: 'gone' }] },
        new Set(['alive']),
      ),
    ).toBe(false);
  });

  it('is true when at least one slot strategy still exists', () => {
    expect(
      instrumentTopIsDurable(
        {
          slots: [
            { strategyDefinitionId: 'gone' },
            { strategyDefinitionId: 'alive' },
          ],
        },
        new Set(['alive']),
      ),
    ).toBe(true);
  });
});

describe('coachNeedsHumanAck', () => {
  it('flags weak and discrepancy', () => {
    expect(coachNeedsHumanAck('weak')).toBe(true);
    expect(coachNeedsHumanAck('discrepancy')).toBe(true);
    expect(coachNeedsHumanAck('aligned')).toBe(false);
    expect(coachNeedsHumanAck(null)).toBe(false);
  });
});

describe('shouldAutoHandoffLab', () => {
  it('requires full cycle + all done + improvements', () => {
    expect(
      shouldAutoHandoffLab({
        fullCycleActive: true,
        allZonesDone: true,
        improvedCount: 2,
        alreadyTriggered: false,
      }),
    ).toBe(true);
    expect(
      shouldAutoHandoffLab({
        fullCycleActive: true,
        allZonesDone: true,
        improvedCount: 0,
        alreadyTriggered: false,
      }),
    ).toBe(false);
    expect(
      shouldAutoHandoffLab({
        fullCycleActive: false,
        allZonesDone: true,
        improvedCount: 2,
        alreadyTriggered: false,
      }),
    ).toBe(false);
  });
});

describe('resolveFullCycleSaveDecision', () => {
  it('saves active only post-lab with improvements and canSave', () => {
    expect(
      resolveFullCycleSaveDecision({
        postLab: true,
        labImprovedCount: 1,
        canSaveTop: true,
      }).action,
    ).toBe('save_active');
  });

  it('keeps previous active when lab did not improve and TOP exists', () => {
    const d = resolveFullCycleSaveDecision({
      postLab: true,
      labImprovedCount: 0,
      canSaveTop: true,
      existingTopStatus: 'active',
    });
    expect(d.action).toBe('skip_keep_previous');
  });

  it('saves first write when lab did not improve and no TOP in BD', () => {
    expect(
      resolveFullCycleSaveDecision({
        postLab: true,
        labImprovedCount: 0,
        canSaveTop: true,
        hasExistingTop: false,
      }).action,
    ).toBe('save_active');
  });

  it('saves first write when existing TOP is orphan (hasExistingTop false)', () => {
    expect(
      resolveFullCycleSaveDecision({
        postLab: true,
        labImprovedCount: 0,
        canSaveTop: true,
        existingTopStatus: 'active',
        hasExistingTop: false,
      }).action,
    ).toBe('save_active');
  });

  it('skips when cannot save top', () => {
    expect(
      resolveFullCycleSaveDecision({
        postLab: true,
        labImprovedCount: 2,
        canSaveTop: false,
      }).action,
    ).toBe('skip_no_candidates');
  });
});

describe('labNoImproveStatus', () => {
  it('messages only when done without improvements', () => {
    expect(labNoImproveStatus(0, 3)).toMatch(/sin Mejor/i);
    expect(labNoImproveStatus(1, 3)).toBeNull();
  });
});

describe('isLabZoneTerminal', () => {
  it('treats no-job and failed as terminal (anti-hang)', () => {
    expect(
      isLabZoneTerminal({
        hasSeed: true,
        hasJob: false,
        hasResult: false,
        activityPhase: null,
      }),
    ).toBe(true);
    expect(
      isLabZoneTerminal({
        hasSeed: true,
        hasJob: true,
        hasResult: false,
        activityPhase: 'failed',
      }),
    ).toBe(true);
    expect(
      isLabZoneTerminal({
        hasSeed: true,
        hasJob: true,
        hasResult: false,
        activityPhase: 'pending',
      }),
    ).toBe(false);
    expect(
      isLabZoneTerminal({
        hasSeed: true,
        hasJob: true,
        hasResult: true,
        activityPhase: 'pending',
      }),
    ).toBe(true);
  });
});

describe('cycle hang statuses', () => {
  it('exposes skip messages for empty universe / lab / watchdog', () => {
    expect(universeEmptyStatus('0 OK')).toMatch(/0 OK/);
    expect(labEmptyZonesStatus()).toMatch(/sin zonas/i);
    expect(labWatchdogStatus()).toMatch(/timeout/i);
  });
});

describe('shouldWaitBeforeFinalistsAutoSave', () => {
  it('waits while note empty after battery (ACS race)', () => {
    expect(
      shouldWaitBeforeFinalistsAutoSave({
        running: false,
        okCount: 3,
        recommendationCount: 0,
        postLabRecsWithRunId: 0,
        postLab: true,
      }),
    ).toBe(true);
  });

  it('does not wait when TOP has runIds', () => {
    expect(
      shouldWaitBeforeFinalistsAutoSave({
        running: false,
        okCount: 3,
        recommendationCount: 3,
        postLabRecsWithRunId: 3,
        postLab: true,
      }),
    ).toBe(false);
  });
});

describe('fullCyclePlayTitle', () => {
  it('labels Play according to pref', () => {
    expect(fullCyclePlayTitle(true)).toMatch(/Probar genéricas/i);
    expect(fullCyclePlayTitle(false)).toMatch(/siguiente paso/i);
  });
});
