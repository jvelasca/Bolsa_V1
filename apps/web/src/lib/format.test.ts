import { describe, expect, it } from "vitest";
import {
  formatDate,
  formatDateTime,
  formatDateTimeCompact,
  formatDateTimeShort,
  formatFxRate,
  formatNumber,
  formatNumber0,
  parseLocalizedNumber,
} from "@/lib/format";

describe("lib/format (es-ES)", () => {
  const iso = "2026-08-12T07:31:00Z";

  it("formatDateTime uses es-ES locale", () => {
    // Coma como separador de hora y patrón español.
    expect(formatDateTime(iso)).toMatch(/\d{1,2}\/\d{1,2}\/\d{4},/);
    expect(formatDateTime(new Date(iso))).toBe(formatDateTime(iso));
  });

  it("formatDateTimeShort returns a short timestamp", () => {
    expect(formatDateTimeShort(iso)).toMatch(/\d{1,2}\/\d{1,2}\/\d{2,4}/);
  });

  it("formatDateTimeCompact includes day, short month, year and time", () => {
    const out = formatDateTimeCompact(iso);
    expect(out).toMatch(/\d{2}/);
    expect(out).toMatch(/\d{4}/);
  });

  it("formatDate returns day, short month, year", () => {
    expect(formatDate(iso)).toMatch(/\d{2}/);
    expect(formatDate(iso)).toMatch(/\d{4}/);
  });

  it("formatNumber uses es-ES thousands separator", () => {
    expect(formatNumber(1234567)).toBe("1.234.567");
    expect(formatNumber(0)).toBe("0");
  });

  it("formatNumber0 keep zero decimals", () => {
    expect(formatNumber0(1234.9)).toBe("1235");
    expect(formatNumber0(1234567.9)).toBe("1.234.568");
  });

  it("formatFxRate keeps 4–6 decimals", () => {
    const out = formatFxRate(1.123456);
    expect(out).toBe("1,123456");
    expect(formatFxRate(1)).toBe("1,0000");
  });

  it("parseLocalizedNumber normalizes es-ES thousands/decimal separators", () => {
    expect(parseLocalizedNumber("1.500")).toBe(1500);
    expect(parseLocalizedNumber("1500")).toBe(1500);
    expect(parseLocalizedNumber("1,5")).toBe(1.5);
    expect(parseLocalizedNumber("1.500,75")).toBe(1500.75);
    expect(parseLocalizedNumber("0")).toBe(0);
    expect(parseLocalizedNumber("1.5")).toBe(1.5);
    expect(parseLocalizedNumber("1.234.567,89")).toBe(1234567.89);
  });

  it("parseLocalizedNumber returns null for invalid/empty input", () => {
    expect(parseLocalizedNumber("")).toBeNull();
    expect(parseLocalizedNumber("   ")).toBeNull();
    expect(parseLocalizedNumber("abc")).toBeNull();
    expect(parseLocalizedNumber("1,2,3")).toBeNull();
  });
});
