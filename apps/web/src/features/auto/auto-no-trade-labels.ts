/**
 * P4 — «Por qué AUTO no operó»: vocabulario único de primer nivel (dato ausente aparte).
 *
 * El audit `P4` pide distinguir seis causas de un día sin operaciones y enlazar cada una con
 * el registro que la demuestra. Este módulo es la **única casa** de la copy en castellano de
 * esa explicación (títulos, causas, estados y motivos de entrada) para que ninguna superficie
 * invente etiquetas ni filtre enums crudos (`ENTRY_RISK_LIMIT`, `paper_auto_env_blocked`, …),
 * que el gate de primer nivel prohíbe.
 *
 * Invariantes:
 * - **`UNKNOWN ≠ 0`.** Un estado sin dato se rotula con el vocabulario de `absent-data`
 *   («Sin dato todavía»); jamás se colapsa a «No aplica» ni a un cero afirmado.
 * - **Tres estados, no dos.** `ocurrió` (la causa se declara con evidencia), `no aplica`
 *   (medido y descartado) y el hueco. No se confunden.
 * - **Sin jerga de motor.** Los nombres técnicos de estado (`reached`/`pending`/`absent`/
 *   `unknown`) y de paso no viven aquí: se traducen en `auto-no-trade-explanation.ts`.
 *
 * @see docs/engineering/auditoria-operativa-diaria-entrada-salida-dia-d-2026-10-08.md (P4)
 */

import type { PaperDeskEntryReasonCodeV1 } from "@bolsa/shared";
import { absentDataLabel } from "@/components/absent-data";

/** Las seis causas del audit, en orden de cadena (descubrimiento → motor). */
export type AutoNoTradeCauseId =
  | "no_opportunity"
  | "no_selection"
  | "risk_regime_veto"
  | "decision_without_order"
  | "order_without_fill"
  | "execution_unconfirmed";

/** Capa: embudo de descubrimiento/Estudio, o cadena del motor determinista. */
export type AutoNoTradeLayerId = "discovery" | "engine";

export const AUTO_NO_TRADE_DISCOVERY_CAUSES: readonly AutoNoTradeCauseId[] = [
  "no_opportunity",
  "no_selection",
  "risk_regime_veto",
] as const;

export const AUTO_NO_TRADE_ENGINE_CAUSES: readonly AutoNoTradeCauseId[] = [
  "decision_without_order",
  "order_without_fill",
  "execution_unconfirmed",
] as const;

/** Copy de las causas — literal del audit, sin reinterpretar el hecho. */
export const AUTO_NO_TRADE_CAUSE_LABELS: Record<AutoNoTradeCauseId, string> = {
  no_opportunity: "No apareció una oportunidad",
  no_selection: "Había candidatos, pero ninguno superó la selección",
  risk_regime_veto: "Hubo un veto de riesgo o de régimen",
  decision_without_order: "Se aprobó una decisión, pero no se creó una orden",
  order_without_fill: "Se creó una orden, pero no llegó a ejecutarse",
  execution_unconfirmed:
    "Se ejecutó, pero falta confirmar la posición o el resultado",
};

/** Título y nota de honestidad de cada capa (qué mide y qué NO afirma). */
export const AUTO_NO_TRADE_LAYER_COPY: Record<
  AutoNoTradeLayerId,
  { title: string; honestyNote: string }
> = {
  discovery: {
    title: "Descubrimiento y decisión de entrada",
    honestyNote:
      "Universo, candidatos y veto de la cadena de Estudio AUTO-paper. No es la traza del motor determinista: cuando un dato no llega, se declara.",
  },
  engine: {
    title: "Cadena del motor AUTO",
    honestyNote:
      "Traza del motor por ciclo. Los pasos que el servicio no publica se declaran «Sin dato todavía»; no se deducen del ranking.",
  },
};

/** Título de la superficie completa. */
export const AUTO_NO_TRADE_PANEL_TITLE = "Por qué AUTO no operó";

export const AUTO_NO_TRADE_PANEL_DESCRIPTION =
  "Ante un día sin operaciones, distingue si AUTO no encontró oportunidad, decidió no operar o se quedó bloqueado en una etapa posterior. Cada causa enlaza con el registro que la demuestra.";

/**
 * Motivos de entrada (`PaperDeskEntryReasonCodeV1`) en lenguaje de usuario.
 * Un código no catalogado degrada a `Sin dato todavía`, nunca se pinta crudo.
 */
const ENTRY_REASON_LABELS: Record<PaperDeskEntryReasonCodeV1, string> = {
  ENTRY_NO_TRIGGER: "Sin disparador de entrada",
  ENTRY_INVALID_STOP: "Stop inválido",
  ENTRY_RISK_LIMIT: "Límite de riesgo alcanzado",
  ENTRY_STALE_DATA: "Datos desactualizados",
  ENTRY_MANDATE_BLOCK: "Mandato bloqueado",
  ENTRY_POLICY_MISSING: "Sin política de ejecución",
  ENTRY_MARKET_CLOSED: "Mercado cerrado",
  ENTRY_DUPLICATE: "Entrada duplicada",
  ENTRY_ENV_BLOCKED: "Ejecución deshabilitada por entorno",
  ENTRY_UNIVERSE_EMPTY: "Universo vacío",
  ENTRY_UNIVERSE_UNAVAILABLE: "Universo no disponible",
  ENTRY_INFRA_UNAVAILABLE: "Infraestructura no disponible",
};

export function entryReasonLabel(code: string | null | undefined): string {
  if (code == null || code === "") return absentDataLabel();
  return (
    ENTRY_REASON_LABELS[code as PaperDeskEntryReasonCodeV1] ?? absentDataLabel()
  );
}

/** Motivos globales de denegación (dryRun/entorno/mercado) en lenguaje de usuario. */
const JIT_DENY_LABELS: Record<string, string> = {
  data_stale: "Datos desactualizados",
  market_closed: "Mercado cerrado",
  portfolio_drift: "Descuadre de cartera",
  paper_auto_env_blocked: "Ejecución AUTO deshabilitada",
  data_unavailable: "Datos no disponibles",
};

export function jitDenyLabel(code: string | null | undefined): string {
  if (code == null || code === "") return absentDataLabel();
  return JIT_DENY_LABELS[code] ?? absentDataLabel();
}

/** Estados de una causa. */
export type AutoNoTradeStatus = "occurred" | "not_applicable" | "unknown";

/**
 * Estado en primer nivel. `unknown` reutiliza el rótulo oficial del hueco (Opción B): no se
 * inventa un «No» ni un «0» donde no hubo medición.
 */
export const AUTO_NO_TRADE_STATUS_LABELS: Record<AutoNoTradeStatus, string> = {
  occurred: "Ocurrió",
  not_applicable: "No aplica",
  unknown: absentDataLabel(),
};

/** Nota de hueco reutilizable (una sola casa del literal). */
export const AUTO_NO_TRADE_UNMEASURED_NOTE = absentDataLabel();
