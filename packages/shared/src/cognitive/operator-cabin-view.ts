/**
 * V2.x — Operator cabin presentation (MERCADO).
 * Maps existing truths → operator language. Not a second FSM / cockpit phase.
 * Confirm = firma · Ranking ≠ BUY · no COMPRAR shortcut.
 *
 * @see docs/engineering/diseno-mercado-2-0-cockpit-2026-08-27.md
 */

import type { EntryOperatingPhaseV1 } from "./entry-operating-copy.js";
import type { EntryOperatingTruthV1 } from "./entry-operating-truth.js";
import type { MercadoCockpitPhase } from "./mercado-cockpit-phase.js";
import type { PaperDeskNextActionV1 } from "./operational-context.js";
import type { PaperAutoPostureV1 } from "./paper-auto-posture.js";
import type { PositionJourneyReadoutV1 } from "./position-journey-readout.js";
import {
  resolveExitPolicy,
  type ExitPolicyV1,
  type ExitTrailWidthV1,
} from "./exit-policy.js";

/** Visual tone for NEXT ACTION hero. */
export type OperatorNextActionToneV1 =
  | "wait_trigger"
  | "entry_ready"
  | "maintain"
  | "protect"
  | "exit"
  | "watch"
  | "review"
  | "none";

export type OperatorNextActionV1 = {
  tone: OperatorNextActionToneV1;
  /** Hero title — ESPERAR TRIGGER · ENTRADA LISTA · MANTENER · … */
  title: string;
  /** One-line support under the title. */
  subtitle: string | null;
  /** CTA honesty (Confirm / AUTO); never COMPRAR. */
  ctaHint: string | null;
  /**
   * V2.11 — what must happen / what changes the action (from Operating Truth).
   * e.g. "confirmar cierre > 184,20"
   */
  condition?: string | null;
  /** V2.11 — vigencia / caducidad from EntryOperatingTruth.expiryLabel */
  expires?: string | null;
  /** V2.11 — key levels for the hero (entry / trigger / stop). */
  levels?: {
    entry?: number | null;
    trigger?: number | null;
    stop?: number | null;
  } | null;
};

/** V2.11 — single facade input; React must not fork if-chains. */
export type OperatorCabinTruthV1 =
  | {
      kind: "cockpit_phase";
      phase: MercadoCockpitPhase;
    }
  | {
      kind: "entry";
      truth: EntryOperatingTruthV1;
      paperAuto?: PaperAutoPostureV1 | null;
    }
  | {
      kind: "position";
      primaryAction: PaperDeskNextActionV1;
      journey?: PositionJourneyReadoutV1 | null;
    };

/**
 * V2.11 — canonical NEXT ACTION resolver. All surfaces consume this.
 * Delegates to existing builders (not a second FSM).
 */
export function resolveOperatorNextAction(
  truth: OperatorCabinTruthV1,
): OperatorNextActionV1 {
  switch (truth.kind) {
    case "cockpit_phase":
      return enrichNextAction(
        buildOperatorNextActionFromCockpitPhase(truth.phase),
      );
    case "entry":
      return enrichNextAction(
        buildOperatorNextActionFromEntry(truth.truth, {
          paperAuto: truth.paperAuto,
        }),
        {
          condition: entryCondition(truth.truth),
          expires: truth.truth.expiryLabel,
          levels: {
            entry: truth.truth.plan.entry,
            trigger: truth.truth.plan.entry,
            stop: truth.truth.plan.stopVigente,
          },
        },
      );
    case "position":
      return enrichNextAction(
        buildOperatorNextActionFromPosition(truth.primaryAction, truth.journey),
        {
          condition: positionCondition(truth.primaryAction, truth.journey),
          levels: {
            entry: truth.journey?.entry ?? null,
            stop:
              truth.journey?.trail.currentStop ??
              truth.journey?.risk.initialStop ??
              null,
          },
        },
      );
  }
}

function enrichNextAction(
  base: OperatorNextActionV1,
  extra?: {
    condition?: string | null;
    expires?: string | null;
    levels?: OperatorNextActionV1["levels"];
  },
): OperatorNextActionV1 {
  return {
    ...base,
    condition: extra?.condition ?? base.condition ?? null,
    expires: extra?.expires ?? base.expires ?? null,
    levels: extra?.levels ?? base.levels ?? null,
  };
}

