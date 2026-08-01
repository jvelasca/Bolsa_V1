/**
 * Tests — secuencia ACS-like: ACK¹ → Lab → Revalidar → Finalistas.
 * Reproduce el bug del doble Play (fingerprint) y el guardado con ACK.
 */

import { describe, expect, it } from 'vitest';
import {
  isCoach1AckSatisfied,
  isFinalistsSavedStatusMessage,
  isSemifinalShortcutStatusMessage,
  resolveAssistantAckPolicy,
  resolveCoach1AdvanceAction,
  sequenceExpectsFinalistsSave,
  shouldReenterUniverseToLabChain,
} from '@/features/backtests/assistant-cycle-orchestrator';
import { resolveFullCycleSaveDecision } from '@/features/backtests/backtest-assistant-full-cycle';

const gateOk = { advance: true as const, reason: 'Coach¹ discrepancy · avance a Lab' };
const gateWeakSkip = {
  advance: false as const,
  reason: 'Coach¹ débil · check «pasar si débil» OFF · Finalistas intactos',
};

describe('ACS-like Coach¹ advance', () => {
  it('with Auto-ACK ON does not wait for checkbox (no doble Play)', () => {
    const action = resolveCoach1AdvanceAction({
      gate: gateOk,
      confidence: 'discrepancy',
      requireAckBeforeLab: true,
      ackReady: false,
      autoAckOnCycle: true,
      pauseIfAckNeeded: false,
      saveSemifinalSkipLab: false,
    });
    expect(action.type).toBe('go_lab');
  });

  it('with Pausar ACK waits until checkbox', () => {
    expect(
      resolveCoach1AdvanceAction({
        gate: gateOk,
        confidence: 'discrepancy',
        requireAckBeforeLab: true,
        ackReady: false,
        autoAckOnCycle: true,
        pauseIfAckNeeded: true,
        saveSemifinalSkipLab: false,
      }).type,
    ).toBe('wait_ack1');

    expect(
      resolveCoach1AdvanceAction({
        gate: gateOk,
        confidence: 'discrepancy',
        requireAckBeforeLab: true,
        ackReady: true,
        autoAckOnCycle: true,
        pauseIfAckNeeded: true,
        saveSemifinalSkipLab: false,
      }).type,
    ).toBe('go_lab');
  });

  it('weak without labEvenIfWeak skips (gate)', () => {
    expect(
      resolveCoach1AdvanceAction({
        gate: gateWeakSkip,
        confidence: 'weak',
        requireAckBeforeLab: true,
        ackReady: true,
        autoAckOnCycle: true,
        pauseIfAckNeeded: false,
        saveSemifinalSkipLab: false,
      }).type,
    ).toBe('skip_lab');
  });

  it('re-enters chain after ACK¹ when fingerprint was consumed', () => {
    expect(
      shouldReenterUniverseToLabChain({
        fingerprintMatches: true,
        pendingAck1: true,
        ackSatisfied: true,
      }),
    ).toBe(true);
    expect(
      shouldReenterUniverseToLabChain({
        fingerprintMatches: true,
        pendingAck1: true,
        ackSatisfied: false,
      }),
    ).toBe(false);
    expect(
      shouldReenterUniverseToLabChain({
        fingerprintMatches: true,
        pendingAck1: false,
        ackSatisfied: true,
      }),
    ).toBe(false);
  });
});

describe('ACS-like Finalists save after ACK final', () => {
  it('saves when Lab improved + ACK final (auto or manual)', () => {
    expect(
      sequenceExpectsFinalistsSave({
        postLab: true,
        labImprovedCount: 2,
        needsAck: true,
        ackReady: true,
        autoAckOnCycle: true,
        pauseIfAckNeeded: false,
        recommendationCount: 3,
      }).shouldSave,
    ).toBe(true);

    expect(
      sequenceExpectsFinalistsSave({
        postLab: true,
        labImprovedCount: 2,
        needsAck: true,
        ackReady: false,
        autoAckOnCycle: true,
        pauseIfAckNeeded: false,
        recommendationCount: 3,
      }).shouldSave,
    ).toBe(true);

    expect(
      resolveFullCycleSaveDecision({
        postLab: true,
        labImprovedCount: 2,
        canSaveTop: true,
      }).action,
    ).toBe('save_active');
  });

  it('blocks save without Lab improve (política)', () => {
    expect(
      sequenceExpectsFinalistsSave({
        postLab: true,
        labImprovedCount: 0,
        needsAck: true,
        ackReady: true,
        autoAckOnCycle: false,
        pauseIfAckNeeded: true,
        recommendationCount: 3,
      }),
    ).toEqual({ shouldSave: false, blockedBy: 'no_lab_improve' });
  });

  it('detects saved status messages from auto-save', () => {
    expect(
      isFinalistsSavedStatusMessage(
        'Ciclo: Mejor(es) Lab + Coach² OK → Finalistas lab_validated.',
      ),
    ).toBe(true);
    expect(
      isSemifinalShortcutStatusMessage('Ciclo: TOP semifinal guardado · Lab omitido (atajo).'),
    ).toBe(true);
  });

  it('ACK policy: config ⋯ is the only ACK source (no duplicate checkbox)', () => {
    expect(
      resolveAssistantAckPolicy({
        autoAckOnCycle: true,
        pauseIfAckNeeded: false,
      }),
    ).toEqual({ mode: 'auto', showHumanCheckbox: false });
    expect(
      resolveAssistantAckPolicy({
        autoAckOnCycle: true,
        pauseIfAckNeeded: true,
      }),
    ).toEqual({ mode: 'human', showHumanCheckbox: true });
    expect(
      resolveAssistantAckPolicy({
        autoAckOnCycle: false,
        pauseIfAckNeeded: false,
      }),
    ).toEqual({ mode: 'human', showHumanCheckbox: true });
    expect(
      isCoach1AckSatisfied({
        needsAck: true,
        ackReady: false,
        autoAckOnCycle: true,
        pauseIfAckNeeded: false,
      }),
    ).toBe(true);
  });

  it('full sequence story: wait → ack → lab → save', () => {
    const wait = resolveCoach1AdvanceAction({
      gate: gateOk,
      confidence: 'discrepancy',
      requireAckBeforeLab: true,
      ackReady: false,
      autoAckOnCycle: false,
      pauseIfAckNeeded: true,
      saveSemifinalSkipLab: false,
    });
    expect(wait.type).toBe('wait_ack1');

    expect(
      shouldReenterUniverseToLabChain({
        fingerprintMatches: true,
        pendingAck1: true,
        ackSatisfied: false,
      }),
    ).toBe(false);

    expect(
      isCoach1AckSatisfied({
        needsAck: true,
        ackReady: true,
        autoAckOnCycle: false,
        pauseIfAckNeeded: true,
      }),
    ).toBe(true);
    expect(
      shouldReenterUniverseToLabChain({
        fingerprintMatches: true,
        pendingAck1: true,
        ackSatisfied: true,
      }),
    ).toBe(true);

    const go = resolveCoach1AdvanceAction({
      gate: gateOk,
      confidence: 'discrepancy',
      requireAckBeforeLab: true,
      ackReady: true,
      autoAckOnCycle: false,
      pauseIfAckNeeded: true,
      saveSemifinalSkipLab: false,
    });
    expect(go.type).toBe('go_lab');

    const save = resolveFullCycleSaveDecision({
      postLab: true,
      labImprovedCount: 3,
      canSaveTop: true,
    });
    expect(save.action).toBe('save_active');
    expect(isFinalistsSavedStatusMessage(`Ciclo: ${save.reason}`)).toBe(true);
  });
});
