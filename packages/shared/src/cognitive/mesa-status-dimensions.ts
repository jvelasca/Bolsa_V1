/**
 * Presentación de estado en 3 dimensiones (ADR-037).
 * No persiste ni amplía JournalStudyUserStatus.
 */

import type { DecisionJournalStudyViewV1 } from "./decision-journal-study.js";
import { JOURNAL_STUDY_STATUS_LABELS } from "./decision-journal-study.js";
import type { PositionStatusV1 } from "./position-state.js";
import type { TradePlanStatusV1 } from "./trade-plan.js";
import { MESA_ENTRY_STATUS_LABEL } from "./mesa-entry-queue.js";

export type MesaStatusDimensionsV1 = {
  thesis: string;
  operational: string;
  position: string;
};

const POSITION_STATUS_LABEL: Record<PositionStatusV1, string> = {
  OPEN: "Abierta",
  PARTIAL: "Parcial",
  PROTECTED: "Protegida",
  CLOSED: "Cerrada",
};

const OPERATIONAL_STATUS_LABEL: Record<TradePlanStatusV1, string> = {
  WATCH: "Vigilar",
  ARMED: "Preparada",
  TRIGGERED: "Propuesta",
  BLOCKED: "Bloqueada",
  EXPIRED: "Caducada",
};

export type MapMesaStatusDimensionsInput = {
  study?: Pick<
    DecisionJournalStudyViewV1,
    "status" | "tradePlanStatus" | "hasOperationalPlan"
  > | null;
  positionStatus?: PositionStatusV1 | null;
  hasOpenPosition?: boolean | null;
  tradePlanStatus?: TradePlanStatusV1 | null;
};

export function mapMesaStatusDimensions(
  input: MapMesaStatusDimensionsInput,
): MesaStatusDimensionsV1 {
  const thesis = input.study?.status
    ? JOURNAL_STUDY_STATUS_LABELS[input.study.status]
    : "Sin tesis";

  const planStatus =
    input.tradePlanStatus ?? input.study?.tradePlanStatus ?? null;
  let operational = "Sin plan";
  if (planStatus) {
    operational = OPERATIONAL_STATUS_LABEL[planStatus] ?? planStatus;
  } else if (input.study && !input.study.hasOperationalPlan) {
    operational = "Sin plan operativo";
  }

  let position = "Sin posición";
  if (input.hasOpenPosition === false) {
    position = "Sin posición";
  } else if (input.positionStatus) {
    position =
      POSITION_STATUS_LABEL[input.positionStatus] ?? input.positionStatus;
  } else if (input.hasOpenPosition) {
    position = "Abierta";
  }

  return { thesis, operational, position };
}

/** Labels UI para grupos de candidatos en Mesa · Hoy. */
export const MESA_CANDIDATE_GROUP_LABEL: Record<TradePlanStatusV1, string> = {
  TRIGGERED: "Listos",
  ARMED: "Preparados",
  WATCH: "Vigilar",
  BLOCKED: "Bloqueados",
  EXPIRED: "Descartados",
};

export { MESA_ENTRY_STATUS_LABEL };