function entryCondition(truth: EntryOperatingTruthV1): string | null {
  const entry = truth.plan.entry;
  if (truth.phase === "preparada" && finite(entry)) {
    return `Confirmar cierre > ${formatLevel(entry)}`;
  }
  if (truth.phase === "disparada" || truth.phase === "propuesta") {
    return truth.triggerLabel
      ? `Trigger: ${truth.triggerLabel}`
      : "Trigger confirmado — revisar y firmar en Confirm";
  }
  return null;
}

function positionCondition(
  primaryAction: PaperDeskNextActionV1,
  journey?: PositionJourneyReadoutV1 | null,
): string | null {
  const stop = journey?.trail.currentStop ?? journey?.risk.initialStop ?? null;
  const unprotected =
    journey != null &&
    !finite(journey.trail.currentStop) &&
    !finite(journey.risk.initialStop);
  if (unprotected) {
    return "Aplicar stop de emergencia (−5 %) o definir stop técnico";
  }
  if (primaryAction === "SUBIR_STOP" && finite(stop)) {
    return `Elevar stop hacia ${formatLevel(stop)}`;
  }
  if (primaryAction === "REDUCIR") {
    if (!journey?.t1.executed && journey?.t1.trigger != null) {
      return `Si alcanza ${formatLevel(journey.t1.trigger)} → reducir T1`;
    }
    if (!journey?.t2.executed && journey?.t2.trigger != null) {
      return `Si alcanza ${formatLevel(journey.t2.trigger)} → reducir T2`;
    }
  }
  if (
    (primaryAction === "MANTENER" || primaryAction === "MONITOR") &&
    !journey?.t1.executed &&
    journey?.t1.trigger != null
  ) {
    return `Mantener hasta T1 ${formatLevel(journey.t1.trigger)}`;
  }
  return null;
}

/** Operator-facing stage along the visible journey (not MercadoCockpitPhase). */
export type OperatorJourneyStageV1 =
  | "sin_contexto"
  | "estudio"
  | "candidato"
  | "oportunidad"
  | "trigger"
  | "entrada"
  | "posicion"
  | "salida";

export const OPERATOR_JOURNEY_STAGE_LABEL: Record<
  OperatorJourneyStageV1,
  string
> = {
  sin_contexto: "Sin valor",
  estudio: "Estudio",
  candidato: "Candidato",
  oportunidad: "Oportunidad",
  trigger: "Trigger",
  entrada: "Entrada",
  posicion: "Posición",
  salida: "Salida",
};

export type OperatorFourAnswersV1 = {
  /** ① ¿Por qué está aquí? */
  thesis: string | null;
  /** ② ¿Qué tiene que pasar para entrar? */
  trigger: string | null;
  /** ③ ¿Cuánto puedo perder? */
  risk: string | null;
  /** ④ ¿Qué haré después? */
  plan: string | null;
};

export type OperatorRiskBoxV1 = {
  capital: number | null;
  riskPct: number | null;
  maxLoss: number | null;
  entry: number | null;
  stop: number | null;
  lossAtStop: number | null;
  rrT1: number | null;
  rrT2: number | null;
  /** V2.12 — position sizing chain */
  quantity: number | null;
  positionValue: number | null;
  portfolioPct: number | null;
  /** Distance entry→stop as % of entry */
  stopDistancePct: number | null;
};

export type OperatorMissionStepStatusV1 =
  | "done"
  | "active"
  | "pending"
  | "absent";

export type OperatorMissionStepV1 = {
  id: "entry" | "stop" | "t1" | "t2" | "trail" | "exit";
  label: string;
  status: OperatorMissionStepStatusV1;
  detail: string | null;
};

export type OperatorAutoChecklistV1 = {
  modeLabel: string;
  autonomyLabel: "Manual" | "Asistido" | "Automático";
  items: ReadonlyArray<{ id: string; label: string; done: boolean }>;
  interveneHint: string;
  honestyLine: string;
  profilePreview: string | null;
};

function finite(n: unknown): n is number {
  return typeof n === "number" && Number.isFinite(n);
}

function formatLevel(n: number | null | undefined): string {
  if (!finite(n)) return "—";
  return n.toFixed(2);
}

function formatMoney(n: number | null | undefined): string {
  if (!finite(n)) return "—";
  return `${Math.round(n)} €`;
}

