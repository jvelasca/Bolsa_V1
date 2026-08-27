/**
 * Arquitectura de usuario V1.20 (ADR-040).
 *
 * Labels/rutas unit-testeables sin montar la barra.
 * L1: Hoy · Mercado · Cartera · Asesor · Laboratorio.
 * Nombres internos (Decision Spine, Consola ops, Journal, Libro, Mesa) no son puertas L1.
 *
 * @see docs/adr/040-user-information-architecture.md
 * @see docs/adr/037-mesa-hoy-operational-ux.md §8
 */

/** Home operativa diaria — ¿qué debo hacer hoy? (ADR-037 + ADR-040). */
export const MESA_LABEL = "Hoy" as const;
export const MESA_PATH = "/mesa" as const;
export const MESA_HINT =
  "Briefing diario: incidentes, atención, posiciones y oportunidades" as const;

/** Terminal de mercado (ruta histórica `/trading`). */
export const MERCADO_LABEL = "Mercado" as const;
export const MERCADO_PATH = "/trading" as const;
export const MERCADO_HINT =
  "Terminal: watchlist, gráfico, operaciones y operativa" as const;

/** @deprecated Use MERCADO_LABEL — alias histórico para imports legacy. */
export const TRADING_NAV_LABEL = MERCADO_LABEL;

/** Hub diario de señales (ruta histórica `/screeners`; bajo Mercado). */
export const SEÑALES_LABEL = "Señales" as const;
export const SEÑALES_PATH = "/screeners" as const;

/** Menú de backtests en nav (mismos hrefs; ya no dice Backtesting). */
export const LABORATORIO_LABEL = "Laboratorio" as const;

export const ASESOR_LABEL = "Asesor" as const;
/** Hub científico / ledger (ruta histórica `/research`; nav «Asesor»). */
export const ASESOR_PATH = "/research" as const;
export const VER_EN_ASESOR_LABEL = "Ver en Asesor" as const;
export const LEDGER_ASESOR_LINK_LABEL = "Ledger Asesor →" as const;
export const CONFIRMAR_LABEL = "Confirmar" as const;

/** Cartera (antes Libro) — posiciones / órdenes / historial / riesgo. */
export const CARTERA_LABEL = "Cartera" as const;
/** @deprecated Use CARTERA_LABEL. */
export const LIBRO_LABEL = CARTERA_LABEL;

export const CARTERA_POSICIONES_LABEL = "Posiciones" as const;
export const CARTERA_ORDENES_LABEL = "Órdenes" as const;
export const CARTERA_HISTORIAL_LABEL = "Historial" as const;
export const CARTERA_RIESGO_LABEL = "Riesgo" as const;

/** @deprecated Aliases Libro → Cartera. */
export const LIBRO_OPERACIONES_LABEL = CARTERA_POSICIONES_LABEL;
export const LIBRO_HISTORIAL_LABEL = CARTERA_HISTORIAL_LABEL;

/** V1.20 — Posiciones en Hoy view=posiciones (compat focus=libro). */
export const CARTERA_POSICIONES_PATH = "/mesa?view=posiciones" as const;
export const CARTERA_ORDENES_PATH =
  "/mesa?view=posiciones&focus=ordenes" as const;
export const CARTERA_RIESGO_PATH =
  "/mesa?view=posiciones&focus=riesgo" as const;
/** @deprecated */
export const LIBRO_OPERACIONES_PATH = CARTERA_POSICIONES_PATH;

export const OPERATIONAL_CONSOLE_PATH = "/operational-console" as const;
export const OPERATIONAL_CONSOLE_LABEL = "Consola avanzada" as const;
export const OPERATIONAL_CONSOLE_HINT =
  "Salud operativa read-only (OE-1, recon, incidentes)" as const;
export const LIBRO_HISTORIAL_PATH = "/history" as const;
export const CARTERA_HISTORIAL_PATH = LIBRO_HISTORIAL_PATH;

export const CARTERA_POSICIONES_HINT = "Posiciones abiertas (en Hoy)" as const;
export const CARTERA_ORDENES_HINT = "Órdenes y pendientes" as const;
export const CARTERA_HISTORIAL_HINT = "Ledger y fills" as const;
export const CARTERA_RIESGO_HINT = "Riesgo abierto y límites" as const;

/** @deprecated */
export const LIBRO_OPERACIONES_HINT = CARTERA_POSICIONES_HINT;
/** @deprecated */
export const LIBRO_HISTORIAL_HINT = CARTERA_HISTORIAL_HINT;

/** V1.20 — Decisiones (antes Decision Spine) en Hoy. */
export const DECISIONES_PATH = "/mesa?view=decisiones" as const;
export const DECISIONES_LABEL = "Decisiones" as const;
/** @deprecated Use DECISIONES_PATH / DECISIONES_LABEL. */
export const DECISION_SPINE_PATH = DECISIONES_PATH;
export const DECISION_SPINE_LABEL = DECISIONES_LABEL;

