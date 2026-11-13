/**
 * DTOs del método **DÍA-D retrospectivo as-run** (ADR-049).
 *
 * El artefacto rejuega la operativa que REALMENTE llevábamos desde un día D pasado y la
 * compara con brazos contrafactuales (`hold_structural`, `cash`, `engine_params`,
 * `candidate`) y con un benchmark de mercado (`market_bh`). Un brazo no medible llega con
 * `measured=false`, `realizedR=null` y un motivo: un hueco declarado, nunca un `0` que se
 * lea como resultado.
 *
 * `audit` conserva la congelación temporal (estado de D, huella de barras, versiones y
 * decisiones) para poder reproducir la simulación. `certification` dice si el MÉTODO es
 * válido; no dice si el resultado es bueno y no autoriza nada.
 *
 * Read-only: la UI lo muestra, no lo ejecuta. La ejecución vive en la cola `auto_ops_jobs`.
 */

export type DiaDAsRunDecisionV1 = {
  date: string | null;
  instrument: string;
  action: string;
  price: number | null;
  reason: string;
};

export type DiaDAsRunArmV1 = {
  arm: string;
  measured: boolean;
  reason: string | null;
  realizedR: number | null;
  pnlCurrency: number | null;
  maeR: number | null;
  mfeR: number | null;
  capture: number | null;
  /** Retorno porcentual del brazo (el benchmark `market_bh` solo publica esto). */
  returnPct: number | null;
  exits: number;
  stops: number;
  targets: number;
  legs: number;
  /** Lotes sembrados del estado arrastrado a `D` (inventario previo reconstruido incluido). */
  carriedInLots?: number;
  /**
   * Posiciones cerradas contadas por **episodio de tenencia**, no por fill: una orden
   * troceada en varios fills es una posición y una reentrada tras quedar plano es otra.
   * `exits` cuenta tramos de venta.
   */
  cycles?: number;
  /**
   * Riesgo en moneda de las posiciones medidas (`Σ riesgo_por_unidad × cantidad`).
   * `pnlCurrency / riskCurrency` es el R de cartera; `realizedR` es la suma de R por
   * posición (cada posición pesa igual, arriesgue lo que arriesgue).
   */
  riskCurrency?: number | null;
  /** Denominador de R aplicado por instrumento (`durable_journal` / `state_at_d`). */
  riskSource?: Record<string, string>;
  reasonCodes: string[];
  decisions: DiaDAsRunDecisionV1[];
};

export type DiaDAsRunStartingStateV1 = {
  legs?: number;
  instruments?: string[];
  cashOnly?: boolean;
};

/** Base de coste de los fills REALES del brazo `as_run`. */
export type DiaDAsRunRealFillsCostBasis = "quoted" | "effective";

/** Modelo de ejecución declarado: coste, deslizamiento y cota de liquidez. */
export type DiaDAsRunExecutionModelV1 = {
  commissionBps: number;
  slippageBps: number;
  spreadBps: number;
  roundTripBps: number;
  executionCostBps: number;
  maxParticipationPct: number | null;
  gapPolicy: string;
  /**
   * `quoted`: el precio del fill es bruto y el coste se cobra en caja.
   * `effective`: el precio ya es neto de coste y `executionCostBps` es 0.
   */
  realFillsCostBasis: DiaDAsRunRealFillsCostBasis;
};

export type DiaDAsRunAuditLegV1 = {
  instrumentId: string;
  direction: string;
  quantity: number;
  entry: number;
  structuralStop: number | null;
  target1: number | null;
  target2: number | null;
};

/** Sobre de auditoría: qué se sabía en D, con qué datos y con qué versiones. */
export type DiaDAsRunAuditV1 = {
  pointInTime: {
    day: string;
    toDay: string | null;
    stateSource: string | null;
    sourceIsReconstructed: boolean;
    legsHash: string;
    legs: DiaDAsRunAuditLegV1[];
    candidateAsOf: string | null;
    /** Universo de D. Solo `declared` permite certificar el estado inicial. */
    universe?: string[];
    universeSource?: "declared" | "derived";
  };
  data: {
    barsSource: string | null;
    timeframe: string | null;
    barsHash: string;
    /** Una huella sha256 por vela: cambiar una vela rompe `barsHash`. */
    barsManifest?: Record<string, Array<[string, string]>>;
    instruments: Array<{
      instrument: string;
      bars: number;
      firstBar: string | null;
      lastBar: string | null;
    }>;
  };
  versions: {
    engine: string;
    schema: string;
    bump: string | null;
    strategy: string | null;
    mandate: string | null;
    paramsHash: string | null;
  };
  /** Parámetros declarados: su hash se recomputa en la certificación. */
  params?: Record<string, unknown> | null;
  execution: DiaDAsRunExecutionModelV1;
  /** Qué benchmark se comparó y con qué capital/periodo/coste. */
  benchmark?: {
    universe: string[];
    capitalBasis: "initial_notional" | "unit";
    capital: number | null;
    costBps: number;
    toDay: string | null;
  };
  decisions: Record<string, DiaDAsRunDecisionV1[]>;
  limits: string[];
};

export type DiaDAsRunCertificationStatusV1 =
  | "certified"
  | "not_certified"
  | "insufficient_sample";

export type DiaDAsRunCertificationCheckV1 = {
  name: string;
  status: "PASS" | "FAIL" | "NOT_EVALUATED";
  reason: string | null;
};

/** Certificación del MÉTODO (no del resultado ni de la rentabilidad). */
export type DiaDAsRunCertificationV1 = {
  version: string;
  verdict: DiaDAsRunCertificationStatusV1;
  certified: boolean;
  checks: DiaDAsRunCertificationCheckV1[];
  failures: string[];
  notEvaluated: string[];
  reasons: string[];
  hash: string;
};

export type DiaDAsRunArtifactV1 = {
  available: boolean;
  readOnly: boolean;
  day: string;
  /** `measured` | `not_measured` — el método declara si pudo medir algo. */
  status: string | null;
  schemaVersion: string | null;
  costBps: number | null;
  startingState: DiaDAsRunStartingStateV1;
  arms: DiaDAsRunArmV1[];
  gaps: Array<{ arm: string; reason: string }>;
  hash: string | null;
  artifactModifiedAt: string | null;
  meta: Record<string, unknown>;
  notes: string[];
  /** Ausente en artefactos v1: la certificación declarará `not_certified`. */
  audit?: DiaDAsRunAuditV1 | null;
  certification?: DiaDAsRunCertificationV1 | null;
};

/** Contrato vigente: sobre de auditoría presente. Los v1 se siguen leyendo. */
export type DiaDAsRunArtifactV2 = DiaDAsRunArtifactV1 & {
  schemaVersion: string;
  audit: DiaDAsRunAuditV1;
};

export type DiaDAsRunListV1 = {
  readOnly: boolean;
  days: string[];
  notes: string[];
};

export type DiaDAsRunJobV1 = {
  id: string;
  kind: string;
  status: string;
  day: string;
  created: boolean;
};

/** Orden canónico de brazos para presentación (el artefacto ya llega ordenado). */
export const DIA_D_AS_RUN_ARMS = [
  "as_run",
  "hold_structural",
  "cash",
  "engine_params",
  "candidate",
  "market_bh",
] as const;
