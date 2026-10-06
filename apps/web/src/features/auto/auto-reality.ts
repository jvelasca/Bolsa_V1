/**
 * AUTO UI REFACTOR (F1) — semáforo de realidad monetaria (helper puro).
 *
 * Una sola respuesta, imposible de mal-interpretar, a la pregunta del usuario básico:
 * *«¿AUTO opera con dinero real?»* → **NO**: la operativa AUTO es simulada.
 *
 * El helper es **puro**: no lee de red ni de storage. La componente
 * `AutoRealityStrip` cablea las fuentes (cuenta activa, kill switch, prefs de libro,
 * armado local) y le pasa el resultado.
 *
 * Invariantes:
 * - **Cuenta activa ≠ modo de ejecución AUTO.** El banner declara el modo del espacio
 *   (`DINERO VIRTUAL` · `AUTO DEMO`) aunque la cuenta conectada sea `live`.
 * - Una cuenta ausente no apaga ese banner: se declara `NO MEDIDO` en su línea y en `notes`.
 * - El rojo `DINERO REAL` no se pinta. AUTO no tiene camino de ejecución real.
 * - **No re-deriva** el modo de libro: delega en `buildPaperAutoPosture` (`@bolsa/shared`).
 *
 * @see docs/engineering/spec-auto-cockpit-usuario-basico-2026-10-05.md §F1
 * @see docs/engineering/spec-auto-operacion-usuario-basico-2026-10-06.md §6
 * @see packages/shared/src/cognitive/paper-auto-posture.ts
 */

import {
  NO_MEASUREMENT_LABEL,
  buildPaperAutoPosture,
  type InvestmentAccountType,
} from "@bolsa/shared";

/**
 * Tono del banner de ejecución. Hoy el helper solo emite `virtual`: el tipo de cuenta
 * no recolorea AUTO. `real` y `unknown` quedan en el tipo para la tira, sin usarse.
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
   * `true` = el modo de ejecución AUTO no usa dinero real. No depende del tipo de cuenta.
   */
  isVirtual: boolean;
  /** `DINERO VIRTUAL`. El modo AUTO no pinta `DINERO REAL`. */
  moneyLabel: string;
  /** `AUTO DEMO`. */
  modeLabel: string;
  /** `No envía órdenes a XTB`. */
  brokerLabel: string;
  /** Cuenta conectada, aparte del modo AUTO. `NO MEDIDO` si el dato falta. */
  accountTypeLabel: string;
  /** Datos de realidad ausentes que se declaran (nunca se asumen). */
  notes: string[];
  /** La maquinaria AUTO está activa (armada). `false` si no. */
  autoActive: boolean;
  /** `Activo` / `Inactivo`. */
  autoLabel: string;
};

export const AUTO_REALITY_MONEY_VIRTUAL = "DINERO VIRTUAL";
export const AUTO_REALITY_MODE_DEMO = "AUTO DEMO";
export const AUTO_REALITY_BROKER_NO_ORDERS = "No envía órdenes a XTB";
export const AUTO_REALITY_ACCOUNT_LIVE = "Cuenta conectada: XTB LIVE";
export const AUTO_REALITY_DISCLAIMER =
  "Operativa 100% simulada (paper): tus decisiones no mueven dinero real.";
export const AUTO_REALITY_AUTO_ACTIVE = "Activo";
export const AUTO_REALITY_AUTO_INACTIVE = "Inactivo";

/**
 * Etiqueta de la cuenta conectada, separada del modo AUTO.
 * Un tipo ausente es `NO MEDIDO`. `live` no se lee como dinero de la ejecución.
 */
export function accountTypeRealityLabel(
  type: InvestmentAccountType | null | undefined,
): string {
  switch (type) {
    case "simulated":
      return "Cuenta demo";
    case "paper":
      return "Paper (broker futuro)";
    case "live":
      return AUTO_REALITY_ACCOUNT_LIVE;
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
  // El banner declara el modo AUTO, no la cuenta. Un tipo ausente se anota aparte
  // y no apaga `DINERO VIRTUAL` ni lo convierte en dinero real.
  if (input.accountType == null) {
    notes.push("Tipo de cuenta NO MEDIDO");
  }
  if (input.paperDExecuteEnv == null) {
    notes.push("Ejecución paper NO MEDIDA");
  }

  return {
    tone: "virtual",
    isVirtual: true,
    moneyLabel: AUTO_REALITY_MONEY_VIRTUAL,
    modeLabel: AUTO_REALITY_MODE_DEMO,
    brokerLabel: AUTO_REALITY_BROKER_NO_ORDERS,
    accountTypeLabel: accountTypeRealityLabel(input.accountType),
    notes,
    autoActive: posture.autoActive,
    autoLabel: posture.autoActive
      ? AUTO_REALITY_AUTO_ACTIVE
      : AUTO_REALITY_AUTO_INACTIVE,
  };
}
