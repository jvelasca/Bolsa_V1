import { describe, expect, it } from "vitest";
import {
  compareByOptimalThenGeo,
  geoTier,
  inferHomeCountry,
  optimalScoreFromPayload,
  rankByOptimalThenGeo,
} from "@/features/trading/demo-book-geo-rank";

describe("demo-book-geo-rank", () => {
  it("infers home from account currency and position mode", () => {
    expect(inferHomeCountry({ accountCurrency: "EUR" })).toBe("ES");
    expect(inferHomeCountry({ accountCurrency: "USD" })).toBe("US");
    expect(
      inferHomeCountry({
        accountCurrency: "USD",
        positionCountries: ["ES", "ES", "DE"],
      }),
    ).toBe("ES");
  });

  it("tiers home < Europe < world under home_first", () => {
    expect(geoTier("ES", "ES", "home_first")).toBe(0);
    expect(geoTier("DE", "ES", "home_first")).toBe(1);
    expect(geoTier("US", "ES", "home_first")).toBe(2);
  });

  it("europe_first treats all EU as tier 0", () => {
    expect(geoTier("ES", "ES", "europe_first")).toBe(0);
    expect(geoTier("DE", "ES", "europe_first")).toBe(0);
    expect(geoTier("US", "ES", "europe_first")).toBe(2);
  });

  it("global_ok ignores geography", () => {
    expect(geoTier("US", "ES", "global_ok")).toBe(0);
    expect(geoTier("ES", "ES", "global_ok")).toBe(0);
  });

  it("ranks by optimal score first, then geo among ties", () => {
    const ctx = {
      prefer: "home_first" as const,
      homeCountry: "ES",
    };
    const ranked = rankByOptimalThenGeo(
      [
        { instrumentId: "us", optimalScore: 0.5, country: "US", tieBreak: "a" },
        { instrumentId: "es", optimalScore: 0.5, country: "ES", tieBreak: "b" },
        {
          instrumentId: "best",
          optimalScore: 0.9,
          country: "US",
          tieBreak: "c",
        },
      ],
      ctx,
    );
    expect(ranked.map((x) => x.instrumentId)).toEqual(["best", "es", "us"]);
  });

  it("never drops a worse-score home vs better-score world", () => {
    const cmp = compareByOptimalThenGeo(
      { instrumentId: "es", optimalScore: 0.2, country: "ES" },
      { instrumentId: "us", optimalScore: 0.8, country: "US" },
      { prefer: "home_first", homeCountry: "ES" },
    );
    expect(cmp).toBeGreaterThan(0); // us first
  });

  it("reads optimal score from payload fields", () => {
    expect(optimalScoreFromPayload({ combinedScore: 0.7 })).toBe(0.7);
    expect(optimalScoreFromPayload({ scoreTa: 0.4 })).toBe(0.4);
    expect(optimalScoreFromPayload({ metrics: { conviction: 0.3 } })).toBe(0.3);
    expect(optimalScoreFromPayload({})).toBe(0);
  });
});
