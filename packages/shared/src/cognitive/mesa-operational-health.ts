/**
 * Estado operativo descompuesto — proyección para Mesa (no canónico único).
 */

import type { DataFreshnessStatusV1 } from "./data-freshness.js";

export type HealthLevelV1 = "ok" | "degraded" | "blocked" | "unknown";

export type MesaHealthDimensionsV1 = {
  systemHealth: HealthLevelV1;
  dataHealth: HealthLevelV1;
  riskState: HealthLevelV1;
  executionReadiness: HealthLevelV1;
  marketState: HealthLevelV1;
  sessionState: HealthLevelV1;
};

export type MesaOperationalStatusLevelV1 = "normal" | "attention" | "blocked";

const STATUS_LABEL: Record<MesaOperationalStatusLevelV1, string> = {
  normal: "Normal",
  attention: "Atención",
  blocked: "Bloqueado",
};

export function buildMesaHealthDimensions(input: {
  killSwitchEffective?: boolean;
  incidentCount?: number;
  entriesBlocked?: boolean;
  vetoed?: number;
  queryFailed?: boolean;
  dataFreshnessStatus?: DataFreshnessStatusV1;
  readinessState?: string | null;
  brokerVenue?: "paper" | "live" | null;
}): MesaHealthDimensionsV1 {
  const queryFailed = Boolean(input.queryFailed);
  const incidents = input.incidentCount ?? 0;

  let systemHealth: HealthLevelV1 = "ok";
  if (input.killSwitchEffective || incidents > 0) systemHealth = "blocked";
  else if (queryFailed) systemHealth = "degraded";

  let dataHealth: HealthLevelV1 = "unknown";
  const dfs = input.dataFreshnessStatus ?? "unknown";
  if (dfs === "fresh") dataHealth = "ok";
  else if (dfs === "stale" || dfs === "invalid") dataHealth = "degraded";
  else if (dfs === "error" || dfs === "missing") dataHealth = "degraded";
  else dataHealth = "unknown";

  let riskState: HealthLevelV1 = "ok";
  if (input.killSwitchEffective) riskState = "blocked";
  else if ((input.vetoed ?? 0) > 0 || input.entriesBlocked) {
    riskState = "degraded";
  }

  let executionReadiness: HealthLevelV1 = "ok";
  const readiness = input.readinessState?.toUpperCase() ?? "";
  if (readiness.includes("BLOCKED")) executionReadiness = "blocked";
  else if (
    readiness.includes("DEGRADED") ||
    readiness.includes("EXPERIMENTAL")
  ) {
    executionReadiness = "degraded";
  }

  const marketState: HealthLevelV1 =
    dfs === "fresh" ? "ok" : dfs === "unknown" ? "unknown" : "degraded";

  const sessionState: HealthLevelV1 =
    input.entriesBlocked || incidents > 0 ? "degraded" : "ok";

  return {
    systemHealth,
    dataHealth,
    riskState,
    executionReadiness,
    marketState,
    sessionState,
  };
}

export function projectMesaOperationalStatus(
  dimensions: MesaHealthDimensionsV1,
): MesaOperationalStatusLevelV1 {
  const levels = Object.values(dimensions);
  if (levels.some((l) => l === "blocked")) return "blocked";
  if (levels.some((l) => l === "degraded" || l === "unknown")) {
    return "attention";
  }
  return "normal";
}

export function mesaOperationalStatusLabel(
  status: MesaOperationalStatusLevelV1,
): string {
  return STATUS_LABEL[status];
}

export type MesaOperationalStatusDetailV1 = {
  status: MesaOperationalStatusLevelV1;
  statusLabel: string;
  dimensions: MesaHealthDimensionsV1;
  primaryReason: string | null;
};

export function buildMesaOperationalStatusDetail(input: {
  killSwitchEffective?: boolean;
  incidentCount?: number;
  entriesBlocked?: boolean;
  vetoed?: number;
  queryFailed?: boolean;
  dataFreshnessStatus?: DataFreshnessStatusV1;
  readinessState?: string | null;
  brokerVenue?: "paper" | "live" | null;
}): MesaOperationalStatusDetailV1 {
  const dimensions = buildMesaHealthDimensions(input);
  const status = projectMesaOperationalStatus(dimensions);

  let primaryReason: string | null = null;
  if (input.killSwitchEffective) primaryReason = "Kill switch activo";
  else if ((input.incidentCount ?? 0) > 0) {
    primaryReason = "Incidente operativo activo";
  } else if (dimensions.executionReadiness === "degraded") {
    primaryReason = `Broker/readiness: ${input.readinessState ?? "degradado"}`;
  } else if (dimensions.dataHealth === "degraded") {
    primaryReason = "Datos de mercado retrasados";
  } else if (input.entriesBlocked) {
    primaryReason = "Entradas bloqueadas";
  }

  return {
    status,
    statusLabel: mesaOperationalStatusLabel(status),
    dimensions,
    primaryReason,
  };
}
