/**
 * Entry Operating UX — copy y CTA canónicos (V1.38).
 * PREPARADA / DISPARADA / PROPUESTA / CONFIRMADA. Ranking ≠ BUY.
 * SEMI: Confirm = firma. PAPER AUTO (F8): mismos objetos; omite firma humana.
 *
 * @see docs/engineering/diseno-mercado-2-0-cockpit-2026-08-27.md §3.1
 */

import type { MercadoCockpitPhase } from "./mercado-cockpit-phase.js";
import {
  type MesaNextActionKindV1,
  type MesaNextActionV1,
} from "./mesa-next-action.js";
import type { PaperAutoPostureV1 } from "./paper-auto-posture.js";
import {
  PAPER_AUTO_ARMED_EXEC_OFF,
  PAPER_AUTO_ARMED_EXEC_ON,
} from "./paper-auto-posture.js";

export const ENTRY_OPERATING_PHASES = [
  "preparada",
  "disparada",
  "propuesta",
  "confirmada",
] as const;

export type EntryOperatingPhaseV1 = (typeof ENTRY_OPERATING_PHASES)[number];

export type EntryOperatingCtaKindV1 =
  | "prepare"
  | "review_confirm"
  | "view_operations"
  | "none";

export type EntryOperatingCtaV1 = {
  kind: EntryOperatingCtaKindV1;
  label: string;
};

/** CTA / copy canónico cuando kill+incidentes+vetoed (fail-closed). */
export const ENTRIES_BLOCKED_CTA_LABEL = "Entradas bloqueadas";
export const ENTRIES_BLOCKED_PROPOSE_MSG =
  "Entradas bloqueadas por incidente o recon — no proponer hasta resolver.";

/** CTA cuando gate diario VETO/DEFERRED — frase y botón alineados (no «Preparar…»). */
export const GATE_VETO_CTA_LABEL = "Gate en veto";
export const GATE_DEFERRED_CTA_LABEL = "Gate diferido";

const ENTRY_PRIMARY_LABEL: Record<EntryOperatingPhaseV1, string> = {
  preparada: "Preparar operación",
  disparada: "Revisar y confirmar",
  propuesta: "Revisar y confirmar",
  confirmada: "Ver operaciones",
};

const ENTRY_CTA_KIND: Record<EntryOperatingPhaseV1, EntryOperatingCtaKindV1> = {
  preparada: "prepare",
  disparada: "review_confirm",
  propuesta: "review_confirm",
  confirmada: "view_operations",
};

export function isEntryOperatingPhase(
  phase: MercadoCockpitPhase,
): phase is EntryOperatingPhaseV1 {
  return (ENTRY_OPERATING_PHASES as readonly string[]).includes(phase);
}

export function entryOperatingPrimaryLabel(
  phase: MercadoCockpitPhase,
): string | null {
  if (!isEntryOperatingPhase(phase)) return null;
  return ENTRY_PRIMARY_LABEL[phase];
}

export function entryOperatingCtaFromPhase(
  phase: EntryOperatingPhaseV1,
  opts: {
    entriesBlocked?: boolean;
    gateStatus?: string | null;
    /** F8: when AUTO active, omit Confirm CTA on entry phases. */
    paperAuto?: PaperAutoPostureV1 | null;
  } = {},
): EntryOperatingCtaV1 {
  if (opts.entriesBlocked && phase !== "confirmada") {
    return { kind: "none", label: ENTRIES_BLOCKED_CTA_LABEL };
  }
  const gate = opts.gateStatus?.toUpperCase();
  if (gate === "VETO" && phase !== "confirmada") {
    return { kind: "none", label: GATE_VETO_CTA_LABEL };
  }
  if (gate === "DEFERRED" && phase !== "confirmada") {
    return { kind: "none", label: GATE_DEFERRED_CTA_LABEL };
  }
  const auto = opts.paperAuto;
  if (
    auto?.autoActive === true &&
    auto.requiresHumanConfirm === false &&
    (phase === "disparada" || phase === "propuesta")
  ) {
    return {
      kind: "none",
      label: auto.executeEligible
        ? PAPER_AUTO_ARMED_EXEC_ON
        : PAPER_AUTO_ARMED_EXEC_OFF,
    };
  }
  return {
    kind: ENTRY_CTA_KIND[phase],
    label: ENTRY_PRIMARY_LABEL[phase],
  };
}

export function formatEntryOperatingPhrase(
  phase: EntryOperatingPhaseV1,
  opts: {
    entriesBlocked?: boolean;
    gateStatus?: string | null;
    paperAuto?: PaperAutoPostureV1 | null;
  } = {},
): string {
  if (opts.entriesBlocked && phase !== "confirmada") {
    return ENTRIES_BLOCKED_PROPOSE_MSG;
  }
  const gate = opts.gateStatus?.toUpperCase();
  if (gate === "VETO" || gate === "DEFERRED") {
    return "Gate de riesgo o mandato en veto — el plan no autoriza entrada.";
  }
  const auto = opts.paperAuto;
  if (auto?.autoActive === true && auto.requiresHumanConfirm === false) {
    switch (phase) {
      case "preparada":
        return "Plan armado (AUTO). Disparador aún no cruzado — Ranking ≠ BUY · sin firma.";
      case "disparada":
        return auto.executeEligible
          ? "Disparo OK · PAPER AUTO omite Confirm — misma disciplina Risk/Policy (paper)."
          : "Disparo OK · AUTO armado · ejecución off (PAPER_D_EXECUTE) — arm ≠ execute.";
      case "propuesta":
        return auto.executeEligible
          ? "PAPER AUTO: sin cola Confirm — IA → Risk → Policy → Execution."
          : "AUTO armado · ejecución off — no hay firma SEMI ni fill hasta PAPER_D_EXECUTE=1.";
      case "confirmada":
        return "Fill / orden en vuelo — mira Operaciones (AUTO o SEMI previo).";
      default:
        return "Sin acción de entrada.";
    }
  }
  switch (phase) {
    case "preparada":
      return "Plan armado. Disparador de entrada aún no cruzado — Ranking ≠ BUY.";
    case "disparada":
      return "Disparo confirmado. Revisa niveles y firma en Confirm — no ejecuta solo.";
    case "propuesta":
      return "Propuesta SEMI en cola. Confirm es la única firma.";
    case "confirmada":
      return "Firma hecha — fill pendiente. Mira Operaciones para el estado de la orden.";
    default:
      return "Sin acción de entrada.";
  }
}

export function formatEntryTriggerLabel(phase: EntryOperatingPhaseV1): string {
  switch (phase) {
    case "preparada":
      return "Pendiente";
    case "disparada":
    case "propuesta":
    case "confirmada":
      return "Disparado";
    default:
      return "—";
  }
}

export function mesaNextActionFromEntryTruth(input: {
  phase: EntryOperatingPhaseV1;
  primaryCta: EntryOperatingCtaV1;
}): MesaNextActionV1 {
  if (input.primaryCta.kind === "none") {
    return {
      kind: "none",
      label: input.primaryCta.label,
      allowsEntry: false,
    };
  }

  let kind: MesaNextActionKindV1;
  switch (input.primaryCta.kind) {
    case "prepare":
      kind = "view_thesis";
      break;
    case "review_confirm":
      kind = "review_proposal";
      break;
    case "view_operations":
      kind = "watch";
      break;
    default:
      kind = "watch";
  }

  return {
    kind,
    label: input.primaryCta.label,
    allowsEntry: false,
  };
}
