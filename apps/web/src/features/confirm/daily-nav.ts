/**
 * Mesa diaria vs laboratorio (R-12 C2 + C4).
 *
 * Labels/rutas unit-testeables sin montar la barra. El bucle diario
 * (Trading · Señales · Confirmar · Libro) es primer nivel; Laboratorio y
 * Asesor quedan en menú. Libro es dropdown a Operaciones + Historial (no
 * fusiona páginas). No fusiona `/research` + `/screeners`.
 *
 * @see docs/engineering/plan-r12-track-c-frontend-2026-08-21.md § C2 · § C4
 */

/** Home operativa diaria — ¿qué debo hacer hoy? (ADR-037). */
export const MESA_LABEL = "Mesa · Hoy" as const;
export const MESA_PATH = "/mesa" as const;
export const MESA_HINT =
  "Briefing diario: incidentes, atención, posiciones y candidatos" as const;

/** Hub diario de señales (ruta histórica `/screeners`; copy trader). */
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
export const TRADING_NAV_LABEL = "Trading" as const;

/** Dropdown Libro (R-12 C4): Operaciones + Historial; Consola ops → Herramientas (V1.15). */
export const LIBRO_LABEL = "Libro" as const;
export const LIBRO_OPERACIONES_LABEL = "Operaciones" as const;
export const LIBRO_HISTORIAL_LABEL = "Historial" as const;
/** V1.19 — Libro absorbido en Mesa (?focus=libro). */
export const LIBRO_OPERACIONES_PATH = "/mesa?focus=libro" as const;
export const OPERATIONAL_CONSOLE_PATH = "/operational-console" as const;
export const OPERATIONAL_CONSOLE_LABEL = "Consola ops" as const;
export const OPERATIONAL_CONSOLE_HINT =
  "Salud operativa read-only (OE-1, recon, incidentes)" as const;
export const LIBRO_HISTORIAL_PATH = "/history" as const;
/** Hint DropdownMenu: posiciones abiertas / órdenes. */
export const LIBRO_OPERACIONES_HINT = "Posiciones y órdenes (en Mesa)" as const;
/** Hint DropdownMenu: ledger contable + fills. */
export const LIBRO_HISTORIAL_HINT = "Ledger y fills" as const;

/** V1.19 — Decision Board absorbido en Mesa (?focus=spine). */
export const DECISION_SPINE_PATH = "/mesa?focus=spine" as const;
export const DECISION_SPINE_LABEL = "Decision Spine" as const;

/**
 * Piezas del menú Libro (testable; misma forma que items de DropdownMenu).
 * Tras Confirmar en el bucle diario; antes del separador de herramientas.
 */
export const LIBRO_NAV = {
  label: LIBRO_LABEL,
  items: [
    {
      label: LIBRO_OPERACIONES_LABEL,
      href: LIBRO_OPERACIONES_PATH,
      hint: LIBRO_OPERACIONES_HINT,
    },
    {
      label: LIBRO_HISTORIAL_LABEL,
      href: LIBRO_HISTORIAL_PATH,
      hint: LIBRO_HISTORIAL_HINT,
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

export const DAILY_NAV_ORDER = [
  MESA_LABEL,
  TRADING_NAV_LABEL,
  SEÑALES_LABEL,
  CONFIRMAR_LABEL,
  LIBRO_LABEL,
] as const;

export const HERRAMIENTAS_NAV_ORDER = [
  "Overview",
  "Cuentas",
  "Alertas",
  "Instrumentos",
  "Decision Board",
  OPERATIONAL_CONSOLE_LABEL,
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
