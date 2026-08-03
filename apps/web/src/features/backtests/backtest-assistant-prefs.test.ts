import { describe, expect, it } from 'vitest';
import {
  defaultAssistantPrefs,
  normalizeAssistantPrefs,
} from '@/features/backtests/backtest-assistant-prefs';

describe('assistant prefs', () => {
  it('defaults enable coach + auto advances + flow gates', () => {
    const d = defaultAssistantPrefs();
    expect(d.universe.runCoachOnEnter).toBe(true);
    expect(d.semifinal.optimizeTop3OnEnter).toBe(true);
    expect(d.lab.autoAdvanceWhenActiveTop).toBe(true);
    expect(d.coach.futureWeight).toBe(0.42);
    expect(d.fullCycleOnPlay).toBe(true);
    expect(d.universe.includeFinalistsInBattery).toBe(true);
    expect(d.coach.labEvenIfWeak).toBe(false);
    expect(d.coach.llmNarrate).toBe(true);
    expect(d.coach.autoAckOnCycle).toBe(true);
    expect(d.coach.pauseIfAckNeeded).toBe(false);
    expect(d.coach.requireAckBeforeLab).toBe(true);
    expect(d.coach.saveSemifinalSkipLab).toBe(false);
  });

  it('normalizes partial patches', () => {
    const n = normalizeAssistantPrefs({
      universe: { runCoachOnEnter: false },
      coach: {
        futureWeight: 0.55,
        labEvenIfWeak: true,
        llmNarrate: false,
        autoAckOnCycle: false,
        pauseIfAckNeeded: true,
        requireAckBeforeLab: false,
        saveSemifinalSkipLab: true,
      },
      fullCycleOnPlay: false,
    });
    expect(n.universe.runCoachOnEnter).toBe(false);
    expect(n.universe.selectAllGenerics).toBe(true);
    expect(n.universe.reuseLoteIfUnchanged).toBe(true);
    expect(n.universe.skipFreshIfUnchanged).toBe(true);
    expect(n.universe.includeMineStrategies).toBe(false);
    expect(n.universe.includeOptimizedStrategies).toBe(false);
    expect(n.universe.includeFinalistsInBattery).toBe(true);
    expect(n.coach.futureWeight).toBe(0.55);
    expect(n.coach.labEvenIfWeak).toBe(true);
    expect(n.coach.llmNarrate).toBe(false);
    expect(n.coach.autoAckOnCycle).toBe(false);
    expect(n.coach.pauseIfAckNeeded).toBe(true);
    expect(n.coach.requireAckBeforeLab).toBe(false);
    expect(n.coach.saveSemifinalSkipLab).toBe(true);
    expect(n.fullCycleOnPlay).toBe(false);
  });

  it('migrates legacy includeMineStrategies true → both Optimized and Mine', () => {
    const n = normalizeAssistantPrefs({
      universe: { includeMineStrategies: true },
    });
    expect(n.universe.includeMineStrategies).toBe(true);
    expect(n.universe.includeOptimizedStrategies).toBe(true);
  });

  it('keeps independent Optimized / Mine flags when both present', () => {
    const n = normalizeAssistantPrefs({
      universe: {
        includeMineStrategies: true,
        includeOptimizedStrategies: false,
      },
    });
    expect(n.universe.includeMineStrategies).toBe(true);
    expect(n.universe.includeOptimizedStrategies).toBe(false);
  });
});
