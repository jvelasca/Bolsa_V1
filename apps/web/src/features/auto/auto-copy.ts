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

export const AUTO_SECTION_COPY: Record<AutoSectionId, AutoSectionCopy> = {
  operar: {
    title: "Operar",
    description:
      "Qué ha elegido AUTO y qué operaciones hay en curso. Todo es dinero virtual (DEMO); no necesitas intervenir.",
  },
  actividad: {
    title: "Actividad",
    description:
      "Qué ha hecho AUTO, en orden: cada análisis, cada operación y cada paso, en una sola línea temporal. Todo es dinero virtual (DEMO).",
  },
  cartera: {
    title: "Cartera",
    description:
      "Vista de la misma cuenta que Cartera, en dinero virtual (DEMO): posiciones simuladas, órdenes en curso e historial. Antes de reducir o cerrar, la app te pide que confirmes.",
  },
  riesgo: {
    title: "Riesgo",
    description:
      "Cuánto puedes perder y qué límites te protegen. Es solo lectura: lo que falta se marca «Sin dato todavía», nunca se rellena con ceros.",
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
