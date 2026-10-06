/**
 * AUTO UI 3.1 — las seis respuestas de la HOME (helper puro).
 *
 * Copia hechos ya producidos. No inventa acción, símbolo, decisión ni cabecera.
 * La decisión de cartera y la materialización no tienen traza: se declaran.
 *
 * @see docs/engineering/spec-auto-operacion-usuario-basico-2026-10-06.md §3 §5
 */

import {
  AUTO_HOME_NO_DATA_LABEL,
  engineStateLabel,
} from "@/features/auto/auto-home-summary";

export const AUTO_SIMULATION_BANNER = "SIMULACIÓN — DINERO VIRTUAL";
export const AUTO_NO_CURRENT_OPERATION = "Sin operación en curso";
export const AUTO_HEADER_ORDER_PENDING = "Orden pendiente";
export const AUTO_HEADER_PARTIAL = "Ejecución parcial";
export const AUTO_HEADER_PRICE_APPLIED = "Precio aplicado";

export type AutoBasicStepFact = {
  key: string;
  value: unknown;
  measurement?: string | null;
};

export type AutoBasicStep = {
  id: string;
  state: string;
  measurement?: string | null;
  facts?: readonly AutoBasicStepFact[] | null;
};

export type AutoBasicCycle = {
  cycleId: string;
  instrumentId?: string | null;
  closed?: boolean | null;
  closedMeasurement?: string | null;
  steps?: readonly AutoBasicStep[] | null;
};

export type AutoBasicHomeInput = {
  isLoading?: boolean;
  isError?: boolean;
  /** `null` = el monitor no trajo cabecera. */
  header?: { state?: string | null } | null;
  cycles?: readonly AutoBasicCycle[] | null;
};

export type AutoBasicCurrentOperation = {
  cycleId: string;
  /** Símbolo medido, o `Sin dato todavía`. */
  symbol: string;
  happened: string;
};

export type AutoBasicHomeV1 = {
  isLoading: boolean;
  isError: boolean;
  /** ¿AUTO está funcionando? */
  workingLabel: string;
  /** ¿Qué está haciendo? Sin hecho de acción, no se inventa. */
  doingLabel: string;
  /** ¿Qué activo? */
  assetLabel: string;
  /** ¿Qué ha decidido? Hoy no hay `PortfolioDecision` durable. */
  decisionLabel: string;
  /** ¿Qué ha ocurrido realmente? */
  happenedLabel: string;
  /** ¿Qué dinero utiliza? */
  moneyLabel: string;
  currentOperations: AutoBasicCurrentOperation[];
};

function stepOf(cycle: AutoBasicCycle, id: string): AutoBasicStep | undefined {
  return (cycle.steps ?? []).find((step) => step.id === id);
}

function reached(step: AutoBasicStep | undefined): boolean {
  return step?.state === "reached";
}

/** Orden o fill ya alcanzados, cierre medido como no cerrado. Una reserva no entra. */
export function isOperationInCourse(cycle: AutoBasicCycle): boolean {
  if (cycle.closed !== false) return false;
  if ((cycle.closedMeasurement ?? "COMPLETE") !== "COMPLETE") return false;
  return reached(stepOf(cycle, "ORDER")) || reached(stepOf(cycle, "FILL"));
}

export function readEntryQuantities(cycle: AutoBasicCycle): {
  requested: number | null;
  applied: number | null;
} {
  const fact = (stepOf(cycle, "ORDER")?.facts ?? []).find(
    (item) => item.key === "entryOrder",
  );
  if (
    !fact ||
    fact.measurement === "UNKNOWN" ||
    fact.measurement === "PARTIAL"
  ) {
    return { requested: null, applied: null };
  }
  if (!fact.value || typeof fact.value !== "object") {
    return { requested: null, applied: null };
  }
  const row = fact.value as Record<string, unknown>;
  const requested =
    typeof row.requestedQty === "number" ? row.requestedQty : null;
  const applied = typeof row.appliedQty === "number" ? row.appliedQty : null;
  return { requested, applied };
}

/**
 * Cabecera §5. No hay traza de apply, así que no dice «Materializada» ni «Completada».
 * Un fill sin cantidad pedida y aplicada medidas no se llama «Precio aplicado».
 */
export function operationHappenedLabel(cycle: AutoBasicCycle): string {
  const order = stepOf(cycle, "ORDER");
  const fill = stepOf(cycle, "FILL");
  const orderReached = reached(order);
  const fillReached = reached(fill);

  if (fillReached && !orderReached) return AUTO_HOME_NO_DATA_LABEL;
  if (!orderReached) return AUTO_HOME_NO_DATA_LABEL;
  if (!fill) return AUTO_HOME_NO_DATA_LABEL;
  if (!fillReached) {
    return fill.state === "pending"
      ? AUTO_HEADER_ORDER_PENDING
      : AUTO_HOME_NO_DATA_LABEL;
  }
  if (fill.measurement != null && fill.measurement !== "COMPLETE") {
    return AUTO_HOME_NO_DATA_LABEL;
  }

  const { requested, applied } = readEntryQuantities(cycle);
  if (requested == null || applied == null) return AUTO_HOME_NO_DATA_LABEL;
  if (applied < requested) return AUTO_HEADER_PARTIAL;
  if (applied === requested) return AUTO_HEADER_PRICE_APPLIED;
  return AUTO_HOME_NO_DATA_LABEL;
}

function symbolOf(cycle: AutoBasicCycle): string {
  const symbol = cycle.instrumentId?.trim();
  return symbol ? symbol : AUTO_HOME_NO_DATA_LABEL;
}

export function buildAutoBasicHome(input: AutoBasicHomeInput): AutoBasicHomeV1 {
  const isLoading = input.isLoading === true;
  const isError = input.isError === true;
  const loaded = !isLoading && !isError && input.header != null;

  const currentOperations = loaded
    ? (input.cycles ?? []).filter(isOperationInCourse).map((cycle) => ({
        cycleId: cycle.cycleId,
        symbol: symbolOf(cycle),
        happened: operationHappenedLabel(cycle),
      }))
    : [];

  const symbols = currentOperations.map((operation) => operation.symbol);
  const assetLabel =
    currentOperations.length === 0
      ? AUTO_HOME_NO_DATA_LABEL
      : symbols.every((symbol) => symbol !== AUTO_HOME_NO_DATA_LABEL)
        ? [...new Set(symbols)].join(", ")
        : AUTO_HOME_NO_DATA_LABEL;

  let happenedLabel = AUTO_NO_CURRENT_OPERATION;
  if (!loaded) {
    happenedLabel = AUTO_HOME_NO_DATA_LABEL;
  } else if (currentOperations.length === 1) {
    happenedLabel = currentOperations[0]!.happened;
  } else if (currentOperations.length > 1) {
    happenedLabel = `${currentOperations.length} operaciones en curso`;
  }

  return {
    isLoading,
    isError,
    workingLabel: loaded
      ? engineStateLabel(input.header?.state)
      : AUTO_HOME_NO_DATA_LABEL,
    doingLabel: AUTO_HOME_NO_DATA_LABEL,
    assetLabel: loaded ? assetLabel : AUTO_HOME_NO_DATA_LABEL,
    decisionLabel: AUTO_HOME_NO_DATA_LABEL,
    happenedLabel,
    moneyLabel: AUTO_SIMULATION_BANNER,
    currentOperations,
  };
}
