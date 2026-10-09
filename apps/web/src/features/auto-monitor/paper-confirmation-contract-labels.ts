/**
 * PAPER-1 — contrato de confirmación PAPER: vocabulario ÚNICO de primer nivel (castellano).
 *
 * Única casa de la copy del contrato. Los tokens crudos del material (`auto_cycle_settlement`,
 * `sim_fill_finance_context`, `COMPLETE`/`PARTIAL`…) NO viven en el primer nivel: aquí se
 * traducen a frases de usuario. El gate de primer nivel vigila que no se filtren identificadores
 * de motor ni el comodín de dato ausente.
 *
 * Invariantes:
 * - **`UNKNOWN ≠ 0`.** Un hueco reutiliza el rótulo de `absent-data` («Sin dato todavía»).
 * - **Sin promoción.** Ninguna etiqueta sugiere que un criterio aislado confirme la operativa.
 * - **La confirmación está reservada.** El rótulo global es «NO CONFIRMADO».
 *
 * @see docs/engineering/contrato-evidencia-paper-confirmacion-2026-10-09.md
 * @see docs/PROJECT_PREMISES.md §5.2
 * @see apps/web/src/features/auto-monitor/dia-d-evidence-aggregate-labels.ts (precedente S4)
 */

import { absentDataLabel } from "@/components/absent-data";
import type {
  PaperConfirmationCriterionId,
  PaperConfirmationCriterionStatus,
} from "./paper-confirmation-contract";

/** Título y descripción de la superficie del contrato. */
export const PAPER_CONFIRMATION_CONTRACT_TITLE =
  "Contrato de confirmación PAPER";

export const PAPER_CONFIRMATION_CONTRACT_DESCRIPTION =
  "Define qué evidencia durable de la ejecución real (operaciones, ejecuciones, cierres, costes y resultados) habilitaría la confirmación. No se emite confirmación: se declaran los criterios cumplidos, incumplidos o todavía sin dato.";

/** Veredicto global (único que este contrato emite). */
export const PAPER_CONFIRMATION_GLOBAL_VERDICT_LABEL = "NO CONFIRMADO";

/** Nota máquina-legible de no promoción. */
export const PAPER_CONFIRMATION_NON_PROMOTION_NOTE =
  "Ningún criterio aislado confirma la operativa: la confirmación permanece reservada y no se emite aunque todos los criterios se cumplan.";

/** Motivo de la reserva de la confirmación. */
export const PAPER_CONFIRMATION_RESERVED_REASON =
  "La confirmación de la ejecución real PAPER todavía no se emite: el contrato queda definido y su promoción está reservada.";

/** Rótulo del hueco reutilizable (una sola casa del literal). */
export const PAPER_CONFIRMATION_UNMEASURED_NOTE = absentDataLabel();

/** Estado de un criterio en primer nivel. `unknown` reutiliza el rótulo oficial del hueco. */
export const PAPER_CONFIRMATION_STATUS_LABELS: Record<
  PaperConfirmationCriterionStatus,
  string
> = {
  met: "Cumplido",
  unmet: "Incumplido",
  unknown: absentDataLabel(),
};

/** Copy de cada criterio: título, enunciado falsable, origen durable y motivos. */
export const PAPER_CONFIRMATION_CRITERION_COPY: Record<
  PaperConfirmationCriterionId,
  {
    title: string;
    requirement: string;
    sourceLabel: string;
    unknownReason: string;
    unmetReason: string;
  }
> = {
  window: {
    title: "Ventana operativa suficiente",
    requirement:
      "La ventana declara al menos cuatro días y dos episodios operados.",
    sourceLabel: "Ventana operativa PAPER",
    unknownReason: "La ventana todavía no declara días ni episodios operados.",
    unmetReason:
      "La ventana declarada no alcanza el mínimo de días y episodios operados.",
  },
  operation_lineage: {
    title: "Operaciones con linaje de ciclo",
    requirement:
      "Hay operaciones cerradas suficientes y todas declaran su identidad de ciclo.",
    sourceLabel: "Operaciones cerradas del material durable",
    unknownReason:
      "Las operaciones cerradas y su linaje de ciclo todavía no se han medido.",
    unmetReason:
      "No hay operaciones cerradas suficientes o alguna no declara su identidad de ciclo.",
  },
  execution_attribution: {
    title: "Ejecuciones atribuidas",
    requirement:
      "Hay ejecuciones durables suficientes y todas están atribuidas a su operación.",
    sourceLabel: "Ejecuciones durables por cuenta y operación",
    unknownReason:
      "Las ejecuciones durables y su atribución todavía no se han medido.",
    unmetReason:
      "No hay ejecuciones durables suficientes o alguna no está atribuida a su operación.",
  },
  closure_reconciliation: {
    title: "Cierres reconciliados",
    requirement:
      "Hay cierres durables suficientes y todos reconcilian con la ida y vuelta del material.",
    sourceLabel: "Cierres durables reconciliados con el material",
    unknownReason:
      "Los cierres durables y su reconciliación todavía no se han medido.",
    unmetReason:
      "No hay cierres durables suficientes o alguno no reconcilia con su ida y vuelta.",
  },
  cost_coverage: {
    title: "Cobertura de costes",
    requirement:
      "Todos los cierres que exigen un coste aplicado lo tienen medido por completo.",
    sourceLabel: "Fricción aplicada por operación cerrada",
    unknownReason: "La cobertura de costes todavía no se ha medido.",
    unmetReason:
      "Algún cierre con coste exigido no tiene su coste aplicado medido por completo.",
  },
  durable_results: {
    title: "Resultados durables",
    requirement:
      "Hay resultados durables suficientes, medidos sobre el cierre real de cada operación.",
    sourceLabel: "Resultado durable por operación cerrada",
    unknownReason: "Los resultados durables todavía no se han medido.",
    unmetReason:
      "No hay resultados durables suficientes medidos sobre el cierre real.",
  },
  non_contradiction: {
    title: "Sin contradicciones",
    requirement:
      "El material no declara ninguna contradicción entre sus cierres.",
    sourceLabel: "Contraste de cierres del material durable",
    unknownReason:
      "Las contradicciones entre cierres todavía no se han medido.",
    unmetReason: "El material declara contradicciones entre sus cierres.",
  },
};