function rrFromLevels(
  entry: number | null | undefined,
  stop: number | null | undefined,
  target: number | null | undefined,
): number | null {
  if (!finite(entry) || !finite(stop) || !finite(target)) return null;
  const risk = Math.abs(entry - stop);
  if (risk <= 0) return null;
  return Math.round((Math.abs(target - entry) / risk) * 100) / 100;
}

/** Map cockpit SEMI phase → operator journey stage (presentation only). */
export function operatorStageFromCockpitPhase(
  phase: MercadoCockpitPhase,
): OperatorJourneyStageV1 {
  switch (phase) {
    case "sin_contexto":
      return "sin_contexto";
    case "descubierto":
      return "candidato";
    case "vigilar":
      return "estudio";
    case "preparada":
    case "bloqueada":
    case "caducada":
      return "oportunidad";
    case "disparada":
      return "trigger";
    case "propuesta":
    case "confirmada":
      return "entrada";
    case "posicion":
      return "posicion";
    default:
      return "estudio";
  }
}

/** NEXT ACTION when there is no EntryOperatingTruth / POV yet (vigilar, descubierto…). */
export function buildOperatorNextActionFromCockpitPhase(
  phase: MercadoCockpitPhase,
): OperatorNextActionV1 {
  switch (phase) {
    case "sin_contexto":
      return {
        tone: "none",
        title: "SIN VALOR",
        subtitle: "Selecciona un valor en Listas o en el gráfico",
        ctaHint: null,
      };
    case "descubierto":
      return {
        tone: "watch",
        title: "CANDIDATO",
        subtitle: "Fuera de Estudio — añádelo para supervisarlo",
        ctaHint: "Añadir a Estudio",
      };
    case "vigilar":
      return {
        tone: "wait_trigger",
        title: "VIGILAR",
        subtitle: "En Estudio · aún sin plan armado — Ranking ≠ BUY",
        ctaHint: "Ver análisis",
      };
    case "bloqueada":
      return {
        tone: "review",
        title: "REVISAR",
        subtitle: "Plan bloqueado por gate o mandato",
        ctaHint: "Ver motivo del bloqueo",
      };
    case "caducada":
      return {
        tone: "watch",
        title: "CADUCADA",
        subtitle: "Plan caducado — niveles residuales no autorizan entrada",
        ctaHint: "Ver análisis",
      };
    default:
      return {
        tone: "watch",
        title:
          OPERATOR_JOURNEY_STAGE_LABEL[operatorStageFromCockpitPhase(phase)],
        subtitle: null,
        ctaHint: null,
      };
  }
}

export function buildOperatorNextActionFromEntry(
  truth: EntryOperatingTruthV1,
  opts: { paperAuto?: PaperAutoPostureV1 | null } = {},
): OperatorNextActionV1 {
  const phase = truth.phase;
  const auto = opts.paperAuto ?? null;
  const autoActive =
    auto?.autoActive === true && auto.requiresHumanConfirm === false;

  if (truth.entriesBlocked || truth.primaryCta.kind === "none") {
    const gate = truth.gateStatus?.toUpperCase();
    if (gate === "VETO" || gate === "DEFERRED") {
      return {
        tone: "review",
        title: "REVISAR",
        subtitle: "Gate de riesgo o mandato — entrada no autorizada",
        ctaHint: truth.primaryCta.label,
      };
    }
    if (autoActive && (phase === "disparada" || phase === "propuesta")) {
      return {
        tone: "entry_ready",
        title: "ENTRADA LISTA",
        subtitle: auto.executeEligible
          ? "Trigger confirmado · AUTO puede ejecutar (paper)"
          : "Trigger confirmado · AUTO armado · ejecución aún off",
        ctaHint: auto.executeEligible
          ? "AUTO ejecutará si está armado"
          : "Armado ≠ ejecución — activa execute en entorno demo",
      };
    }
    return {
      tone: "none",
      title: "SIN ACCIÓN",
      subtitle: truth.phrase,
      ctaHint: truth.primaryCta.label,
    };
  }

  switch (phase as EntryOperatingPhaseV1) {
    case "preparada":
      return {
        tone: "wait_trigger",
        title: "ESPERAR TRIGGER",
        subtitle: `Entrada prevista: ${formatLevel(truth.plan.entry)} · Stop: ${formatLevel(truth.plan.stopVigente)}`,
        ctaHint: autoActive
          ? "AUTO vigilará el disparador"
          : "Preparar operación → cola Confirm",
      };
    case "disparada":
      return {
        tone: "entry_ready",
        title: "ENTRADA LISTA",
        subtitle: `Trigger confirmado · Entrada ${formatLevel(truth.plan.entry)}`,
        ctaHint: autoActive
          ? auto?.executeEligible
            ? "AUTO ejecutará si está armado"
            : "AUTO armado · ejecución off"
          : "Revisar y confirmar (Confirm = firma)",
      };
    case "propuesta":
      return {
        tone: "entry_ready",
        title: "ENTRADA LISTA",
        subtitle: "Propuesta en cola · Confirm es la única firma",
        ctaHint: "Revisar y confirmar",
      };
    case "confirmada":
      return {
        tone: "watch",
        title: "EN EJECUCIÓN",
        subtitle: "Firma hecha · fill pendiente",
        ctaHint: "Ver operaciones",
      };
    default:
      return {
        tone: "watch",
        title: "VIGILAR",
        subtitle: truth.phrase,
        ctaHint: null,
      };
  }
}

