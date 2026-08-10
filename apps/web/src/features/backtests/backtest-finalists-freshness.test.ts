/**
 * Tests — frescura Finalistas (fingerprint + skip).
 */

import { beforeEach, describe, expect, it } from "vitest";
import {
  FINALISTS_FRESHNESS_ENGINE,
  FINALISTS_FRESHNESS_STORAGE_KEY,
  buildFinalistsFreshnessStamp,
  buildFinalistsInputFingerprint,
  clearLocalFreshnessFingerprint,
  compareFinalistsFingerprints,
  formatFreshnessAge,
  freshnessSkipDenialLabel,
  instrumentLastBarDate,
  mergeFreshnessIntoCoachFacts,
  readFinalistsFreshness,
  readLocalFreshnessFingerprint,
  shouldSkipFinalistsSearch,
  writeLocalFreshnessFingerprint,
} from "@/features/backtests/backtest-finalists-freshness";

const baseFp = () =>
  buildFinalistsInputFingerprint({
    instrumentId: "id-grf",
    timeframe: "1d",
    periodPreset: "all",
    initialCash: "10000",
    commissionBps: "5",
    slippageBps: "2",
    lastBarDate: "2026-07-28",
    loteRowIds: ["sma_crossover", "saved:abc"],
    profilePolicyVersion: "coach-profile-v0",
  });

describe("buildFinalistsInputFingerprint", () => {
  it("changes when lastBarDate changes", () => {
    const a = baseFp();
    const b = buildFinalistsInputFingerprint({
      instrumentId: "id-grf",
      timeframe: "1d",
      periodPreset: "all",
      initialCash: "10000",
      commissionBps: "5",
      slippageBps: "2",
      lastBarDate: "2026-07-29",
      loteRowIds: ["sma_crossover", "saved:abc"],
      profilePolicyVersion: "coach-profile-v0",
    });
    expect(a).not.toBe(b);
    expect(a).toContain(FINALISTS_FRESHNESS_ENGINE);
  });

  it("is stable to lote id order and number/string scalars", () => {
    const a = buildFinalistsInputFingerprint({
      instrumentId: "x",
      timeframe: "1d",
      periodPreset: "all",
      initialCash: 1,
      commissionBps: 0,
      slippageBps: 0,
      lastBarDate: "2026-07-28T12:00:00Z",
      loteRowIds: ["b", "a"],
    });
    const b = buildFinalistsInputFingerprint({
      instrumentId: "x",
      timeframe: "1d",
      periodPreset: "all",
      initialCash: "1",
      commissionBps: "0",
      slippageBps: "0",
      lastBarDate: "2026-07-28",
      loteRowIds: ["a", "b"],
    });
    expect(a).toBe(b);
  });
});

