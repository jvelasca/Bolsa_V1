/**
 * R-12 C3 — copy de mesa para AUTO de cuenta (libro operativo).
 * AUTO no está disponible en BETA: no se presenta como modo usable.
 * `DEMO_BOOK_AUTO_UI_ENABLED` permanece false; no thaw de execute.
 *
 * No confundir con Lista AUTO del Laboratorio (`list-auto-activity-store`).
 */

/** Flag de producto: no habilitar pill AUTO hasta thaw explícito. */
export const DEMO_BOOK_AUTO_UI_ENABLED = false;

/** R-12 C3 — etiqueta trader: AUTO de cuenta no usable en BETA. */
export const DEMO_BOOK_AUTO_UNAVAILABLE_LABEL = "No disponible (BETA)";

/** R-12 C3 — tooltip de mesa. Sin jerga de ops; SEMI = firma humana. */
export const DEMO_BOOK_AUTO_TOOLTIP =
  "AUTO no está disponible en BETA. Usa SEMI: la app propone y tú firmas.";

/** R-12 C3 — líneas cortas si el panel las muestra. Sin jerga de execute/ops. */
export const DEMO_BOOK_AUTO_RISK_LINES = [
  "AUTO no está disponible en BETA.",
  "SEMI: tú firmas cada operación (Confirm).",
] as const;

/** R-12 C3 — pie del panel Config operativa. */
export const DEMO_BOOK_AUTO_FOOTER =
  "SEMI = Confirm humano. AUTO no disponible (BETA).";
