import type {
  InstrumentWithMetaDto,
  ListColumnId,
  ListSortState,
} from "@bolsa/shared";
import { LIST_COLUMN_LABELS } from "@bolsa/shared";
import { formatPct, formatPrice } from "@/features/charts/chart-utils";

function escapeCsv(value: string | number | null | undefined): string {
  if (value == null) return "";
  const text = String(value);
  if (text.includes(",") || text.includes('"') || text.includes("\n")) {
    return `"${text.replace(/"/g, '""')}"`;
  }
  return text;
}

function cellValue(item: InstrumentWithMetaDto, column: ListColumnId): string {
  switch (column) {
    case "symbol":
      return item.symbol;
    case "name":
      return item.name;
    case "lastClose":
      return item.meta.lastClose != null ? item.meta.lastClose.toFixed(2) : "";
    case "changePct":
      return item.meta.changePct != null ? item.meta.changePct.toFixed(2) : "";
    case "isin":
      return item.isin ?? "";
    case "syncStatus":
      return (
        item.meta.lastSync?.status ??
        (item.meta.barCount > 0 ? "success" : "pending")
      );
    case "processStatus":
      return "process";
    case "lastLabAt":
    case "lastCoreRAt":
    case "ioScore":
    case "taScore":
    case "faScore":
    case "dictamenStars":
    case "recStance":
      return "";
    default:
      return "";
  }
}

export function exportInstrumentsCsv(
  instruments: InstrumentWithMetaDto[],
  columns: ListColumnId[],
  listName: string,
) {
  const header = columns.map((c) => LIST_COLUMN_LABELS[c]).join(",");
  const rows = instruments.map((item) =>
    columns.map((column) => escapeCsv(cellValue(item, column))).join(","),
  );
  const csv = [header, ...rows].join("\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `${listName.replace(/\s+/g, "-").toLowerCase()}.csv`;
  anchor.click();
  URL.revokeObjectURL(url);
}

export function getListCellDisplay(
  item: InstrumentWithMetaDto,
  column: ListColumnId,
): { text: string; className?: string } {
  switch (column) {
    case "symbol":
      return { text: item.symbol, className: "font-medium" };
    case "name":
      return { text: item.name };
    case "lastClose":
      return {
        text:
          item.meta.lastClose != null ? formatPrice(item.meta.lastClose) : "—",
        className: "text-right tabular-nums",
      };
    case "changePct":
      return {
        text:
          item.meta.changePct != null ? formatPct(item.meta.changePct) : "—",
        className: `text-right tabular-nums ${
          item.meta.changePct != null && item.meta.changePct >= 0
            ? "text-success"
            : "text-destructive"
        }`,
      };
    case "isin":
      return {
        text: item.isin?.trim() || "—",
        className: "text-[10px] tabular-nums text-muted-foreground",
      };
    case "syncStatus": {
      const status =
        item.meta.lastSync?.status ??
        (item.meta.barCount > 0 ? "success" : "pending");
      const label =
        status === "success" || status === "partial"
          ? "ok"
          : status === "failed"
            ? "error"
            : "pending";
      return { text: label, className: "sr-only" };
    }
    case "processStatus":
      return { text: "procesos", className: "sr-only" };
    case "lastLabAt":
    case "lastCoreRAt":
      return {
        text: "—",
        className: "text-[10px] tabular-nums text-muted-foreground",
      };
    case "ioScore":
    case "taScore":
    case "faScore":
    case "dictamenStars":
    case "recStance":
      return {
        text: "—",
        className: "text-[10px] tabular-nums text-muted-foreground",
      };
    default:
      return { text: "—" };
  }
}

function sortValue(
  item: InstrumentWithMetaDto,
  column: ListColumnId,
): string | number {
  switch (column) {
    case "symbol":
      return item.symbol.toLowerCase();
    case "name":
      return item.name.toLowerCase();
    case "lastClose":
      return item.meta.lastClose ?? -Infinity;
    case "changePct":
      return item.meta.changePct ?? -Infinity;
    case "isin":
      return (item.isin ?? "").toLowerCase();
    case "syncStatus":
      return item.meta.lastSync?.status ?? "";
    case "processStatus":
      return 0;
    case "lastLabAt":
    case "lastCoreRAt":
      return "";
    case "ioScore":
    case "taScore":
    case "faScore":
    case "dictamenStars":
      return -Infinity;
    case "recStance":
      return "";
    default:
      return "";
  }
}

export function sortInstrumentList(
  items: InstrumentWithMetaDto[],
  sort: ListSortState | undefined,
): InstrumentWithMetaDto[] {
  if (!sort) return items;
  const factor = sort.direction === "asc" ? 1 : -1;
  return [...items].sort((a, b) => {
    const va = sortValue(a, sort.column);
    const vb = sortValue(b, sort.column);
    if (typeof va === "number" && typeof vb === "number") {
      return (va - vb) * factor;
    }
    return String(va).localeCompare(String(vb), "es") * factor;
  });
}