export function buildOperatorNextActionFromPosition(
  primaryAction: PaperDeskNextActionV1,
  journey?: PositionJourneyReadoutV1 | null,
): OperatorNextActionV1 {
  const stop = journey?.trail.currentStop ?? journey?.risk.initialStop ?? null;
  const unprotected =
    journey != null &&
    !finite(journey.trail.currentStop) &&
    !finite(journey.risk.initialStop);
  const t1Done = journey?.t1.executed === true;
  const t2Done = journey?.t2.executed === true;
  const nextTarget =
    !t1Done && journey?.t1.trigger != null
      ? `T1 ${formatLevel(journey.t1.trigger)}`
      : !t2Done && journey?.t2.trigger != null
        ? `T2 ${formatLevel(journey.t2.trigger)}`
        : journey?.trail.active
          ? "Trailing activo"
          : null;

  switch (primaryAction) {
    case "SALIR":
      return {
        tone: "exit",
        title: "SALIR",
        subtitle: "Stop o invalidación — revisar salida",
        ctaHint: "Salir (Confirm = firma)",
      };
    case "SUBIR_STOP":
      return {
        tone: "protect",
        title: "PROTEGER",
        subtitle: finite(stop)
          ? `Elevar stop hacia ${formatLevel(stop)}`
          : "Trailing o stop a elevar",
        ctaHint: "Proteger (propuesta → Confirm)",
      };
    case "REDUCIR":
      return {
        tone: "protect",
        title: "REDUCIR",
        subtitle: nextTarget ?? "Reducir según plan",
        ctaHint: "Reducir (Confirm = firma)",
      };
    case "REVISAR_DATOS_NO_FRESCOS":
    case "BLOQUEADO":
      return {
        tone: "review",
        title: "REVISAR",
        subtitle: "Datos o reconciliación — no operar a ciegas",
        ctaHint: "Revisar",
      };
    case "ESPERAR_APERTURA":
      return {
        tone: "watch",
        title: "ESPERAR",
        subtitle: "Sesión cerrada o pendiente de apertura",
        ctaHint: null,
      };
    case "MONITOR":
    case "MANTENER":
    default:
      // V2.10 — OPEN_UNPROTECTED without stop: hero = PROTEGER (emergency), not MANTENER
      if (unprotected) {
        return {
          tone: "protect",
          title: "PROTEGER",
          subtitle:
            "Sin stop técnico · emergencia −5 % sugerida (no es stop de estrategia)",
          ctaHint: "Proteger (Confirm = firma)",
        };
      }
      return {
        tone: "maintain",
        title: "MANTENER",
        subtitle:
          [
            finite(stop) ? `Stop ${formatLevel(stop)}` : null,
            t1Done ? "T1 alcanzado" : null,
            nextTarget ? `Próximo: ${nextTarget}` : null,
          ]
            .filter(Boolean)
            .join(" · ") || "Posición protegida",
        ctaHint: "Mantener",
      };
  }
}

