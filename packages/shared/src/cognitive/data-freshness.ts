/**
 * Contrato unificado de frescura de datos (UI + Risk Gate DS-05).
 */

export type DataFreshnessStatusV1 =
  | "unknown"
  | "fresh"
  | "stale"
  | "missing"
  | "invalid"
  | "error";

export type DataFreshnessV1 = {
  asOf: string | null;
  source: string;
  ageMinutes: number | null;
  status: DataFreshnessStatusV1;
  thresholdMinutes: number;
  label: string;
};

export const DATA_FRESHNESS_THRESHOLD_MINUTES = 5 * 24 * 60;

export function buildDataFreshness(input: {
  lastBarDate?: string | null;
  queryFailed?: boolean;
  now?: Date;
  thresholdMinutes?: number;
  source?: string;
}): DataFreshnessV1 {
  const thresholdMinutes =
    input.thresholdMinutes ?? DATA_FRESHNESS_THRESHOLD_MINUTES;
  const source = input.source ?? "ohlcv";

  if (input.queryFailed) {
    return {
      asOf: null,
      source,
      ageMinutes: null,
      status: "error",
      thresholdMinutes,
      label: "No consultado",
    };
  }

  const raw = input.lastBarDate?.trim();
  if (!raw) {
    return {
      asOf: null,
      source,
      ageMinutes: null,
      status: "unknown",
      thresholdMinutes,
      label: "—",
    };
  }

  const ts = new Date(raw);
  if (Number.isNaN(ts.getTime())) {
    return {
      asOf: raw,
      source,
      ageMinutes: null,
      status: "invalid",
      thresholdMinutes,
      label: "—",
    };
  }

  const now = input.now ?? new Date();
  const ageMinutes = Math.max(
    0,
    Math.floor((now.getTime() - ts.getTime()) / 60_000),
  );
  const asOf = ts.toISOString();

  if (ageMinutes > thresholdMinutes) {
    return {
      asOf,
      source,
      ageMinutes,
      status: "stale",
      thresholdMinutes,
      label: `Retrasados · ${formatAgeMinutes(ageMinutes)}`,
    };
  }

  return {
    asOf,
    source,
    ageMinutes,
    status: "fresh",
    thresholdMinutes,
    label: `Actualizados · ${formatAgeMinutes(ageMinutes)}`,
  };
}

function formatAgeMinutes(minutes: number): string {
  if (minutes < 60) return `${minutes} min`;
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  if (h < 48) return m > 0 ? `${h}h ${m}m` : `${h}h`;
  const d = Math.floor(h / 24);
  return `${d}d`;
}

/** Compat Mesa chip — mapea contrato unificado a forma legacy. */
export type MesaDataFreshnessChipV1 =
  | { state: "unknown"; label: string }
  | { state: "fresh"; label: string; ageMinutes: number }
  | { state: "stale"; label: string; ageMinutes: number }
  | { state: "error"; label: string };

export function mesaDataFreshnessFromContract(
  freshness: DataFreshnessV1,
): MesaDataFreshnessChipV1 {
  if (freshness.status === "error") {
    return { state: "error", label: freshness.label };
  }
  if (freshness.status === "fresh" && freshness.ageMinutes != null) {
    return {
      state: "fresh",
      label: freshness.label,
      ageMinutes: freshness.ageMinutes,
    };
  }
  if (freshness.status === "stale" && freshness.ageMinutes != null) {
    return {
      state: "stale",
      label: freshness.label,
      ageMinutes: freshness.ageMinutes,
    };
  }
  return { state: "unknown", label: freshness.label };
}