/** Vistas Hoy (`?view=`). */
export const HOY_VIEW = {
  resumen: "resumen",
  posiciones: "posiciones",
  oportunidades: "oportunidades",
  decisiones: "decisiones",
  journal: "journal",
  confirmar: "confirmar",
} as const;
export type HoyView = (typeof HOY_VIEW)[keyof typeof HOY_VIEW];

export function hoyViewHref(view: HoyView): string {
  if (view === HOY_VIEW.resumen) return MESA_PATH;
  return `${MESA_PATH}?view=${view}`;
}

/**
 * Piezas del menú Cartera (testable).
 */
export const CARTERA_NAV = {
  label: CARTERA_LABEL,
  items: [
    {
      label: CARTERA_POSICIONES_LABEL,
      href: CARTERA_POSICIONES_PATH,
      hint: CARTERA_POSICIONES_HINT,
    },
    {
      label: CARTERA_ORDENES_LABEL,
      href: CARTERA_ORDENES_PATH,
      hint: CARTERA_ORDENES_HINT,
    },
    {
      label: CARTERA_HISTORIAL_LABEL,
      href: CARTERA_HISTORIAL_PATH,
      hint: CARTERA_HISTORIAL_HINT,
    },
    {
      label: CARTERA_RIESGO_LABEL,
      href: CARTERA_RIESGO_PATH,
      hint: CARTERA_RIESGO_HINT,
    },
  ],
} as const;

/** @deprecated Use CARTERA_NAV. */
export const LIBRO_NAV = {
  label: CARTERA_LABEL,
  items: [
    {
      label: CARTERA_POSICIONES_LABEL,
      href: CARTERA_POSICIONES_PATH,
      hint: CARTERA_POSICIONES_HINT,
    },
    {
      label: CARTERA_HISTORIAL_LABEL,
      href: CARTERA_HISTORIAL_PATH,
      hint: CARTERA_HISTORIAL_HINT,
    },
  ],
} as const;

/** Menú Mercado (terminal + exploración). */
export const MERCADO_NAV = {
  label: MERCADO_LABEL,
  items: [
    {
      label: "Terminal",
      href: MERCADO_PATH,
      hint: MERCADO_HINT,
    },
    {
      label: SEÑALES_LABEL,
      href: SEÑALES_PATH,
      hint: "Screening y rastreadores",
    },
    {
      label: "Instrumentos",
      href: "/instruments",
      hint: "Catálogo y fichas",
    },
    {
      label: "Alertas",
      href: "/alerts",
      hint: "Alertas de precio",
    },
  ],
} as const;

/**
 * Hint del primer ítem del menú Asesor (`hint` existente).
 * Tesis / FA — no es el bucle diario de señales.
 */
export const ASESOR_TESIS_HINT =
  "Tesis y fundamental — no es el bucle diario de señales" as const;

/** Copy de mesa para Estudio (API list id `estudio` / ADR-024 no cambia). */
export const UNIVERSO_EN_VIGILANCIA = "Universo en vigilancia" as const;

/** Nivel 1 — cinco conceptos de usuario (ADR-040). */
export const DAILY_NAV_ORDER = [
  MESA_LABEL,
  MERCADO_LABEL,
  CARTERA_LABEL,
  ASESOR_LABEL,
  LABORATORIO_LABEL,
] as const;

/** UX-01…05 — destinos canónicos (DoD producto). */
export const UX_DOOR = {
  whatToDoToday: MESA_LABEL,
  bestToBuy: `${MESA_LABEL} → Oportunidades`,
  studySymbol: `${MERCADO_LABEL} / ${ASESOR_LABEL}`,
  modifyOrder: `${CARTERA_LABEL} → Órdenes`,
  opsFailed: `${MESA_LABEL} → estado operativo → Detalles`,
} as const;

/**
 * @deprecated Herramientas ya no es L1. Conservado para tests de migración.
 * Overview/Cuentas/Fiscal → ⚙; Alertas → 🔔; Spine/Consola/Journal → Hoy.
 */
export const HERRAMIENTAS_NAV_ORDER = [
  "Overview",
  "Cuentas",
  "Alertas",
  "Instrumentos",
] as const;

/**
 * Title del chevron contraído en list-hub (atajos a puertas diarias).
 * No nombra el objeto «Rastreadores» de la página Señales.
 */
export const LIST_HUB_EXPAND_ACCESOS_TITLE =
  `Accesos: ${SEÑALES_LABEL}, Alertas, ${LABORATORIO_LABEL}` as const;

export const LAB_TESIS_NAV_ORDER = [LABORATORIO_LABEL, ASESOR_LABEL] as const;

/** Deep-link al historial del Asesor (ledger Research API). */
export function asesorHistoryHref(trialId?: string | null): string {
  const params = new URLSearchParams({ tab: "history" });
  const id = trialId?.trim();
  if (id) params.set("trialId", id);
  return `${ASESOR_PATH}?${params.toString()}`;
}

/**
 * Banner Operativa cuando el modo exige pertenecer a Estudio.
 * `mode` ya viene en mayúsculas (p. ej. SEMI).
 */
export function formatFueraUniversoOperativaCopy(mode: string): string {
  return `Fuera del Universo en vigilancia — ${mode} exige estar en Estudio`;
}
