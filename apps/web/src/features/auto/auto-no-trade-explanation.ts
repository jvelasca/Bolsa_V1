/**
 * P4 — «Por qué AUTO no operó»: read-model puro de dos capas rotuladas.
 *
 * Traduce lo que el frontend YA puede leer a las seis causas del audit, sin inventar datos:
 *
 *  - **Capa 1 · Descubrimiento** (causas 1–3): del embudo de Estudio AUTO-paper
 *    (`estudioStatus`/`estudioCount`, `autoDesk.entry.skipped` con sus motivos) y del veto
 *    global (kill switch, incidentes, propuestas vetadas).
 *  - **Capa 2 · Motor** (causas 4–6): de la traza por ciclo del monitor
 *    (`ORDER`/`FILL` + cierre), filtrada por día.
 *
 * Invariantes (audit `P4` + UI 5.0):
 * - **`UNKNOWN ≠ 0`.** Un dato que no llega se declara hueco; jamás se colapsa a «No aplica»
 *   ni a un cero afirmado. `incidentCount = -1`/`incidentsFailed` es fallo de lectura, no un 0.
 * - **Ninguna causa se afirma sin evidencia.** Donde el motor no publica el paso (p. ej. la
 *   decisión de cartera, hoy inexistente), la causa queda «Sin dato todavía».
 * - **Cada causa declarada enlaza con su registro** (`ref` → ciclo/orden que la demuestra).
 * - Determinista y sin `Date`: el día entra como parámetro.
 *
 * @see docs/engineering/auditoria-operativa-diaria-entrada-salida-dia-d-2026-10-08.md (P4)
 * @see apps/web/src/features/auto/auto-no-trade-labels.ts
 */

import { absentDataLabel } from "@/components/absent-data";
import {
  AUTO_NO_TRADE_CAUSE_LABELS,
  AUTO_NO_TRADE_DISCOVERY_CAUSES,
  AUTO_NO_TRADE_ENGINE_CAUSES,
  AUTO_NO_TRADE_LAYER_COPY,
  AUTO_NO_TRADE_STATUS_LABELS,
  AUTO_NO_TRADE_UNMEASURED_NOTE,
  entryReasonLabel,
  jitDenyLabel,
  type AutoNoTradeCauseId,
  type AutoNoTradeLayerId,
  type AutoNoTradeStatus,
} from "./auto-no-trade-labels";

// ---------------------------------------------------------------------------
// Entradas (normalizadas; el panel hace el mapeo desde los DTO, no este módulo)
// ---------------------------------------------------------------------------

export type AutoNoTradeStepFacts = {
  id: string;
  state: string;
  measurement?: string | null;
  note?: string | null;
  at?: string | null;
};

export type AutoNoTradeCycleFacts = {
  /** Identidad del ciclo (opaca aquí: este módulo no la interpreta). */
  id: string;
  closed?: boolean | null;
  closedMeasurement?: string | null;
  steps?: readonly AutoNoTradeStepFacts[] | null;
  resultClosedAt?: string | null;
};

export type AutoNoTradeAutoDeskFacts = {
  blocked?: boolean | null;
  blockReason?: string | null;
  entry?: {
    status?: string | null;
    proposed?: number | null;
    executed?: number | null;
    candidates?:
      | readonly { symbol?: string | null; instrumentId?: string | null }[]
      | null;
    skipped?:
      | readonly {
          symbol?: string | null;
          instrumentId?: string | null;
          reasonCode?: string | null;
          vetoes?: readonly string[] | null;
        }[]
      | null;
  } | null;
  jitDenies?: Record<string, number> | null;
};

export type AutoNoTradeGateFacts = {
  killOn: boolean;
  vetoed: number;
  /** `-1` = lectura de incidentes fallida (NO es un 0 medido). */
  incidentCount: number;
  incidentsFailed: boolean;
};

