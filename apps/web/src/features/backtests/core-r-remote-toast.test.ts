import { describe, expect, it } from 'vitest';
import {
  parseRemoteEnqueueSignal,
  shouldToastRemoteEnqueue,
} from '@/features/backtests/core-r-remote-toast';

describe('shouldToastRemoteEnqueue', () => {
  it('silent when no signal or zero added', () => {
    expect(
      shouldToastRemoteEnqueue(
        { lastRemoteEnqueueAt: null, lastRemoteEnqueueAdded: 2 },
        null,
      ).shouldToast,
    ).toBe(false);
    expect(
      shouldToastRemoteEnqueue(
        { lastRemoteEnqueueAt: '2026-08-02T12:00:00.000Z', lastRemoteEnqueueAdded: 0 },
        null,
      ).shouldToast,
    ).toBe(false);
  });

  it('toasts when unseen', () => {
    const d = shouldToastRemoteEnqueue(
      { lastRemoteEnqueueAt: '2026-08-02T12:00:00.000Z', lastRemoteEnqueueAdded: 3 },
      null,
    );
    expect(d.shouldToast).toBe(true);
    expect(d.added).toBe(3);
  });

  it('silent when already seen same or newer', () => {
    expect(
      shouldToastRemoteEnqueue(
        { lastRemoteEnqueueAt: '2026-08-02T12:00:00.000Z', lastRemoteEnqueueAdded: 1 },
        '2026-08-02T12:00:00.000Z',
      ).shouldToast,
    ).toBe(false);
    expect(
      shouldToastRemoteEnqueue(
        { lastRemoteEnqueueAt: '2026-08-02T11:00:00.000Z', lastRemoteEnqueueAdded: 1 },
        '2026-08-02T12:00:00.000Z',
      ).shouldToast,
    ).toBe(false);
  });

  it('toasts when remote is newer than last seen', () => {
    expect(
      shouldToastRemoteEnqueue(
        { lastRemoteEnqueueAt: '2026-08-02T13:00:00.000Z', lastRemoteEnqueueAdded: 2 },
        '2026-08-02T12:00:00.000Z',
      ).shouldToast,
    ).toBe(true);
  });
});

describe('parseRemoteEnqueueSignal', () => {
  it('reads scheduler blob fields', () => {
    expect(
      parseRemoteEnqueueSignal({
        lastRemoteEnqueueAt: '2026-08-02T12:00:00.000Z',
        lastRemoteEnqueueAdded: 4,
      }),
    ).toEqual({
      lastRemoteEnqueueAt: '2026-08-02T12:00:00.000Z',
      lastRemoteEnqueueAdded: 4,
    });
  });
});
