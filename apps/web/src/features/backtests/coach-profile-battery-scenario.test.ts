/**
 * CORE-P — escenario offline multi-perfil (misma batería, dos políticas).
 * Sin API: gate Lab · techo DD · stamp · mismatch · familias · frescura.
 */

import { describe, expect, it } from "vitest";
import {
  activeTopProfileMismatch,
  buildCoachProfileBindingFacts,
  buildProfilePolicyFingerprintSegment,
  labImprovedRespectingProfileDd,
  labSpaceWidthFactorForRisk,
  preferredLabFamiliesForHorizon,
  resolveCoachProfilePolicy,
  shouldAdvanceToLab,
} from "@/features/backtests/coach-profile-policy";
import {
  buildFinalistsFreshnessStamp,
  buildFinalistsInputFingerprint,
  shouldSkipFinalistsSearch,
} from "@/features/backtests/backtest-finalists-freshness";

const BATTERY = {
  instrumentId: "inst-ibex-tef",
  timeframe: "1d",
  periodPreset: "all" as const,
  initialCash: "10000",
  commissionBps: "5",
  slippageBps: "2",
  lastBarDate: "2026-07-29",
  loteRowIds: ["sma_crossover", "rsi_mean_reversion", "saved:x1"] as const,
  weakAudit: "weak" as const,
  recCount: 3,
  labCandidateDdPct: 25,
};

describe("CORE-P battery scenario (offline multi-perfil)", () => {
  const low = resolveCoachProfilePolicy({
    profileId: "p-low",
    profileName: "Conservador",
    riskTolerance: "low",
    horizon: "long_term",
  });
  const high = resolveCoachProfilePolicy({
    profileId: "p-high",
    profileName: "Agresivo",
    riskTolerance: "high",
    horizon: "intraday",
  });

  it("same weak battery → Lab only for high risk", () => {
    expect(
      shouldAdvanceToLab({
        confidence: BATTERY.weakAudit,
        policy: low,
        recommendationCount: BATTERY.recCount,
      }).advance,
    ).toBe(false);
    expect(
      shouldAdvanceToLab({
        confidence: BATTERY.weakAudit,
        policy: high,
        recommendationCount: BATTERY.recCount,
      }).advance,
    ).toBe(true);
  });

  it("same Lab DD candidate → blocked for low, ok for high", () => {
    const dd = BATTERY.labCandidateDdPct;
    expect(
      labImprovedRespectingProfileDd({
        scoreImproved: true,
        maxDrawdownPct: dd,
        maxDrawdownSoftPct: low.maxDrawdownSoftPct,
      }).profileDdBlocked,
    ).toBe(true);
    expect(
      labImprovedRespectingProfileDd({
        scoreImproved: true,
        maxDrawdownPct: dd,
        maxDrawdownSoftPct: high.maxDrawdownSoftPct,
      }).improved,
    ).toBe(true);
  });

  it("stamps differ; active TOP from low mismatches high", () => {
    const stampLow = buildCoachProfileBindingFacts(low);
    const stampHigh = buildCoachProfileBindingFacts(high);
    expect(stampLow.profileId).not.toBe(stampHigh.profileId);
    expect(
      activeTopProfileMismatch({
        topStatus: "active",
        stampedProfileId: String(stampLow.profileId),
        activeProfileId: String(stampHigh.profileId),
      }).mismatch,
    ).toBe(true);
  });

  it("preferred Lab families follow horizon", () => {
    expect(preferredLabFamiliesForHorizon(low.horizon)[0]).toBe(
      "sma_crossover",
    );
    expect(preferredLabFamiliesForHorizon(high.horizon)[0]).toBe(
      "rsi_mean_reversion",
    );
  });

  it("soft-bias space width differs by risk on same battery", () => {
    expect(labSpaceWidthFactorForRisk(low.riskTolerance)).toBe(0.75);
    expect(labSpaceWidthFactorForRisk(high.riskTolerance)).toBe(1.35);
  });

  it("profile switch invalidates Finalistas freshness skip", () => {
    const segLow = buildProfilePolicyFingerprintSegment(low);
    const segHigh = buildProfilePolicyFingerprintSegment(high);
    expect(segLow).not.toBe(segHigh);

    const fpLow = buildFinalistsInputFingerprint({
      ...BATTERY,
      loteRowIds: [...BATTERY.loteRowIds],
      profilePolicyVersion: segLow,
    });
    const fpHigh = buildFinalistsInputFingerprint({
      ...BATTERY,
      loteRowIds: [...BATTERY.loteRowIds],
      profilePolicyVersion: segHigh,
    });
    expect(fpLow).not.toBe(fpHigh);

    const stored = buildFinalistsFreshnessStamp({
      inputFingerprint: fpLow,
      lab: true,
    });
    const skipSame = shouldSkipFinalistsSearch({
      preferSkip: true,
      forceRescan: false,
      currentFingerprint: fpLow,
      stored,
      topStatus: "active",
      hasSlots: true,
    });
    expect(skipSame.skip).toBe(true);

    const skipAfterSwitch = shouldSkipFinalistsSearch({
      preferSkip: true,
      forceRescan: false,
      currentFingerprint: fpHigh,
      stored,
      topStatus: "active",
      hasSlots: true,
    });
    expect(skipAfterSwitch.skip).toBe(false);
    expect(skipAfterSwitch.reason).toBe("fingerprint_mismatch");
  });
});
