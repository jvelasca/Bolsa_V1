/**
 * Tests — CORE-P CoachProfilePolicy / gate Lab / techo DD / multi-perfil.
 */

import { describe, expect, it } from 'vitest';
import {
  activeTopProfileMismatch,
  buildCoachProfileBindingFacts,
  buildProfilePolicyFingerprintSegment,
  formatCoachProfileRailLabel,
  formatPreferredLabFamiliesHint,
  isDrawdownWithinSoftCap,
  labImprovedRespectingProfileDd,
  preferredCategoriesForHorizon,
  preferredLabFamiliesForHorizon,
  resolveCoachProfilePolicy,
  resolveDefaultLabFamily,
  labSpaceWidthFactorForRisk,
  formatLabRiskSpaceHint,
  shouldAdvanceToLab,
} from '@/features/backtests/coach-profile-policy';

describe('resolveCoachProfilePolicy', () => {
  it('defaults conservative without profile', () => {
    const p = resolveCoachProfilePolicy({});
    expect(p.allowLabIfWeak).toBe(false);
    expect(p.suggestedFutureWeight).toBe(0.3);
    expect(p.policyVersion).toBe('coach-profile-v1');
    expect(p.profileId).toBeNull();
  });

  it('high risk may lab if weak', () => {
    const p = resolveCoachProfilePolicy({
      profileId: 'p-agg',
      riskTolerance: 'high',
      horizon: 'swing',
    });
    expect(p.allowLabIfWeak).toBe(true);
    expect(p.maxDrawdownSoftPct).toBeGreaterThan(30);
    expect(p.profileId).toBe('p-agg');
  });

  it('moderate / low block lab if weak', () => {
    expect(resolveCoachProfilePolicy({ riskTolerance: 'moderate' }).allowLabIfWeak).toBe(false);
    expect(resolveCoachProfilePolicy({ riskTolerance: 'low' }).allowLabIfWeak).toBe(false);
    expect(resolveCoachProfilePolicy({ riskTolerance: 'low' }).maxDrawdownSoftPct).toBe(18);
  });
});

describe('shouldAdvanceToLab', () => {
  const conservative = resolveCoachProfilePolicy({ riskTolerance: 'low' });
  const aggressive = resolveCoachProfilePolicy({ riskTolerance: 'high' });

  it('skips lab when weak and check OFF (overrides aggressive profile)', () => {
    const d = shouldAdvanceToLab({
      confidence: 'weak',
      policy: aggressive,
      labEvenIfWeak: false,
      recommendationCount: 3,
    });
    expect(d.advance).toBe(false);
    expect(d.reason).toMatch(/check/i);
  });

  it('allows lab when weak and check ON (overrides conservative profile)', () => {
    const d = shouldAdvanceToLab({
      confidence: 'weak',
      policy: conservative,
      labEvenIfWeak: true,
      recommendationCount: 3,
    });
    expect(d.advance).toBe(true);
  });

  it('falls back to profile when check omitted', () => {
    expect(
      shouldAdvanceToLab({
        confidence: 'weak',
        policy: conservative,
        recommendationCount: 3,
      }).advance,
    ).toBe(false);
    expect(
      shouldAdvanceToLab({
        confidence: 'weak',
        policy: aggressive,
        recommendationCount: 3,
      }).advance,
    ).toBe(true);
  });

  it('advances on consensus', () => {
    expect(
      shouldAdvanceToLab({
        confidence: 'consensus',
        policy: conservative,
        labEvenIfWeak: false,
        recommendationCount: 3,
      }).advance,
    ).toBe(true);
  });

  it('blocks empty TOP', () => {
    expect(
      shouldAdvanceToLab({
        confidence: 'consensus',
        policy: aggressive,
        labEvenIfWeak: true,
        recommendationCount: 0,
      }).advance,
    ).toBe(false);
  });
});