describe("shouldSkipFinalistsSearch", () => {
  const fp = baseFp();
  const stored = buildFinalistsFreshnessStamp({
    inputFingerprint: fp,
    lab: true,
  });

  it("skips when active TOP + matching stamp", () => {
    expect(
      shouldSkipFinalistsSearch({
        preferSkip: true,
        topStatus: "active",
        stored,
        currentFingerprint: fp,
        hasSlots: true,
      }),
    ).toEqual({ skip: true, reason: "fresh" });
  });

  it("adopts any active TOP with slots and no stamp", () => {
    expect(
      shouldSkipFinalistsSearch({
        preferSkip: true,
        topStatus: "active",
        evidenceLevel: "in_sample_only",
        stored: null,
        currentFingerprint: fp,
        hasSlots: true,
      }),
    ).toEqual({
      skip: true,
      reason: "adopt_existing_top",
      adoptFingerprint: true,
    });
  });

  it("does not omit without Finalistas slots (aunque haya stamp / huella)", () => {
    expect(
      shouldSkipFinalistsSearch({
        preferSkip: true,
        topStatus: "active",
        stored,
        currentFingerprint: fp,
        localFingerprint: fp,
        memoryFingerprint: fp,
        hasSlots: false,
      }),
    ).toEqual({ skip: false, reason: "no_finalists_slots" });
  });

  it("does not skip on force or prefs off", () => {
    expect(
      shouldSkipFinalistsSearch({
        preferSkip: true,
        forceRescan: true,
        topStatus: "active",
        stored,
        currentFingerprint: fp,
        hasSlots: true,
      }).reason,
    ).toBe("force");
    expect(
      shouldSkipFinalistsSearch({
        preferSkip: false,
        topStatus: "active",
        stored,
        currentFingerprint: fp,
        hasSlots: true,
      }).reason,
    ).toBe("prefs_off");
  });

  it("skips on session memory when Finalistas existen", () => {
    expect(
      shouldSkipFinalistsSearch({
        preferSkip: true,
        topStatus: "active",
        stored: null,
        currentFingerprint: fp,
        memoryFingerprint: fp,
        hasSlots: true,
      }),
    ).toEqual({ skip: true, reason: "session_fresh" });
  });

  it("skips on localStorage fingerprint when Finalistas existen", () => {
    expect(
      shouldSkipFinalistsSearch({
        preferSkip: true,
        topStatus: "active",
        stored: null,
        currentFingerprint: fp,
        localFingerprint: fp,
        hasSlots: true,
      }),
    ).toEqual({ skip: true, reason: "local_fresh" });
  });

  it("skips on DB stamp with Finalistas (semifinal OK)", () => {
    expect(
      shouldSkipFinalistsSearch({
        preferSkip: true,
        topStatus: "semifinal",
        stored,
        currentFingerprint: fp,
        hasSlots: true,
      }),
    ).toEqual({ skip: true, reason: "fresh" });
  });

  it("skips with bar_hysteresis when only lastBarDate moved within slack", () => {
    const fpNew = buildFinalistsInputFingerprint({
      instrumentId: "id-grf",
      timeframe: "1d",
      periodPreset: "all",
      initialCash: "10000",
      commissionBps: "5",
      slippageBps: "2",
      lastBarDate: "2026-08-01",
      loteRowIds: ["sma_crossover", "saved:abc"],
      profilePolicyVersion: "coach-profile-v0",
    });
    expect(compareFinalistsFingerprints(fp, fpNew)).toBe("bar_hysteresis");
    expect(
      shouldSkipFinalistsSearch({
        preferSkip: true,
        topStatus: "active",
        stored,
        currentFingerprint: fpNew,
        hasSlots: true,
      }),
    ).toEqual({ skip: true, reason: "bar_hysteresis" });
  });

  it("does not skip when lastBarDate exceeds slack", () => {
    const fpFar = buildFinalistsInputFingerprint({
      instrumentId: "id-grf",
      timeframe: "1d",
      periodPreset: "all",
      initialCash: "10000",
      commissionBps: "5",
      slippageBps: "2",
      lastBarDate: "2026-08-05",
      loteRowIds: ["sma_crossover", "saved:abc"],
      profilePolicyVersion: "coach-profile-v0",
    });
    expect(compareFinalistsFingerprints(fp, fpFar)).toBe("mismatch");
    expect(
      shouldSkipFinalistsSearch({
        preferSkip: true,
        topStatus: "active",
        stored,
        currentFingerprint: fpFar,
        hasSlots: true,
      }).reason,
    ).toBe("fingerprint_mismatch");
  });

  it("does not apply hysteresis when profile/lote changes", () => {
    const fpOther = buildFinalistsInputFingerprint({
      instrumentId: "id-grf",
      timeframe: "1d",
      periodPreset: "all",
      initialCash: "10000",
      commissionBps: "5",
      slippageBps: "2",
      lastBarDate: "2026-07-29",
      loteRowIds: ["sma_crossover", "saved:abc"],
      profilePolicyVersion: "coach-profile-v1|pid:other",
    });
    expect(compareFinalistsFingerprints(fp, fpOther)).toBe("mismatch");
  });
});

describe("clearLocalFreshnessFingerprint", () => {
  beforeEach(() => {
    localStorage.removeItem(FINALISTS_FRESHNESS_STORAGE_KEY);
  });

  it("removes only the instrument|TF entry", () => {
    writeLocalFreshnessFingerprint({
      instrumentId: "acs",
      timeframe: "1d",
      fingerprint: "fp-acs",
    });
    writeLocalFreshnessFingerprint({
      instrumentId: "san",
      timeframe: "1d",
      fingerprint: "fp-san",
    });
    clearLocalFreshnessFingerprint("acs", "1d");
    expect(readLocalFreshnessFingerprint("acs", "1d")).toBeNull();
    expect(readLocalFreshnessFingerprint("san", "1d")?.fingerprint).toBe(
      "fp-san",
    );
  });
});

describe("local freshness storage", () => {
  beforeEach(() => {
    localStorage.removeItem(FINALISTS_FRESHNESS_STORAGE_KEY);
  });

  it("roundtrips fingerprint across read/write", () => {
    writeLocalFreshnessFingerprint({
      instrumentId: "id-1",
      timeframe: "1d",
      fingerprint: "fp-abc",
      at: "2026-07-26T10:00:00.000Z",
    });
    expect(readLocalFreshnessFingerprint("id-1", "1d")).toEqual({
      fingerprint: "fp-abc",
      lastSearchAt: "2026-07-26T10:00:00.000Z",
      timeframe: "1d",
    });
  });
});

describe("instrumentLastBarDate", () => {
  it("reads meta.lastBarDate from InstrumentWithMeta", () => {
    expect(
      instrumentLastBarDate({
        meta: { lastBarDate: "2026-07-28" },
      }),
    ).toBe("2026-07-28");
    expect(instrumentLastBarDate(null)).toBeNull();
  });
});

describe("coachFacts roundtrip", () => {
  it("merges and reads freshness", () => {
    const stamp = buildFinalistsFreshnessStamp({
      inputFingerprint: "abc",
      lab: true,
    });
    const facts = mergeFreshnessIntoCoachFacts({ dualAudit: null }, stamp);
    expect(readFinalistsFreshness(facts)?.inputFingerprint).toBe("abc");
    expect(
      formatFreshnessAge(stamp.lastSearchAt, Date.parse(stamp.lastSearchAt)),
    ).toBe("ahora");
    expect(freshnessSkipDenialLabel("no_stamp")).toMatch(/stamp/i);
  });
});
