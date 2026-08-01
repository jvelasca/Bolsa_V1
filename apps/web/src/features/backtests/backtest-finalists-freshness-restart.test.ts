/**
 * Escenario: frescura Finalistas tras reinicio (sin sesión).
 */

import { beforeEach, describe, expect, it } from 'vitest';
import {
  FINALISTS_FRESHNESS_STORAGE_KEY,
  buildFinalistsFreshnessStamp,
  buildFinalistsInputFingerprint,
  isFinalistsFreshnessContextReady,
  shouldSkipFinalistsSearch,
  writeLocalFreshnessFingerprint,
} from '@/features/backtests/backtest-finalists-freshness';

const INSTRUMENT_ID = 'inst-grf-test';
const TIMEFRAME = '1d';

function fingerprint(opts: {
  lastBarDate: string | null;
  profilePolicyVersion?: string;
}) {
  return buildFinalistsInputFingerprint({
    instrumentId: INSTRUMENT_ID,
    timeframe: TIMEFRAME,
    periodPreset: 'all',
    initialCash: '10000',
    commissionBps: '0',
    slippageBps: '0',
    lastBarDate: opts.lastBarDate,
    loteRowIds: ['preset:sma_crossover'],
    profilePolicyVersion: opts.profilePolicyVersion ?? 'coach-profile-v1|pid:p1|ff:1',
  });
}

describe('frescura cross-restart (Lista AUTO)', () => {
  beforeEach(() => {
    localStorage.removeItem(FINALISTS_FRESHNESS_STORAGE_KEY);
  });

  it('NO omite sin slots aunque haya huella local (Finalistas borrados)', () => {
    const fp = fingerprint({ lastBarDate: '2026-07-28' });
    writeLocalFreshnessFingerprint({
      instrumentId: INSTRUMENT_ID,
      timeframe: TIMEFRAME,
      fingerprint: fp,
    });
    expect(
      shouldSkipFinalistsSearch({
        preferSkip: true,
        topStatus: null,
        stored: null,
        currentFingerprint: fp,
        memoryFingerprint: null,
        localFingerprint: fp,
        hasSlots: false,
      }).reason,
    ).toBe('no_finalists_slots');
  });

  it('omite con huella local solo si hay Finalistas (slots)', () => {
    const fp = fingerprint({ lastBarDate: '2026-07-28' });
    writeLocalFreshnessFingerprint({
      instrumentId: INSTRUMENT_ID,
      timeframe: TIMEFRAME,
      fingerprint: fp,
    });
    expect(
      shouldSkipFinalistsSearch({
        preferSkip: true,
        topStatus: 'active',
        stored: null,
        currentFingerprint: fp,
        memoryFingerprint: null,
        localFingerprint: fp,
        hasSlots: true,
      }).reason,
    ).toBe('local_fresh');
  });

  it('omite con stamp DB tras reinicio (perfil ya listo)', () => {
    const fp = fingerprint({ lastBarDate: '2026-07-28' });
    const stored = buildFinalistsFreshnessStamp({ inputFingerprint: fp, lab: true });
    expect(
      shouldSkipFinalistsSearch({
        preferSkip: true,
        topStatus: 'active',
        stored,
        currentFingerprint: fp,
        memoryFingerprint: null,
        localFingerprint: null,
        hasSlots: true,
      }).reason,
    ).toBe('fresh');
  });

  it('NO omite si pid:none (carrera de perfil) ≠ stamp con perfil real', () => {
    const stamped = fingerprint({
      lastBarDate: '2026-07-28',
      profilePolicyVersion: 'coach-profile-v1|pid:real|ff:1',
    });
    const tooEarly = fingerprint({
      lastBarDate: '2026-07-28',
      profilePolicyVersion: 'coach-profile-v1|pid:none|ff:1',
    });
    expect(stamped).not.toBe(tooEarly);
    expect(
      shouldSkipFinalistsSearch({
        preferSkip: true,
        topStatus: 'active',
        stored: buildFinalistsFreshnessStamp({ inputFingerprint: stamped }),
        currentFingerprint: tooEarly,
        hasSlots: true,
      }).reason,
    ).toBe('fingerprint_mismatch');
  });

  it('omite con histéresis si solo avanzó lastBarDate (≤5d en 1d)', () => {
    const fpOld = fingerprint({ lastBarDate: '2026-07-28' });
    const stored = buildFinalistsFreshnessStamp({ inputFingerprint: fpOld });
    const fpNew = fingerprint({ lastBarDate: '2026-07-29' });
    expect(
      shouldSkipFinalistsSearch({
        preferSkip: true,
        topStatus: 'active',
        stored,
        currentFingerprint: fpNew,
        localFingerprint: fpOld,
        hasSlots: true,
      }).reason,
    ).toBe('bar_hysteresis');
  });

  it('reanaliza si lastBarDate supera slack (6+ días en 1d)', () => {
    const fpOld = fingerprint({ lastBarDate: '2026-07-28' });
    const stored = buildFinalistsFreshnessStamp({ inputFingerprint: fpOld });
    const fpNew = fingerprint({ lastBarDate: '2026-08-03' });
    expect(
      shouldSkipFinalistsSearch({
        preferSkip: true,
        topStatus: 'active',
        stored,
        currentFingerprint: fpNew,
        localFingerprint: fpOld,
        hasSlots: true,
      }).reason,
    ).toBe('fingerprint_mismatch');
  });

  it('context ready exige perfil e instrumentos', () => {
    expect(
      isFinalistsFreshnessContextReady({
        instrumentsFetched: true,
        accountProfileReady: false,
        strategiesReady: true,
      }),
    ).toBe(false);
    expect(
      isFinalistsFreshnessContextReady({
        instrumentsFetched: true,
        accountProfileReady: true,
        strategiesReady: true,
      }),
    ).toBe(true);
  });

  it('adopta TOP active con slots sin stamp', () => {
    const fp = fingerprint({ lastBarDate: '2026-07-28' });
    expect(
      shouldSkipFinalistsSearch({
        preferSkip: true,
        topStatus: 'active',
        stored: null,
        currentFingerprint: fp,
        memoryFingerprint: null,
        localFingerprint: null,
        hasSlots: true,
      }),
    ).toEqual({
      skip: true,
      reason: 'adopt_existing_top',
      adoptFingerprint: true,
    });
  });

  it('lista multi-ticker: mayoritariamente Omitido tras reinicio (perfil listo)', () => {
    const lastBar = '2026-07-28';
    const tickers = ['ACS', 'ITX', 'SAN', 'BBVA', 'REP', 'IBE', 'TEF', 'AENA'];
    let omit = 0;
    for (const symbol of tickers) {
      const instrumentId = `inst-${symbol.toLowerCase()}`;
      const fp = buildFinalistsInputFingerprint({
        instrumentId,
        timeframe: TIMEFRAME,
        periodPreset: 'all',
        initialCash: '10000',
        commissionBps: '0',
        slippageBps: '0',
        lastBarDate: lastBar,
        loteRowIds: ['preset:sma_crossover'],
        profilePolicyVersion: 'coach-profile-v1|pid:p1|ff:1',
      });
      const decision = shouldSkipFinalistsSearch({
        preferSkip: true,
        topStatus: 'active',
        stored: buildFinalistsFreshnessStamp({ inputFingerprint: fp, lab: true }),
        currentFingerprint: fp,
        memoryFingerprint: null,
        localFingerprint: null,
        hasSlots: true,
      });
      if (decision.skip) omit += 1;
    }
    expect(omit).toBe(tickers.length);
    expect(omit / tickers.length).toBeGreaterThanOrEqual(0.75);
  });
});
