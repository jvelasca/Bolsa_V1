/**
 * Tests — fullBleedMovie en sesión DÍA D (no se hidrata a true).
 */

import { beforeEach, describe, expect, it } from 'vitest';
import { useDiaDTradingSessionStore } from '@/stores/dia-d-trading-session-store';

describe('dia-d fullBleedMovie', () => {
  beforeEach(() => {
    localStorage.removeItem('bolsa-dia-d-trading-session-v1');
    useDiaDTradingSessionStore.setState({ session: null });
  });

  it('toggles fullBleed on active session', () => {
    const store = useDiaDTradingSessionStore.getState();
    store.enterSession({
      instrumentId: 'i1',
      symbol: 'ACS',
      strategyDefinitionId: 's1',
      strategyLabel: 'SMA',
      rank: 1,
      diaD: '2024-01-01',
      endDate: '2024-12-31',
    });
    expect(useDiaDTradingSessionStore.getState().session?.fullBleedMovie).toBe(false);
    store.setFullBleedMovie(true);
    expect(useDiaDTradingSessionStore.getState().session?.fullBleedMovie).toBe(true);
    store.setFullBleedMovie(false);
    expect(useDiaDTradingSessionStore.getState().session?.fullBleedMovie).toBe(false);
  });

  it('persists session without locking fullBleed across reload', async () => {
    const store = useDiaDTradingSessionStore.getState();
    store.enterSession({
      instrumentId: 'i1',
      symbol: 'ACS',
      strategyDefinitionId: 's1',
      strategyLabel: 'SMA',
      rank: 1,
      diaD: '2024-01-01',
      endDate: '2024-12-31',
    });
    store.setFullBleedMovie(true);

    // Simulate what partialize writes + what merge reads on next boot.
    const raw = localStorage.getItem('bolsa-dia-d-trading-session-v1');
    expect(raw).toBeTruthy();
    const parsed = JSON.parse(raw!) as {
      state?: { session?: { fullBleedMovie?: boolean; symbol?: string } };
    };
    expect(parsed.state?.session?.fullBleedMovie).toBe(false);

    useDiaDTradingSessionStore.setState({ session: null });
    localStorage.setItem(
      'bolsa-dia-d-trading-session-v1',
      JSON.stringify({
        state: {
          session: {
            ...parsed.state!.session,
            fullBleedMovie: true, // legacy stuck value
          },
        },
        version: 0,
      }),
    );

    // Re-apply merge path used by persist middleware.
    const persisted = JSON.parse(
      localStorage.getItem('bolsa-dia-d-trading-session-v1')!,
    ).state as { session: Record<string, unknown> };
    useDiaDTradingSessionStore.setState({
      session: {
        ...(persisted.session as never),
        gateDecisions: [],
        fullBleedMovie: false,
      },
    });
    expect(useDiaDTradingSessionStore.getState().session?.symbol).toBe('ACS');
    expect(useDiaDTradingSessionStore.getState().session?.fullBleedMovie).toBe(false);
  });
});
