import { describe, expect, it } from "vitest";
import {
  classifyWfe,
  formatPositiveFoldShare,
  formatWfe,
  walkForwardStabilityFlags,
  wfeBandLabel,
} from "@/features/backtests/backtest-walk-forward-metrics";

describe("walk-forward metrics (P3.I)", () => {
  it("classifies WFE bands", () => {
    expect(classifyWfe(0.8)).toBe("acceptable");
    expect(classifyWfe(0.55)).toBe("fragile");
    expect(classifyWfe(0.4)).toBe("weak");
    expect(classifyWfe(null)).toBe("undefined");
    expect(wfeBandLabel("fragile")).toBe("frágil");
  });

  it("formats WFE and positive fold share", () => {
    expect(formatWfe(0.62)).toBe("0.62");
    expect(formatWfe(null)).toBe("n/d");
    expect(formatPositiveFoldShare(0.6667, 3)).toBe("2/3 pliegues OOS≥0");
  });

  it("flags weak WFE, high CV and few positive folds", () => {
    const flags = walkForwardStabilityFlags({
      walkForwardEfficiency: 0.3,
      oosCv: 1.4,
      positiveOosFoldShare: 0.25,
    });
    expect(flags.weakWfe).toBe(true);
    expect(flags.unstableCv).toBe(true);
    expect(flags.fewPositiveFolds).toBe(true);
  });

  it("does not flag acceptable stable WF", () => {
    const flags = walkForwardStabilityFlags({
      walkForwardEfficiency: 0.75,
      oosCv: 0.3,
      positiveOosFoldShare: 1,
    });
    expect(flags.weakWfe).toBe(false);
    expect(flags.unstableCv).toBe(false);
    expect(flags.fewPositiveFolds).toBe(false);
  });
});
