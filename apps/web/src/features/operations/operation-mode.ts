/**
 * UI Contract 5.0 (`UI5-10`/`UI5-13`) — modo de operación como insignia (nunca deducible).
 *
 * Cada operación declara su modo (`AUTO`/`SEMI`/`MANUAL`) **y** el canal de dinero
 * (`SIMULADO`/`LIVE`). El modo no se infiere del ticker ni de un atributo oculto: sólo se afirma
 * con evidencia. La única evidencia que el wire expone hoy es `HUMAN_MANUAL`
 * (`tradePlanId` con prefijo `manual-`); el resto se declara «Sin dato todavía» salvo dentro del
 * espacio AUTO, cuyo modo es AUTO por definición de la superficie.
 *
 * @see docs/engineering/spec-ui-contract-5-0-2026-10-08.md §UI5-10
 * @see docs/domain-language.md §4.2
 */

import type { PositionDto } from "@bolsa/shared";
import { positionIsHumanManual } from "@/features/operations/propose-position-exit";

export const OPERATION_MODE_NO_DATA_LABEL = "Sin dato todavía";

export type OperationMode = "AUTO" | "SEMI" | "MANUAL";
export type OperationChannel = "SIMULADO" | "LIVE";

/**
 * Casing canónico de primer nivel del modo (`UI5-10`): `AUTO`/`SEMI`/`MANUAL`.
 * Única fuente para superficies que sólo rotulan el modo (p. ej. el libro DEMO),
 * de modo que nunca convivan `AUTO` con `Auto`/`Manual`/`Semi`.
 */
export const OPERATION_MODE_LABEL: Record<OperationMode, string> = {
  AUTO: "AUTO",
  SEMI: "SEMI",
  MANUAL: "MANUAL",
};

export type OperationModeBadgeV1 = {
  mode: OperationMode | null;
  channel: OperationChannel;
};

/** Superficie que hospeda la lista (espacio AUTO vs resto de la app). */
export type OperationSurface = "market" | "auto";

/** Operación producida por AUTO: modo AUTO, canal simulado. */
export const AUTO_OPERATION_MODE: OperationModeBadgeV1 = {
  mode: "AUTO",
  channel: "SIMULADO",
};

/** Operación de libro DEMO en SEMI: la app propone y una persona firma. */
export const SEMI_OPERATION_MODE: OperationModeBadgeV1 = {
  mode: "SEMI",
  channel: "SIMULADO",
};

/** Etiqueta visible de la insignia: `AUTO · SIMULADO` o `Sin dato todavía`. */
export function operationModeLabel(badge: OperationModeBadgeV1): string {
  return badge.mode
    ? `${badge.mode} · ${badge.channel}`
    : OPERATION_MODE_NO_DATA_LABEL;
}

/**
 * Modo de una posición con la evidencia disponible. `HUMAN_MANUAL` es la única evidencia que el
 * `PositionDto` expone (la posición nació por el canal HTTP manual). Dentro de AUTO, el modo es
 * AUTO; en el resto de la app, sin evidencia, se declara «Sin dato todavía».
 */
export function operationModeForPosition(
  position: PositionDto,
  surface: OperationSurface,
): OperationModeBadgeV1 {
  if (positionIsHumanManual(position)) {
    return { mode: "MANUAL", channel: "SIMULADO" };
  }
  if (surface === "auto") return AUTO_OPERATION_MODE;
  return { mode: null, channel: "SIMULADO" };
}
