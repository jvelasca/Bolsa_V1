import { describe, expect, it } from "vitest";
import {
  ABSENT_NUMBER,
  formatBps,
  formatDate,
  formatDateTime,
  formatDateTimeCompact,
  formatDateTimeShort,
  formatFxRate,
  formatMoney,
  formatNumber,
  formatNumber0,
  formatPct,
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

  it("formatMoney usa es-ES, 2 decimales fijos y símbolo de divisa", () => {
    // Convención es-ES: cuatro dígitos enteros no llevan separador de miles.
    expect(formatMoney(1234.5)).toContain("1234,50");
    expect(formatMoney(12345.5)).toContain("12.345,50");
    expect(formatMoney(1234.5)).toContain("€");
    expect(formatMoney(-0.5)).toContain("-0,50");
    expect(formatMoney(0)).toContain("0,00");
    expect(formatMoney(1234.5, "USD")).toContain("1234,50");
  });

  it("formatMoney no convierte lo no medido en cero", () => {
    expect(formatMoney(null)).toBe(ABSENT_NUMBER);
    expect(formatMoney(undefined)).toBe(ABSENT_NUMBER);
    expect(formatMoney(Number.NaN)).toBe(ABSENT_NUMBER);
    expect(formatMoney(Number.POSITIVE_INFINITY)).toBe(ABSENT_NUMBER);
  });

  it("formatPct toma puntos porcentuales (no ratios)", () => {
    expect(formatPct(12.3456)).toBe("12,35 %");
    expect(formatPct(-3.1)).toBe("-3,10 %");
    expect(formatPct(12.3456, 1)).toBe("12,3 %");
    expect(formatPct(null)).toBe(ABSENT_NUMBER);
    // 0,1234 se pinta como 0,12 % (puntos), no como 12,34 %: el valor ya viene en puntos.
    expect(formatPct(0.1234)).toBe("0,12 %");
  });

  it("formatBps usa separador es-ES y sufijo bps", () => {
    expect(formatBps(22)).toBe("22 bps");
    expect(formatBps(12.714)).toBe("12,71 bps");
    expect(formatBps(12500.5, 1)).toBe("12.500,5 bps");
    expect(formatBps(null)).toBe(ABSENT_NUMBER);
  });
});