export type AutoNoTradeDiscoveryFacts = {
  /** ¿Respondió la consulta? Si no, toda la capa es hueco. */
  loaded: boolean;
  /** `ok` | `empty` | `unavailable` (unavailable ≠ empty). */
  estudioStatus?: string | null;
  estudioCount?: number | null;
  autoDesk?: AutoNoTradeAutoDeskFacts | null;
  gate?: AutoNoTradeGateFacts | null;
};

export type AutoNoTradeEngineFacts = {
  loaded: boolean;
  cycles?: readonly AutoNoTradeCycleFacts[] | null;
};

export type AutoNoTradeExplanationInput = {
  /** `YYYY-MM-DD` del día explicado; `null` = ventana completa. */
  day: string | null;
  discovery: AutoNoTradeDiscoveryFacts | null;
  engine: AutoNoTradeEngineFacts | null;
};

// ---------------------------------------------------------------------------
// Salidas
// ---------------------------------------------------------------------------

export type AutoNoTradeEvidenceV1 = {
  label: string;
  /** Identidad del registro que la demuestra (ciclo), si existe. */
  ref?: string | null;
};

export type AutoNoTradeRowV1 = {
  id: AutoNoTradeCauseId;
  label: string;
  status: AutoNoTradeStatus;
  statusLabel: string;
  evidence: AutoNoTradeEvidenceV1[];
};

export type AutoNoTradeLayerV1 = {
  id: AutoNoTradeLayerId;
  title: string;
  honestyNote: string;
  /** `false` si toda la capa es hueco. */
  measured: boolean;
  rows: AutoNoTradeRowV1[];
};

export type AutoNoTradeExplanationV1 = {
  day: string | null;
  layers: AutoNoTradeLayerV1[];
  headline: string;
  /** `true` si alguna causa se declara con evidencia. */
  hasDeclaredCause: boolean;
};

// ---------------------------------------------------------------------------
// Utilidades puras
// ---------------------------------------------------------------------------

/** Número medido o `null`; nunca colapsa ausencia a 0. */
function num(value: number | null | undefined): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function makeRow(
  id: AutoNoTradeCauseId,
  status: AutoNoTradeStatus,
  evidence: AutoNoTradeEvidenceV1[] = [],
): AutoNoTradeRowV1 {
  return {
    id,
    label: AUTO_NO_TRADE_CAUSE_LABELS[id],
    status,
    statusLabel: AUTO_NO_TRADE_STATUS_LABELS[status],
    evidence,
  };
}

/** ¿El ciclo tiene actividad en la fecha? (por sello de paso o de cierre). */
export function cycleBelongsToDay(
  cycle: AutoNoTradeCycleFacts,
  day: string,
): boolean {
  const stamps: Array<string | null | undefined> = [
    cycle.resultClosedAt,
    ...(cycle.steps ?? []).map((step) => step.at ?? null),
  ];
  return stamps.some(
    (stamp) => typeof stamp === "string" && stamp.startsWith(day),
  );
}

function stepState(
  cycle: AutoNoTradeCycleFacts,
  stepId: string,
): string | null {
  const step = (cycle.steps ?? []).find((item) => item.id === stepId);
  return step ? step.state : null;
}

function isConfirmedClosed(cycle: AutoNoTradeCycleFacts): boolean {
  return (
    cycle.closed === true &&
    (cycle.closedMeasurement ?? "COMPLETE") === "COMPLETE"
  );
}

/** Agrupa los motivos de las candidaturas descartadas, con orden determinista. */
function groupSkippedReasons(
  skipped: readonly {
    reasonCode?: string | null;
  }[],
): Array<[string, number]> {
  const counts = new Map<string, number>();
  for (const row of skipped) {
    const code = (row.reasonCode ?? "").trim();
    if (!code) continue;
    counts.set(code, (counts.get(code) ?? 0) + 1);
  }
  return [...counts.entries()].sort(
    (a, b) => b[1] - a[1] || a[0].localeCompare(b[0]),
  );
}

