import { describe, expect, it } from "vitest";
import { instrumentMatchesSearchQuery, normalizeIsin } from "@bolsa/shared";

describe("instrumentMatchesSearchQuery", () => {
  const item = {
    symbol: "SAN",
    name: "Banco Santander",
    yahooSymbol: "SAN.MC",
    isin: "ES0113900J37",
  };

  it("matches by partial ISIN", () => {
    expect(instrumentMatchesSearchQuery(item, "0113900J37")).toBe(true);
  });

  it("matches by ISIN with spaces", () => {
    expect(instrumentMatchesSearchQuery(item, "ES01 1390 0J37")).toBe(true);
  });

  it("matches by symbol as before", () => {
    expect(instrumentMatchesSearchQuery(item, "san")).toBe(true);
  });
});

describe("normalizeIsin", () => {
  it("strips separators", () => {
    expect(normalizeIsin("es01-1390-0j37")).toBe("ES0113900J37");
  });
});