describe('CORE-P multi-perfil', () => {
  it('same weak audit → different gate by profile', () => {
    const low = resolveCoachProfilePolicy({
      profileId: 'conservative',
      profileName: 'Conservador',
      riskTolerance: 'low',
      horizon: 'position',
    });
    const high = resolveCoachProfilePolicy({
      profileId: 'aggressive',
      profileName: 'Agresivo',
      riskTolerance: 'high',
      horizon: 'swing',
    });
    expect(low.allowLabIfWeak).not.toBe(high.allowLabIfWeak);
    expect(
      shouldAdvanceToLab({
        confidence: 'weak',
        policy: low,
        recommendationCount: 3,
      }).advance,
    ).toBe(false);
    expect(
      shouldAdvanceToLab({
        confidence: 'weak',
        policy: high,
        recommendationCount: 3,
      }).advance,
    ).toBe(true);
    expect(buildProfilePolicyFingerprintSegment(low)).not.toBe(
      buildProfilePolicyFingerprintSegment(high),
    );
    expect(formatCoachProfileRailLabel(low)).toMatch(/Conservador/);
    expect(buildCoachProfileBindingFacts(high).profileId).toBe('aggressive');
  });

  it('Lab techo DD: mejora de score no adopta si rompe perfil', () => {
    const low = resolveCoachProfilePolicy({ riskTolerance: 'low' });
    expect(isDrawdownWithinSoftCap(12, low.maxDrawdownSoftPct)).toBe(true);
    expect(isDrawdownWithinSoftCap(22, low.maxDrawdownSoftPct)).toBe(false);

    const blocked = labImprovedRespectingProfileDd({
      scoreImproved: true,
      maxDrawdownPct: 30,
      maxDrawdownSoftPct: low.maxDrawdownSoftPct,
    });
    expect(blocked.improved).toBe(false);
    expect(blocked.profileDdBlocked).toBe(true);

    const ok = labImprovedRespectingProfileDd({
      scoreImproved: true,
      maxDrawdownPct: 10,
      maxDrawdownSoftPct: low.maxDrawdownSoftPct,
    });
    expect(ok.improved).toBe(true);
    expect(ok.profileDdBlocked).toBe(false);

    const high = resolveCoachProfilePolicy({ riskTolerance: 'high' });
    expect(
      labImprovedRespectingProfileDd({
        scoreImproved: true,
        maxDrawdownPct: 35,
        maxDrawdownSoftPct: high.maxDrawdownSoftPct,
      }).improved,
    ).toBe(true);
  });
});

describe('CORE-P preferred Lab families + profile mismatch', () => {
  it('maps horizon categories to Lab families', () => {
    expect(preferredCategoriesForHorizon('long_term')).toEqual(['trend', 'composite']);
    expect(preferredLabFamiliesForHorizon('long_term')).toEqual(['sma_crossover']);
    expect(preferredLabFamiliesForHorizon('intraday')[0]).toBe('rsi_mean_reversion');
    expect(formatPreferredLabFamiliesHint('swing')).toMatch(/Lab prioriza/);
  });

  it('resolveDefaultLabFamily: seed > adopción > horizonte', () => {
    expect(
      resolveDefaultLabFamily({
        seedFamily: 'macd_signal_cross',
        adoptionFamily: 'rsi_mean_reversion',
        horizon: 'long_term',
      }),
    ).toBe('macd_signal_cross');
    expect(
      resolveDefaultLabFamily({
        adoptionFamily: 'rsi_mean_reversion',
        horizon: 'long_term',
      }),
    ).toBe('rsi_mean_reversion');
    expect(resolveDefaultLabFamily({ horizon: 'intraday' })).toBe('rsi_mean_reversion');
    expect(resolveDefaultLabFamily({ horizon: 'long_term' })).toBe('sma_crossover');
    expect(resolveDefaultLabFamily({})).toBe('sma_crossover');
  });

  it('soft-bias Lab space width by riskTolerance', () => {
    expect(labSpaceWidthFactorForRisk('low')).toBe(0.75);
    expect(labSpaceWidthFactorForRisk('high')).toBe(1.35);
    expect(labSpaceWidthFactorForRisk('moderate')).toBe(1);
    expect(labSpaceWidthFactorForRisk(null)).toBe(1);
    expect(formatLabRiskSpaceHint('low')).toMatch(/estrecho/);
    expect(formatLabRiskSpaceHint('high')).toMatch(/amplio/);
    expect(formatLabRiskSpaceHint('moderate')).toBeNull();
  });

  it('warns when active TOP stamped with another profile', () => {
    expect(
      activeTopProfileMismatch({
        topStatus: 'active',
        stampedProfileId: 'p-old',
        activeProfileId: 'p-new',
      }).mismatch,
    ).toBe(true);
    expect(
      activeTopProfileMismatch({
        topStatus: 'active',
        stampedProfileId: 'p1',
        activeProfileId: 'p1',
      }).mismatch,
    ).toBe(false);
    expect(
      activeTopProfileMismatch({
        topStatus: 'draft',
        stampedProfileId: 'a',
        activeProfileId: 'b',
      }).mismatch,
    ).toBe(false);
  });
});
