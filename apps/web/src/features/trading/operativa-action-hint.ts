/**
 * S4 · Vía de actuación de la ventana maximizada de DECISIÓN.
 *
 * Qué hace: describe, en lenguaje de producto, qué vía existe para este valor
 * (entrada, salida o ninguna) y, si la entrada está cerrada, **por qué**.
 *
 * Qué NO hace: no autoriza nada. El CTA real lo sigue gobernando el cockpit con
 * `canPropose`; esta pista solo lo explica por adelantado y con el mismo orden de
 * comprobaciones, para que la ventana maximizada no insinúe una operación que el
 * cockpit va a bloquear.
 *
 * Regla dura: «sin actuación» nunca significa «sin posición». La ausencia de
 * posición la declara la cartera medida; aquí solo se dice qué vía existe.
 *
 * @see docs/engineering/diseno-decision-maximizada-s4-2026-11-12.md
 */

import type { AsesorCarteraStateIdV1 } from "@bolsa/shared";

export const OPERATIVA_ACTION_HINT_IDS = [
  "entrada_disponible",
  "entrada_bloqueada",
  "salida_en_accion",
  "sin_actuacion",
] as const;

export type OperativaActionHintIdV1 =
  (typeof OPERATIVA_ACTION_HINT_IDS)[number];

/**
 * Motivos de bloqueo de entrada, en el mismo orden que evalúa `canPropose`.
 * El primero que falla es el que se declara: no se acumulan motivos.
 */
export const OPERATIVA_BLOCK_REASON_IDS = [
  "sin_cuenta",
  "cartera_sin_medir",
  "estudios_sin_medir",
  "modo_sin_propuesta",
  "entradas_bloqueadas",
  "fuera_de_estudio",
] as const;

export type OperativaBlockReasonIdV1 =
  (typeof OPERATIVA_BLOCK_REASON_IDS)[number];

export type OperativaBlockReasonDefinitionV1 = {
  id: OperativaBlockReasonIdV1;
  label: string;
  detail: string;
};

export const OPERATIVA_BLOCK_REASONS: ReadonlyArray<OperativaBlockReasonDefinitionV1> =
  [
    {
      id: "sin_cuenta",
      label: "Sin cuenta activa",
      detail:
        "No hay cuenta activa: sin cuenta no se puede proponer una entrada.",
    },
    {
      id: "cartera_sin_medir",
      label: "Cartera sin medir",
      detail:
        "La cartera no se ha leído: no se puede afirmar que no haya posición.",
    },
    {
      id: "estudios_sin_medir",
      label: "Estudios sin medir",
      detail:
        "El parte diario no se ha leído: no hay plan operativo que proponer.",
    },
    {
      id: "modo_sin_propuesta",
      label: "El modo actual no propone entradas",
      detail:
        "El modo de la cuenta no encola propuestas: la entrada no se puede preparar desde aquí.",
    },
    {
      id: "entradas_bloqueadas",
      label: "Entradas bloqueadas",
      detail:
        "El riesgo o una incidencia activa bloquean las entradas. Solo se admiten cierres.",
    },
    {
      id: "fuera_de_estudio",
      label: "Fuera de Estudio",
      detail:
        "El modo exige pertenencia a Estudio y este valor no está dentro.",
    },
  ];

export function operativaBlockReasonDefinition(
  id: OperativaBlockReasonIdV1,
): OperativaBlockReasonDefinitionV1 {
  const found = OPERATIVA_BLOCK_REASONS.find((reason) => reason.id === id);
  if (!found) throw new Error(`Motivo de bloqueo desconocido: ${id}`);
  return found;
}

export type ResolveOperativaActionHintInput = {
  /** Categoría de presentación del clasificador S3. */
  carteraStateId: AsesorCarteraStateIdV1;
  /** Posición abierta **medida**. */
  hasOpenPosition: boolean;
  hasAccount: boolean;
  positionMeasured: boolean;
  studiesMeasured: boolean;
  /** El modo permite encolar Confirm (PAPER/SEMI/AUTO según prefs). */
  canEnqueueConfirm: boolean;
  entriesBlocked: boolean;
  requiresEstudio: boolean;
  inEstudio: boolean;
};

export type OperativaActionHintV1 = {
  id: OperativaActionHintIdV1;
  label: string;
  detail: string;
  /** Motivo declarado solo en `entrada_bloqueada`. */
  blockedReason: OperativaBlockReasonIdV1 | null;
  /**
   * Hay una vía que el cockpit puede ejecutar. Una pista con `false` no
   * deshabilita el CTA: el CTA sigue mandando.
   */
  canAct: boolean;
};

/** Primer motivo de bloqueo, con la precedencia de `canPropose`. */
export function resolveOperativaBlockReason(
  input: ResolveOperativaActionHintInput,
): OperativaBlockReasonIdV1 | null {
  if (!input.hasAccount) return "sin_cuenta";
  if (!input.positionMeasured) return "cartera_sin_medir";
  if (!input.studiesMeasured) return "estudios_sin_medir";
  if (!input.canEnqueueConfirm) return "modo_sin_propuesta";
  if (input.entriesBlocked) return "entradas_bloqueadas";
  if (input.requiresEstudio && !input.inEstudio) return "fuera_de_estudio";
  return null;
}

export function resolveOperativaActionHint(
  input: ResolveOperativaActionHintInput,
): OperativaActionHintV1 {
  if (input.carteraStateId === "sin_datos") {
    return {
      id: "sin_actuacion",
      label: "Sin actuación",
      detail:
        "Falta una medición imprescindible: no se describe ninguna vía de actuación.",
      blockedReason: null,
      canAct: false,
    };
  }

  if (input.hasOpenPosition) {
    return {
      id: "salida_en_accion",
      label: "Salida en ACCIÓN",
      detail:
        "Hay una posición abierta: la gestión de salida vive en ACCIÓN, con su propio CTA. Esto no es una orden.",
      blockedReason: null,
      canAct: true,
    };
  }

  if (input.carteraStateId !== "recomendacion_favorable") {
    return {
      id: "sin_actuacion",
      label: "Sin actuación",
      detail:
        "El dictamen no emitió compra: no hay entrada que proponer. El contexto técnico informa, no habilita.",
      blockedReason: null,
      canAct: false,
    };
  }

  const blockedReason = resolveOperativaBlockReason(input);
  if (blockedReason) {
    const reason = operativaBlockReasonDefinition(blockedReason);
    return {
      id: "entrada_bloqueada",
      label: "Entrada bloqueada",
      detail: reason.detail,
      blockedReason,
      canAct: false,
    };
  }

  return {
    id: "entrada_disponible",
    label: "Entrada disponible",
    detail:
      "El dictamen emitió compra y la vía está abierta. Proponer no firma: la firma se hace en Confirm.",
    blockedReason: null,
    canAct: true,
  };
}