export function buildOperatorFourAnswers(input: {
  phase: MercadoCockpitPhase;
  thesisSummary?: string | null;
  entry?: number | null;
  stop?: number | null;
  triggerLabel?: string | null;
  riskAmount?: number | null;
  riskR?: number | null;
  target1?: number | null;
  target2?: number | null;
  trailActive?: boolean;
}): OperatorFourAnswersV1 {
  const thesis =
    input.thesisSummary?.trim() ||
    (input.phase === "descubierto"
      ? "Fuera de Estudio"
      : input.phase === "vigilar"
        ? "En supervisión Estudio"
        : input.phase === "posicion"
          ? "Posición abierta"
          : "Plan operativo");

  let trigger: string | null = null;
  if (input.phase === "preparada") {
    trigger = `Esperar ruptura / disparo hacia ${formatLevel(input.entry)}`;
  } else if (input.phase === "disparada" || input.phase === "propuesta") {
    trigger = `Trigger confirmado (${input.triggerLabel ?? "Disparado"})`;
  } else if (input.phase === "confirmada") {
    trigger = "Entrada firmada · fill en curso";
  } else if (input.phase === "posicion") {
    trigger = "Ya dentro — gestionar plan";
  } else if (input.phase === "vigilar") {
    trigger = "Aún sin plan armado";
  }

  const riskParts: string[] = [];
  if (finite(input.stop)) riskParts.push(`Stop ${formatLevel(input.stop)}`);
  if (finite(input.riskR)) riskParts.push(`${input.riskR.toFixed(2)}R`);
  if (finite(input.riskAmount)) riskParts.push(formatMoney(input.riskAmount));
  const risk = riskParts.length > 0 ? riskParts.join(" · ") : null;

  const planParts: string[] = [];
  if (finite(input.target1)) planParts.push(`T1 ${formatLevel(input.target1)}`);
  if (finite(input.target2)) planParts.push(`T2 ${formatLevel(input.target2)}`);
  if (input.trailActive) planParts.push("Trailing");
  if (planParts.length === 0 && input.phase === "posicion") {
    planParts.push("Stop → T1 → T2 → Trailing → Salida");
  }
  const plan = planParts.length > 0 ? planParts.join(" → ") : null;

  return { thesis, trigger, risk, plan };
}

export function buildOperatorRiskBox(input: {
  capital?: number | null;
  riskPct?: number | null;
  maxLoss?: number | null;
  entry?: number | null;
  stop?: number | null;
  lossAtStop?: number | null;
  target1?: number | null;
  target2?: number | null;
  quantity?: number | null;
  positionValue?: number | null;
  portfolioPct?: number | null;
}): OperatorRiskBoxV1 {
  const lossAtStop = finite(input.lossAtStop)
    ? input.lossAtStop
    : finite(input.maxLoss)
      ? input.maxLoss
      : null;
  const entry = finite(input.entry) ? input.entry : null;
  const stop = finite(input.stop) ? input.stop : null;
  let stopDistancePct: number | null = null;
  if (entry != null && stop != null && entry > 0) {
    stopDistancePct = Math.round((Math.abs(entry - stop) / entry) * 1000) / 10;
  }
  const quantity = finite(input.quantity) ? input.quantity : null;
  let positionValue = finite(input.positionValue) ? input.positionValue : null;
  if (positionValue == null && quantity != null && entry != null) {
    positionValue = Math.round(quantity * entry * 100) / 100;
  }
  return {
    capital: finite(input.capital) ? input.capital : null,
    riskPct: finite(input.riskPct) ? input.riskPct : null,
    maxLoss: finite(input.maxLoss) ? input.maxLoss : lossAtStop,
    entry,
    stop,
    lossAtStop,
    rrT1: rrFromLevels(input.entry, input.stop, input.target1),
    rrT2: rrFromLevels(input.entry, input.stop, input.target2),
    quantity,
    positionValue,
    portfolioPct: finite(input.portfolioPct) ? input.portfolioPct : null,
    stopDistancePct,
  };
}

