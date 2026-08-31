/**
 * Export ledger (movimientos de cuenta) a CSV / JSON.
 * Patrón Blob+anchor alineado con backtest-export.
 */

import type { LedgerEntryDto } from "@bolsa/shared";
import { formatLedgerEntryLabel } from "@bolsa/shared";

function downloadBlob(filename: string, content: string, mime: string) {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

/** Escapa celdas CSV (exportado para tests). */
export function csvEscape(value: string | number | null | undefined): string {
  if (value == null) return "";
  const text = String(value);
  if (/[",\n]/.test(text)) return `"${text.replace(/"/g, '""')}"`;
  return text;
}

function ledgerFilenameBase(accountLabel: string, asOf = new Date()): string {
  const safe = accountLabel
    .trim()
    .replace(/[^\w-]+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 48);
  const day = asOf.toISOString().slice(0, 10);
  return `ledger-${safe || "account"}-${day}`;
}

export type LedgerExportRow = {
  executedAt: string;
  type: string;
  label: string;
  description: string | null;
  symbol: string | null;
  quantity: number | null;
  price: number | null;
  amount: number;
  currency: string;
  balanceAfter: number;
  id: string;
};

export function buildLedgerExportRows(
  entries: LedgerEntryDto[],
): LedgerExportRow[] {
  return entries.map((entry) => ({
    executedAt: entry.executedAt,
    type: entry.type,
    label: formatLedgerEntryLabel(entry),
    description: entry.description,
    symbol: entry.symbol,
    quantity: entry.quantity,
    price: entry.price,
    amount: entry.amount,
    currency: entry.currency,
    balanceAfter: entry.balanceAfter,
    id: entry.id,
  }));
}

export function buildLedgerCsv(entries: LedgerEntryDto[]): string {
  const header = [
    "executedAt",
    "type",
    "label",
    "description",
    "symbol",
    "quantity",
    "price",
    "amount",
    "currency",
    "balanceAfter",
    "id",
  ];
  const rows = buildLedgerExportRows(entries).map((row) =>
    [
      row.executedAt,
      row.type,
      row.label,
      row.description,
      row.symbol,
      row.quantity,
      row.price,
      row.amount,
      row.currency,
      row.balanceAfter,
      row.id,
    ]
      .map(csvEscape)
      .join(","),
  );
  return [header.join(","), ...rows].join("\n");
}

export function exportLedgerCsv(
  entries: LedgerEntryDto[],
  accountLabel: string,
): void {
  downloadBlob(
    `${ledgerFilenameBase(accountLabel)}.csv`,
    buildLedgerCsv(entries),
    "text/csv;charset=utf-8",
  );
}

export function exportLedgerJson(
  entries: LedgerEntryDto[],
  accountLabel: string,
): void {
  const payload = {
    exportedAt: new Date().toISOString(),
    account: accountLabel,
    entries: buildLedgerExportRows(entries),
  };
  downloadBlob(
    `${ledgerFilenameBase(accountLabel)}.json`,
    JSON.stringify(payload, null, 2),
    "application/json",
  );
}

/**
 * Tamaño de página al pedir ledger para export.
 * Alineado con `GET /accounts/{id}/ledger` (`limit` le=200). Vista lista sigue en 30.
 */
export const LEDGER_EXPORT_PAGE_SIZE = 200;

/** Tope de seguridad: 50 × 200 = 10_000 filas. */
export const LEDGER_EXPORT_MAX_PAGES = 50;

export type FetchLedgerPage = (
  limit: number,
  offset: number,
) => Promise<LedgerEntryDto[]>;

export type FetchAllLedgerResult = {
  entries: LedgerEntryDto[];
  truncated: boolean;
};

/**
 * Junta páginas del ledger hasta página corta/vacía o tope de seguridad.
 * `pageSize` debe ser ≤ 200 (validación API).
 */
export async function fetchAllLedgerEntries(
  fetchPage: FetchLedgerPage,
  opts?: { pageSize?: number; maxPages?: number },
): Promise<FetchAllLedgerResult> {
  const pageSize = Math.min(
    Math.max(1, opts?.pageSize ?? LEDGER_EXPORT_PAGE_SIZE),
    LEDGER_EXPORT_PAGE_SIZE,
  );
  const maxPages = Math.max(1, opts?.maxPages ?? LEDGER_EXPORT_MAX_PAGES);
  const entries: LedgerEntryDto[] = [];
  let truncated = false;

  for (let page = 0; page < maxPages; page += 1) {
    const batch = await fetchPage(pageSize, page * pageSize);
    if (!batch.length) break;
    entries.push(...batch);
    if (batch.length < pageSize) break;
    if (page === maxPages - 1) truncated = true;
  }

  return { entries, truncated };
}
