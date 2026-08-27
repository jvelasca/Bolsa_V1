/**
 * Chip de frescura del barrido Estudio (Hoy / Mercado encabezado).
 * Umbral alineado con OPPORTUNITY_SCAN_STALE_HOURS (48h).
 * Prefijo «Barrido» — no «Datos» (reservado a OHLCV/DS-05).
 */

import { OPPORTUNITY_SCAN_STALE_HOURS } from "./opportunity-ranking.js";
import { SCAN_FRESHNESS_PREFIX } from "./product-vocabulary.js";

export type ScanFreshnessChipToneV1 = "fresh" | "stale" | "missing";

export type ScanFreshnessChipV1 = {
  tone: ScanFreshnessChipToneV1;
  /** Texto corto para el chip (Barrido · …). */
  label: string;
  ageHours: number | null;
  asOf: string | null;
};

function hoursAgo(iso: string | null | undefined, now: Date): number | null {
  if (!iso) return null;
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return null;
  return (now.getTime() - t) / (1000 * 60 * 60);
}

function formatShortAsOf(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const day = d.toLocaleDateString(undefined, {
    day: "2-digit",
    month: "short",
  });
  const time = d.toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
  });
  return `${day} · ${time}`;
}

/**
 * Chip Barrido para encabezados.
 * fresh: as-of reciente; stale: >48h; missing: sin scan.
 */
export function buildScanFreshnessChip(input: {
  scanUpdatedAt?: string | null;
  now?: Date;
  staleHours?: number;
}): ScanFreshnessChipV1 {
  const now = input.now ?? new Date();
  const staleHours = input.staleHours ?? OPPORTUNITY_SCAN_STALE_HOURS;
  const asOf = input.scanUpdatedAt ?? null;
  const age = hoursAgo(asOf, now);
  const prefix = SCAN_FRESHNESS_PREFIX;

  if (asOf == null || age == null) {
    return {
      tone: "missing",
      label: `${prefix} · No actualizado`,
      ageHours: null,
      asOf: null,
    };
  }
  if (age > staleHours) {
    const hours = Math.round(age);
    return {
      tone: "stale",
      label: `${prefix} · Último análisis hace ${hours} h`,
      ageHours: age,
      asOf,
    };
  }
  return {
    tone: "fresh",
    label: `${prefix} · ${formatShortAsOf(asOf)}`,
    ageHours: age,
    asOf,
  };
}