export function buildOperatorMissionSteps(
  journey: PositionJourneyReadoutV1,
): OperatorMissionStepV1[] {
  const entryDone = finite(journey.entry);
  const stopDone =
    finite(journey.risk.initialStop) || finite(journey.trail.currentStop);
  const t1 = journey.t1;
  const t2 = journey.t2;
  const trail = journey.trail;

  function legStatus(
    leg: PositionJourneyReadoutV1["t1"],
  ): OperatorMissionStepStatusV1 {
    if (leg.status === "absent") return "absent";
    if (leg.executed || leg.status === "executed") return "done";
    if (leg.status === "triggered") return "active";
    return "pending";
  }

  return [
    {
      id: "entry",
      label: "Entrada",
      status: entryDone ? "done" : "pending",
      detail: formatLevel(journey.entry),
    },
    {
      id: "stop",
      label: "Stop",
      status: stopDone ? "done" : "pending",
      detail: formatLevel(
        journey.trail.currentStop ?? journey.risk.initialStop,
      ),
    },
    {
      id: "t1",
      label: "T1",
      status: legStatus(t1),
      detail:
        t1.trigger != null
          ? `${formatLevel(t1.trigger)}${
              t1.qtyFractionPct != null ? ` · ${t1.qtyFractionPct}%` : ""
            }`
          : null,
    },
    {
      id: "t2",
      label: "T2",
      status: legStatus(t2),
      detail:
        t2.trigger != null
          ? `${formatLevel(t2.trigger)}${
              t2.qtyFractionPct != null ? ` · ${t2.qtyFractionPct}%` : ""
            }`
          : null,
    },
    {
      id: "trail",
      label: "Trailing",
      status: !trail.activationEligible
        ? "pending"
        : trail.active
          ? "active"
          : "pending",
      detail: !trail.activationEligible
        ? "Tras T1"
        : trail.active
          ? `Activo · stop ${formatLevel(trail.currentStop)}`
          : "Listo",
    },
  ];
}

function trailWidthLabel(w: ExitTrailWidthV1): string {
  switch (w) {
    case "tight":
      return "temprano";
    case "wide":
      return "amplio";
    default:
      return "progresivo";
  }
}

function profileLabel(templateId: string | null | undefined): string {
  if (templateId === "conservative") return "Conservador";
  if (templateId === "aggressive_swing") return "Swing agresivo";
  return "Moderado";
}

export function formatExitPolicyOperatorPreview(
  policy: ExitPolicyV1,
  templateId?: string | null,
): string {
  const t1 = Math.round(policy.t1ReduceFraction * 100);
  const t2 = Math.round(policy.t2ReduceFraction * 100);
  return `${profileLabel(templateId)} · T1 ${t1}% · T2 ${t2}% · Trailing ${trailWidthLabel(policy.trailWidth)}`;
}

export function buildOperatorAutoChecklist(input: {
  posture: PaperAutoPostureV1;
  templateId?: string | null;
  killOn?: boolean | null;
}): OperatorAutoChecklistV1 {
  const { posture } = input;
  const autonomyLabel: OperatorAutoChecklistV1["autonomyLabel"] =
    posture.bookMode === "manual"
      ? "Manual"
      : posture.bookMode === "auto" && posture.autoActive
        ? "Automático"
        : "Asistido";

  const autoOn = posture.autoActive;
  const items = [
    {
      id: "entry",
      label: "Entrada condicionada",
      done: autoOn || posture.bookMode === "semi",
    },
    {
      id: "stop",
      label: "Stop inicial",
      done: autoOn || posture.bookMode === "semi",
    },
    { id: "t1", label: "T1 automático", done: autoOn },
    { id: "t2", label: "T2 automático", done: autoOn },
    { id: "trail", label: "Trailing automático", done: autoOn },
  ];

  const honestyParts: string[] = [];
  if (posture.bookMode === "auto") {
    honestyParts.push(posture.autoArmed ? "AUTO armado" : "AUTO sin armar");
    honestyParts.push(
      posture.executeEligible
        ? "ejecución demo activa"
        : "ejecución demo off (armado ≠ ejecución)",
    );
  } else if (posture.bookMode === "semi") {
    honestyParts.push("Asistido · Confirm = firma");
  } else {
    honestyParts.push("Manual · tú operas");
  }
  if (input.killOn === true) honestyParts.push("kill activo");

  const policy = resolveExitPolicy(input.templateId);
  return {
    modeLabel: posture.modeLabel,
    autonomyLabel,
    items,
    interveneHint: "Puedes intervenir en cualquier momento.",
    honestyLine: honestyParts.join(" · "),
    profilePreview: formatExitPolicyOperatorPreview(policy, input.templateId),
  };
}