// ---------------------------------------------------------------------------
// Capa 1 · Descubrimiento (causas 1–3)
// ---------------------------------------------------------------------------

function buildDiscoveryLayer(
  discovery: AutoNoTradeDiscoveryFacts | null,
): AutoNoTradeLayerV1 {
  const loaded = discovery?.loaded === true;
  const estudioStatus = (discovery?.estudioStatus ?? "").trim();
  const autoDesk = discovery?.autoDesk ?? null;
  const entry = autoDesk?.entry ?? null;
  const gate = discovery?.gate ?? null;
  const proposed = num(entry?.proposed);
  const executed = num(entry?.executed);
  const candidates = entry?.candidates ?? null;
  const skipped = entry?.skipped ?? null;
  const candidateCount = candidates ? candidates.length : null;
  const knownCandidates = candidateCount ?? proposed;

  const rows: AutoNoTradeRowV1[] = [];

  // Causa 1 — No apareció una oportunidad.
  {
    const evidence: AutoNoTradeEvidenceV1[] = [];
    let status: AutoNoTradeStatus;
    if (!loaded) {
      status = "unknown";
    } else if (estudioStatus === "unavailable") {
      status = "unknown";
      evidence.push({
        label:
          "El universo de Estudio no está disponible; no se interpreta como cero candidatos.",
      });
    } else if (estudioStatus === "empty") {
      status = "occurred";
      evidence.push({ label: "El universo de Estudio está vacío." });
    } else if (knownCandidates === null) {
      status = "unknown";
      evidence.push({ label: AUTO_NO_TRADE_UNMEASURED_NOTE });
    } else if (knownCandidates === 0) {
      status = "occurred";
      evidence.push({ label: "No se registraron candidatos en el ciclo." });
    } else {
      status = "not_applicable";
      evidence.push({
        label: `${knownCandidates} candidatura(s) detectada(s).`,
      });
    }
    rows.push(makeRow("no_opportunity", status, evidence));
  }

  // Causa 2 — Había candidatos, pero ninguno superó la selección.
  {
    const evidence: AutoNoTradeEvidenceV1[] = [];
    let status: AutoNoTradeStatus;
    if (!loaded) {
      status = "unknown";
    } else if (skipped && skipped.length > 0) {
      status = "occurred";
      evidence.push({
        label: `${skipped.length} candidatura(s) descartada(s).`,
      });
      for (const [code, count] of groupSkippedReasons(skipped)) {
        evidence.push({ label: `${entryReasonLabel(code)}: ${count}` });
      }
    } else if (knownCandidates === null) {
      status = "unknown";
      evidence.push({ label: AUTO_NO_TRADE_UNMEASURED_NOTE });
    } else if (knownCandidates === 0) {
      status = "not_applicable";
    } else if (executed === null) {
      status = "unknown";
      evidence.push({ label: AUTO_NO_TRADE_UNMEASURED_NOTE });
    } else if (executed <= 0) {
      status = "occurred";
      evidence.push({
        label:
          "Hubo candidatos y ninguno llegó a ejecutarse; sin motivo declarado.",
      });
    } else {
      status = "not_applicable";
    }
    rows.push(makeRow("no_selection", status, evidence));
  }

  // Causa 3 — Veto de riesgo o de régimen.
  {
    const evidence: AutoNoTradeEvidenceV1[] = [];
    let vetoed = false;
    if (gate?.killOn) {
      evidence.push({ label: "Interruptor de seguridad activo." });
      vetoed = true;
    }
    if (gate && !gate.incidentsFailed && gate.incidentCount > 0) {
      evidence.push({
        label: `${gate.incidentCount} incidente(s) operativo(s) abierto(s).`,
      });
      vetoed = true;
    }
    if (gate && gate.vetoed > 0) {
      evidence.push({
        label: `${gate.vetoed} propuesta(s) vetada(s) en el tablero.`,
      });
      vetoed = true;
    }
    for (const [code, count] of Object.entries(autoDesk?.jitDenies ?? {})) {
      if ((count ?? 0) > 0) {
        evidence.push({ label: `${jitDenyLabel(code)}: ${count}` });
        vetoed = true;
      }
    }
    if (autoDesk?.blocked) {
      const mapped = autoDesk.blockReason
        ? jitDenyLabel(autoDesk.blockReason)
        : absentDataLabel();
      evidence.push({
        label:
          mapped === absentDataLabel()
            ? "Bloqueo declarado por el ciclo de entrada."
            : `Bloqueo: ${mapped}`,
      });
      vetoed = true;
    }
    const vetoedCandidates = (skipped ?? []).filter(
      (row) => (row.vetoes ?? []).length > 0,
    );
    if (vetoedCandidates.length > 0) {
      evidence.push({
        label: `${vetoedCandidates.length} candidatura(s) con veto de riesgo.`,
      });
      vetoed = true;
    }

    let status: AutoNoTradeStatus;
    if (vetoed) status = "occurred";
    else if (!loaded) status = "unknown";
    else if (gate?.incidentsFailed) status = "unknown";
    else if (entry === null && gate === null) status = "unknown";
    else status = "not_applicable";
    rows.push(makeRow("risk_regime_veto", status, evidence));
  }

  return {
    id: "discovery",
    title: AUTO_NO_TRADE_LAYER_COPY.discovery.title,
    honestyNote: AUTO_NO_TRADE_LAYER_COPY.discovery.honestyNote,
    measured: rows.some((row) => row.status !== "unknown"),
    rows,
  };
}

