/**
 * S4-agregador-evidencia — vocabulario ÚNICO de primer nivel (castellano).
 *
 * Única casa de la copy del agregado. Los tokens crudos del contrato (`READY`/`MATCH`/`MIXED`…)
 * NO viven en el primer nivel: aquí se traducen a frases de usuario. El gate de primer nivel
 * vigila que no se filtren enums ni el comodín de dato ausente.
 *
 * Invariantes:
 * - **`UNKNOWN ≠ 0`.** Un hueco reutiliza el rótulo de `absent-data` («Sin dato todavía»).
 * - **Sin promoción.** Ninguna etiqueta sugiere que una capa confirme la siguiente.
 *
 * @see docs/PROJECT_PREMISES.md §5.2
 * @see apps/web/src/features/auto/auto-no-trade-labels.ts (precedente de vocabulario único)
 */

import { absentDataLabel } from "@/components/absent-data";
import type { DiaDEvidenceLayerId } from "./dia-d-evidence-aggregate";

/** Título y descripción de la superficie completa. */
export const DIA_D_EVIDENCE_AGGREGATE_TITLE = "Evidencia de la operativa";

export const DIA_D_EVIDENCE_AGGREGATE_DESCRIPTION =
  "Reúne las cuatro capas de evidencia sin promocionar ninguna: ventana, contraste declarado frente a ejecutado, evidencia fuera de muestra y ejecución real. Mientras no exista ejecución real, el veredicto es NO CONFIRMADO.";

/** Veredicto global (único que este agregado emite). */
export const DIA_D_EVIDENCE_GLOBAL_VERDICT_LABEL = "NO CONFIRMADO";

/** Nota máquina-legible de no promoción (eco de §5.2). */
export const DIA_D_EVIDENCE_NON_PROMOTION_NOTE =
  "Alcanzar una capa no confirma la siguiente: la ventana lista no confirma el contraste, y el contraste no confirma la evidencia fuera de muestra. La confirmación queda reservada a la ejecución real, que todavía no se emite.";

/** Motivo del hueco cuando la sub-vista que lo mide aún no se ha abierto. */
export const DIA_D_EVIDENCE_OPEN_SUBVIEW_REASON =
  "Abre la sub-vista para medirla.";

/** Motivo del hueco estructural de la capa PAPER (confirmación reservada). */
export const DIA_D_EVIDENCE_PAPER_REASON =
  "La evidencia de ejecución real todavía no se emite.";

/** Copy por capa: título, nota de honestidad y origen (sin jerga de motor). */
export const DIA_D_EVIDENCE_LAYER_COPY: Record<
  DiaDEvidenceLayerId,
  { title: string; honestyNote: string; sourceLabel: string }
> = {
  window: {
    title: "Ventana operativa",
    honestyNote:
      "Mide si la ventana reúne días, episodios y ciclos suficientes. Estar lista no confirma la operativa.",
    sourceLabel: "Feedback por ventana",
  },
  reconciliation: {
    title: "Declarado frente a ejecutado",
    honestyNote:
      "Contrasta lo que el replay declaró con lo que después se ejecutó de verdad. Coincidir no confirma la operativa.",
    sourceLabel: "Sandbox por día",
  },
  oos: {
    title: "Evidencia fuera de muestra",
    honestyNote:
      "Evidencia fuera de muestra del replay por instrumento. Estar soportada no confirma la operativa.",
    sourceLabel: "Feedback por valor",
  },
  paper: {
    title: "Evidencia de ejecución real",
    honestyNote:
      "Evidencia de ejecución real. Queda reservada y todavía no se emite; por eso el veredicto global nunca se cierra.",
    sourceLabel: "Ejecución real",
  },
};

/** Rótulos humanizados de la capa VENTANA (clave = token crudo, nivel 3). */
export const WINDOW_VERDICT_LABELS: Record<string, string> = {
  READY: "Ventana lista",
  INCONCLUSIVE: "Ventana no concluyente",
};

/** Rótulos humanizados de la capa RECONCILIACIÓN. `NOT_MEASURED` no está: es hueco. */
export const RECONCILIATION_VERDICT_LABELS: Record<string, string> = {
  MATCH: "Coincide",
  PARTIAL: "Coincide en parte",
  DIVERGENT: "Discrepa",
};

/** Rótulos humanizados de la capa OOS. `NOT_MEASURED` no está: es hueco. */
export const OOS_VERDICT_LABELS: Record<string, string> = {
  OOS_SUPPORTED: "Soportado fuera de muestra",
  MIXED: "Resultado mixto",
  REFUTED: "Refutado",
};

/** Rótulo del hueco reutilizable (una sola casa del literal). */
export const DIA_D_EVIDENCE_UNMEASURED_NOTE = absentDataLabel();