/** Operator-facing AUTO line (no PAPER_D_EXECUTE / env jargon). */
export function formatOperatorAutoHonesty(
  posture: PaperAutoPostureV1 | null | undefined,
  killOn?: boolean | null,
): string | null {
  if (!posture) return null;
  const checklist = buildOperatorAutoChecklist({ posture, killOn });
  return checklist.honestyLine;
}

/** V2.12 — remaining / realized from journey (no React invention of %). */
export type PositionReductionReadoutV1 = {
  birthQuantity: number;
  remainingQuantity: number;
  realizedPct: number | null;
  remainingPct: number | null;
  t1QtyFractionPct: number | null;
  t2QtyFractionPct: number | null;
};

export function buildPositionReductionReadout(input: {
  birthQuantity: number;
  remainingQuantity: number;
  t1QtyFractionPct?: number | null;
  t2QtyFractionPct?: number | null;
}): PositionReductionReadoutV1 {
  const birth = Math.max(0, input.birthQuantity);
  const remaining = Math.max(0, input.remainingQuantity);
  let realizedPct: number | null = null;
  let remainingPct: number | null = null;
  if (birth > 0) {
    realizedPct = Math.round(((birth - remaining) / birth) * 1000) / 10;
    remainingPct = Math.round((remaining / birth) * 1000) / 10;
  }
  return {
    birthQuantity: birth,
    remainingQuantity: remaining,
    realizedPct,
    remainingPct,
    t1QtyFractionPct: finite(input.t1QtyFractionPct)
      ? input.t1QtyFractionPct
      : null,
    t2QtyFractionPct: finite(input.t2QtyFractionPct)
      ? input.t2QtyFractionPct
      : null,
  };
}

/** V2.13 — what AUTO will do for this instrument (ExitPolicy + journey). */
export type OperatorAutoPlanPreviewV1 = {
  profileLabel: string;
  nextActionTitle: string;
  items: ReadonlyArray<{ id: string; label: string; done: boolean }>;
  ifReachesLines: string[];
  trailingLine: string | null;
  honestyLine: string;
};

export function buildOperatorAutoPlanPreview(input: {
  journey?: PositionJourneyReadoutV1 | null;
  templateId?: string | null;
  nextAction: OperatorNextActionV1;
  posture?: PaperAutoPostureV1 | null;
  killOn?: boolean | null;
}): OperatorAutoPlanPreviewV1 {
  const policy = resolveExitPolicy(input.templateId);
  const t1Pct = Math.round(policy.t1ReduceFraction * 100);
  const t2Pct = Math.round(policy.t2ReduceFraction * 100);
  const journey = input.journey;
  const stopDone =
    journey != null &&
    (finite(journey.risk.initialStop) || finite(journey.trail.currentStop));
  const items = [
    {
      id: "stop",
      label: "Stop inicial",
      done: stopDone,
    },
    {
      id: "t1",
      label: `T1 ${t1Pct}%`,
      done: journey?.t1.executed === true,
    },
    {
      id: "t2",
      label: `T2 ${t2Pct}%`,
      done: journey?.t2.executed === true,
    },
    {
      id: "trail",
      label: `Trailing ${trailWidthLabel(policy.trailWidth)}`,
      done: journey?.trail.active === true,
    },
    {
      id: "exit",
      label: "Salida final",
      done: false,
    },
  ];

  const ifReachesLines: string[] = [];
  if (journey?.t1.trigger != null && !journey.t1.executed) {
    ifReachesLines.push(
      `${formatLevel(journey.t1.trigger)} → vender ${t1Pct}%`,
    );
  }
  if (journey?.t2.trigger != null && !journey.t2.executed) {
    ifReachesLines.push(
      `${formatLevel(journey.t2.trigger)} → vender ${t2Pct}%`,
    );
  }

  const trailingLine =
    journey?.trail.active === true
      ? `Trailing activo · stop ${formatLevel(journey.trail.currentStop)}`
      : journey?.trail.activationEligible
        ? "Tras T1 actualizará stop automáticamente"
        : "Trailing tras T1";

  const honesty =
    formatOperatorAutoHonesty(input.posture, input.killOn) ??
    "Confirm = firma · armado ≠ ejecución";

  return {
    profileLabel: profileLabel(input.templateId),
    nextActionTitle: input.nextAction.title,
    items,
    ifReachesLines,
    trailingLine,
    honestyLine: honesty,
  };
}
