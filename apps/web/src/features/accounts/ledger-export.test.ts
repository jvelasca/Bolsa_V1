/**
 * Tests — export ledger CSV/JSON helpers + paginación.
 */

import { describe, expect, it, vi } from "vitest";
import type { LedgerEntryDto } from "@bolsa/shared";
import {
  buildLedgerCsv,
  buildLedgerExportRows,
  csvEscape,
  fetchAllLedgerEntries,
  LEDGER_EXPORT_PAGE_SIZE,
} from "@/features/accounts/ledger-export";

function sampleEntry(partial?: Partial<LedgerEntryDto>): LedgerEntryDto {
  return {
    id: "led-1",
    accountId: "acc-1",
    portfolioId: null,
    type: "deposit",
    amount: 1000,
    currency: "EUR",
    balanceAfter: 1000,
    instrumentId: null,
    symbol: null,
    quantity: null,
    price: null,
    referenceType: null,
    referenceId: null,
    description: 'Nota "demo"',
    executedAt: "2026-08-31T12:30:00.000Z",
    ...partial,
  };
}

describe("ledger-export", () => {
  it("csvEscape quotes commas and quotes", () => {
    expect(csvEscape("a,b")).toBe('"a,b"');
    expect(csvEscape('say "hi"')).toBe('"say ""hi"""');
    expect(csvEscape(null)).toBe("");
  });

  it("buildLedgerCsv includes header and formatted label row", () => {
    const csv = buildLedgerCsv([sampleEntry()]);
    const lines = csv.split("\n");
    expect(lines[0]).toContain("executedAt");
    expect(lines[0]).toContain("balanceAfter");
    expect(lines[1]).toContain("2026-08-31T12:30:00.000Z");
    expect(lines[1]).toContain("deposit");
    expect(lines[1]).toContain("1000");
    expect(lines[1]).toMatch(/Nota/);
  });

  it("buildLedgerExportRows maps label via formatLedgerEntryLabel", () => {
    const rows = buildLedgerExportRows([sampleEntry({ type: "withdrawal" })]);
    expect(rows).toHaveLength(1);
    expect(rows[0]?.type).toBe("withdrawal");
    expect(rows[0]?.label.length).toBeGreaterThan(0);
    expect(rows[0]?.id).toBe("led-1");
  });

  it("LEDGER_EXPORT_PAGE_SIZE stays within API le=200", () => {
    expect(LEDGER_EXPORT_PAGE_SIZE).toBeLessThanOrEqual(200);
    expect(LEDGER_EXPORT_PAGE_SIZE).toBeGreaterThan(0);
  });

  it("fetchAllLedgerEntries joins pages until short page", async () => {
    const page1 = Array.from({ length: 200 }, (_, i) =>
      sampleEntry({ id: `led-${i}` }),
    );
    const page2 = [
      sampleEntry({ id: "led-200" }),
      sampleEntry({ id: "led-201" }),
    ];
    const fetchPage = vi
      .fn()
      .mockResolvedValueOnce(page1)
      .mockResolvedValueOnce(page2);
    const result = await fetchAllLedgerEntries(fetchPage);
    expect(result.entries).toHaveLength(202);
    expect(result.truncated).toBe(false);
    expect(fetchPage).toHaveBeenCalledWith(200, 0);
    expect(fetchPage).toHaveBeenCalledWith(200, 200);
  });

  it("fetchAllLedgerEntries stops on empty first page", async () => {
    const fetchPage = vi.fn().mockResolvedValue([]);
    const result = await fetchAllLedgerEntries(fetchPage);
    expect(result.entries).toHaveLength(0);
    expect(result.truncated).toBe(false);
    expect(fetchPage).toHaveBeenCalledTimes(1);
  });

  it("fetchAllLedgerEntries marks truncated at maxPages", async () => {
    const full = Array.from({ length: 10 }, (_, i) =>
      sampleEntry({ id: `led-${i}` }),
    );
    const fetchPage = vi.fn().mockResolvedValue(full);
    const result = await fetchAllLedgerEntries(fetchPage, {
      pageSize: 10,
      maxPages: 2,
    });
    expect(result.entries).toHaveLength(20);
    expect(result.truncated).toBe(true);
    expect(fetchPage).toHaveBeenCalledTimes(2);
  });
});