// ---------------------------------------------------------------------------
// Capa 2 · Motor AUTO (causas 4–6)
// ---------------------------------------------------------------------------

function buildEngineLayer(
  engine: AutoNoTradeEngineFacts | null,
  day: string | null,
): AutoNoTradeLayerV1 {
  const loaded = engine?.loaded === true;
  const all = engine?.cycles ?? [];
  const cycles = day
    ? all.filter((cycle) => cycleBelongsToDay(cycle, day))
    : all;

  const rows: AutoNoTradeRowV1[] = [];
  const noReading = !loaded || cycles.length === 0;
  const firstRef = cycles[0]?.id ?? null;

  const refOf = (
    predicate: (cycle: AutoNoTradeCycleFacts) => boolean,
  ): string | null => cycles.find(predicate)?.id ?? firstRef;

  // Causa 4 — Se aprobó una decisión, pero no se creó una orden.
  {
    const progressed = cycles.filter(
      (cycle) =>
        stepState(cycle, "RISK") === "reached" ||
        stepState(cycle, "RESERVATION") === "reached",
    );
    const evidence: AutoNoTradeEvidenceV1[] = [];
    let status: AutoNoTradeStatus;
    if (noReading || progressed.length === 0) {
      status = noReading ? "unknown" : "not_applicable";
    } else if (progressed.some((c) => stepState(c, "ORDER") === "reached")) {
      status = "not_applicable";
    } else if (progressed.some((c) => stepState(c, "ORDER") === "absent")) {
      status = "occurred";
      evidence.push({ label: "No se creó ninguna orden para la decisión." });
      evidence.push({
        label: `${progressed.length} ciclo(s) con decisión sin orden.`,
      });
    } else {
      // `unknown`/ausente: no se distingue «no se creó» de «no durable».
      status = "unknown";
      evidence.push({
        label:
          "El paso «orden» no es medible: no se distingue «no se creó» de «no quedó registrada».",
      });
    }
    rows.push(
      makeRow(
        "decision_without_order",
        status,
        status === "occurred"
          ? evidence.map((item) => ({
              ...item,
              ref: refOf((c) => stepState(c, "ORDER") === "absent"),
            }))
          : evidence,
      ),
    );
  }

  // Causa 5 — Se creó una orden, pero no llegó a ejecutarse.
  {
    const withOrder = cycles.filter(
      (cycle) => stepState(cycle, "ORDER") === "reached",
    );
    const evidence: AutoNoTradeEvidenceV1[] = [];
    let status: AutoNoTradeStatus;
    if (noReading) {
      status = "unknown";
    } else if (withOrder.length === 0) {
      status = "not_applicable";
    } else {
      const pending = withOrder.filter((c) => {
        const state = stepState(c, "FILL");
        return state === "pending" || state === "absent";
      });
      const filled = withOrder.filter(
        (c) => stepState(c, "FILL") === "reached",
      );
      if (pending.length > 0) {
        status = "occurred";
        evidence.push({
          label: "La orden no registró ejecución.",
          ref: refOf((c) => {
            const state = stepState(c, "FILL");
            return state === "pending" || state === "absent";
          }),
        });
        evidence.push({ label: `${pending.length} orden(es) sin ejecución.` });
      } else if (filled.length > 0) {
        status = "not_applicable";
      } else {
        status = "unknown";
        evidence.push({ label: "La ejecución de la orden no es medible." });
      }
    }
    rows.push(makeRow("order_without_fill", status, evidence));
  }

  // Causa 6 — Se ejecutó, pero falta confirmar la posición o el resultado.
  {
    const withFill = cycles.filter(
      (cycle) => stepState(cycle, "FILL") === "reached",
    );
    const evidence: AutoNoTradeEvidenceV1[] = [];
    let status: AutoNoTradeStatus;
    if (noReading) {
      status = "unknown";
    } else if (withFill.length === 0) {
      status = "not_applicable";
    } else {
      const unconfirmed = withFill.filter((c) => !isConfirmedClosed(c));
      const confirmed = withFill.filter((c) => isConfirmedClosed(c));
      if (unconfirmed.length > 0) {
        status = "occurred";
        evidence.push({
          label: "La posición o el resultado no están confirmados.",
          ref: refOf((c) => !isConfirmedClosed(c)),
        });
        evidence.push({
          label: `${unconfirmed.length} operación(es) sin confirmar.`,
        });
      } else if (confirmed.length > 0) {
        status = "not_applicable";
      } else {
        status = "unknown";
        evidence.push({ label: "El cierre de la operación no es medible." });
      }
    }
    rows.push(makeRow("execution_unconfirmed", status, evidence));
  }

  return {
    id: "engine",
    title: AUTO_NO_TRADE_LAYER_COPY.engine.title,
    honestyNote: AUTO_NO_TRADE_LAYER_COPY.engine.honestyNote,
    measured: rows.some((row) => row.status !== "unknown"),
    rows,
  };
}

// ---------------------------------------------------------------------------
// Constructor
// ---------------------------------------------------------------------------

export function buildAutoNoTradeExplanation(
  input: AutoNoTradeExplanationInput,
): AutoNoTradeExplanationV1 {
  const discovery = buildDiscoveryLayer(input.discovery);
  const engine = buildEngineLayer(input.engine, input.day);
  const layers = [discovery, engine];

  const declared = layers
    .flatMap((layer) => layer.rows)
    .find((row) => row.status === "occurred");

  const headline = declared
    ? `Primera causa declarada: ${declared.label}.`
    : "No hay una causa declarada con los datos disponibles; los huecos se señalan como «Sin dato todavía».";

  return {
    day: input.day,
    layers,
    headline,
    hasDeclaredCause: Boolean(declared),
  };
}

/** Orden canónico de las causas en la explicación (para tests y consumidores). */
export const AUTO_NO_TRADE_CAUSE_ORDER: readonly AutoNoTradeCauseId[] = [
  ...AUTO_NO_TRADE_DISCOVERY_CAUSES,
  ...AUTO_NO_TRADE_ENGINE_CAUSES,
] as const;
