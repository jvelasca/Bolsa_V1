/**
 * AUTO UI REFACTOR (F4a) — copy de primer nivel en lenguaje de usuario.
 *
 * Fuente única de los títulos y descripciones de las cinco secciones del espacio AUTO.
 * El primer nivel NO usa jerga de ingeniería (`read-only`, `cross-ciclo`, `enqueue`): dice
 * qué puede hacer el usuario y qué está viendo. El vocabulario técnico se conserva en el
 * detalle bajo demanda, no aquí.
 *
 * @see docs/engineering/spec-auto-cockpit-usuario-basico-2026-10-05.md §F4
 */

export type AutoSectionId =
  | "operar"
  | "actividad"
  | "cartera"
  | "riesgo"
  | "analisis"
  | "sistema";

export type AutoSectionCopy = {
  title: string;
  description: string;
};

/**
 * Frase oficial de dinero virtual (`UI5-20`, enmienda UI 7.0).
 *
 * Lenguaje único para explicar que AUTO no usa dinero real. Sustituye a la alternancia
 * DEMO/PAPER/SIMULADO/DINERO VIRTUAL en el primer nivel: un solo término = un solo significado.
 */
export const AUTO_VIRTUAL_MONEY_PHRASE =
  "AUTO trabaja con dinero virtual: no utiliza dinero real ni envía órdenes reales.";

export const AUTO_SECTION_COPY: Record<AutoSectionId, AutoSectionCopy> = {
  operar: {
    title: "Operar",
    description:
      "Qué oportunidades ha encontrado AUTO y qué operaciones están en curso. Es dinero virtual; no necesitas intervenir.",
  },
  actividad: {
    title: "Actividad",
    description:
      "Qué ha hecho AUTO, en orden: cada análisis, cada operación y cada paso, en una sola línea temporal. Es dinero virtual.",
  },
  cartera: {
    title: "Cartera",
    description:
      "Vista de la misma cuenta que Cartera, en dinero virtual: posiciones simuladas, órdenes en curso e historial. AUTO puede continuar su operativa simulada sin tu firma; las acciones que tú hagas sobre una posición sí requieren tu confirmación.",
  },
  riesgo: {
    title: "Riesgo",
    description:
      "¿Hay algún problema de riesgo ahora mismo? Es solo lectura: lo que falta se marca «Sin dato todavía», nunca se rellena con ceros.",
  },
  analisis: {
    title: "Análisis",
    description:
      "Qué ha pasado y qué se puede aprender: resultados, evidencia de cada estrategia e investigación. Aquí se explica; no se opera.",
  },
  sistema: {
    title: "Sistema",
    description:
      "Cómo está funcionando AUTO por dentro: salud del motor, qué registró la simulación, cuadre de cuentas y auditoría. Es solo lectura.",
  },
};
