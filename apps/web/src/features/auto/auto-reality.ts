/**
 * AUTO UI REFACTOR (F1) — semáforo de realidad monetaria (helper puro).
 *
 * Una sola respuesta, imposible de mal-interpretar, a la pregunta del usuario básico:
 * *«¿AUTO opera con dinero real?»* → **NO**: hoy la operativa es 100% simulada (paper).
 *
 * El helper es **puro**: no lee de red ni de storage. La componente
 * `AutoRealityStrip` cablea las fuentes (cuenta activa, kill switch, prefs de libro,
 * armado local) y le pasa el resultado.
 *
 * Invariantes:
 * - **No se asume**: un tipo de cuenta ausente se declara `NO MEDIDO` y toma el tono neutro
 *   `unknown` (ámbar), nunca el verde tranquilizador de `virtual`.
 * - **Fail-closed**: `live` es el único estado que reclama dinero real.
 * - **No re-deriva** el modo de libro: delega en `buildPaperAutoPosture` (`@bolsa/shared`).
 *
 * @see docs/engineering/spec-auto-cockpit-usuario-basico-2026-10-05.md §F1
 * @see packages/shared/src/cognitive/paper-auto-posture.ts
 */

import {
  NO_MEASUREMENT_LABEL,
  buildPaperAutoPosture,
  type InvestmentAccountType,
} from "@bolsa/shared";

/**
 * Tono del semáforo: verde = virtual, rojo = dinero real (reservado, no alcanzable hoy),
 * ámbar = tipo de cuenta no confirmado (el dato aún no llegó o el registro no lo trae).
 */
export type AutoRealityTone = "virtual" | "real" | "unknown";

export type AutoRealityInputV1 = {
  /** Tipo de la cuenta activa. Ausente/`null` → se declara `NO MEDIDO`. */
  accountType?: InvestmentAccountType | null;
  /** Modo del libro operativo (manual/semi/auto). */
  bookMode?: string | null;
  /** Armado local AUTO (A3). */
  autoArmed?: boolean | null;
  /** Eco server `PAPER_D_EXECUTE`. */
  paperDExecuteEnv?: boolean | null;
};

export type AutoRealityV1 = {
  tone: AutoRealityTone;
  /**
   * `true` = la operativa no usa dinero real. `null` = no se sabe (tipo de cuenta no
   * confirmado): un hueco no se rellena con `true` (principio `UNKNOWN ≠ 0`).
   */
  isVirtual: boolean | null;
  /** `DINERO VIRTUAL` / `DINERO REAL`. */
  moneyLabel: string;
  /** `AUTO DEMO`. */
  modeLabel: string;
  /** `No envía órdenes a XTB`. */
  brokerLabel: string;
  /** Tipo de cuenta legible; `NO MEDIDO` si el dato falta. */
  accountTypeLabel: string;
  /** Datos de realidad ausentes que se declaran (nunca se asumen). */
  notes: string[];
  /** La maquinaria AUTO está activa (armada). `false` si no. */
  autoActive: boolean;
  /** `Activo` / `Inactivo`. */
  autoLabel: string;
};

export const AUTO_REALITY_MONEY_VIRTUAL = "DINERO VIRTUAL";
export const AUTO_REALITY_MONEY_REAL = "DINERO REAL";
export const AUTO_REALITY_MONEY_UNKNOWN = "TIPO DE CUENTA NO CONFIRMADO";
export const AUTO_REALITY_MODE_DEMO = "AUTO DEMO";
export const AUTO_REALITY_BROKER_NO_ORDERS = "No envía órdenes a XTB";
export const AUTO_REALITY_BROKER_LIVE = "Broker LIVE conectado";
export const AUTO_REALITY_BROKER_UNKNOWN = "Broker NO MEDIDO";
export const AUTO_REALITY_DISCLAIMER =
  "Operativa 100% simulada (paper): tus decisiones no mueven dinero real.";
export const AUTO_REALITY_AUTO_ACTIVE = "Activo";
export const AUTO_REALITY_AUTO_INACTIVE = "Inactivo";

/** Etiqueta de tipo de cuenta **honesta**: un tipo ausente es `NO MEDIDO`, no `Live`. */
export function accountTypeRealityLabel(
  type: InvestmentAccountType | null | undefined,
): string {
  switch (type) {
    case "simulated":
      return "Cuenta demo";
    case "paper":
      return "Paper (broker futuro)";
    case "live":
      return "Cuenta real";
    default:
      return NO_MEASUREMENT_LABEL;
  }
}

export function buildAutoReality(input: AutoRealityInputV1): AutoRealityV1 {
  const bookMode =
    input.bookMode === "manual" ||
    input.bookMode === "semi" ||
    input.bookMode === "auto"
      ? input.bookMode
      : null;
  const posture = buildPaperAutoPosture({
    bookMode,
    autoArmed: input.autoArmed ?? null,
    paperDExecuteEnv: input.paperDExecuteEnv ?? null,
  });

  const notes: string[] = [];
  const accountKnown = input.accountType != null;
  // Sólo `live` reclama dinero real. Un tipo ausente NO se finge `virtual`: se declara
  // `unknown` (ámbar) para no pintar el verde tranquilizador sobre un hueco.
  const realMoney = input.accountType === "live";
  if (!accountKnown) {
    notes.push("Tipo de cuenta NO MEDIDO");
  }
  if (input.paperDExecuteEnv == null) {
    notes.push("Ejecución paper NO MEDIDA");
  }

  const tone: AutoRealityTone = !accountKnown
    ? "unknown"
    : realMoney
      ? "real"
      : "virtual";
  const moneyLabel = !accountKnown
    ? AUTO_REALITY_MONEY_UNKNOWN
    : realMoney
      ? AUTO_REALITY_MONEY_REAL
      : AUTO_REALITY_MONEY_VIRTUAL;
  const brokerLabel = !accountKnown
    ? AUTO_REALITY_BROKER_UNKNOWN
    : realMoney
      ? AUTO_REALITY_BROKER_LIVE
      : AUTO_REALITY_BROKER_NO_ORDERS;

  return {
    tone,
    isVirtual: accountKnown ? !realMoney : null,
    moneyLabel,
    modeLabel: AUTO_REALITY_MODE_DEMO,
    brokerLabel,
    accountTypeLabel: accountTypeRealityLabel(input.accountType),
    notes,
    autoActive: posture.autoActive,
    autoLabel: posture.autoActive
      ? AUTO_REALITY_AUTO_ACTIVE
      : AUTO_REALITY_AUTO_INACTIVE,
  };
}
