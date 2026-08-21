/**
 * Mesa diaria vs laboratorio (R-12 C2).
 *
 * Labels/rutas unit-testeables sin montar la barra. El bucle diario
 * (Trading · Señales · Confirmar) es primer nivel; Laboratorio y Asesor
 * quedan en menú. No fusiona `/research` + `/screeners`.
 *
 * @see docs/engineering/plan-r12-track-c-frontend-2026-08-21.md § C2
 */

/** Hub diario de señales (ruta histórica `/screeners`; copy trader). */
export const SEÑALES_LABEL = "Señales" as const;
export const SEÑALES_PATH = "/screeners" as const;

/** Menú de backtests en nav (mismos hrefs; ya no dice Backtesting). */
export const LABORATORIO_LABEL = "Laboratorio" as const;

export const ASESOR_LABEL = "Asesor" as const;
export const CONFIRMAR_LABEL = "Confirmar" as const;
export const TRADING_NAV_LABEL = "Trading" as const;

/**
 * Hint del primer ítem del menú Asesor (`hint` existente).
 * Tesis / FA — no es el bucle diario de señales.
 */
export const ASESOR_TESIS_HINT =
  "Tesis y fundamental — no es el bucle diario de señales" as const;

/** Copy de mesa para Estudio (API list id `estudio` / ADR-024 no cambia). */
export const UNIVERSO_EN_VIGILANCIA = "Universo en vigilancia" as const;

export const DAILY_NAV_ORDER = [
  TRADING_NAV_LABEL,
  SEÑALES_LABEL,
  CONFIRMAR_LABEL,
] as const;

export const HERRAMIENTAS_NAV_ORDER = [
  "Overview",
  "Cuentas",
  "Alertas",
  "Instrumentos",
] as const;

export const LAB_TESIS_NAV_ORDER = [LABORATORIO_LABEL, ASESOR_LABEL] as const;

/**
 * Banner Operativa cuando el modo exige pertenecer a Estudio.
 * `mode` ya viene en mayúsculas (p. ej. SEMI).
 */
export function formatFueraUniversoOperativaCopy(mode: string): string {
  return `Fuera del Universo en vigilancia — ${mode} exige estar en Estudio`;
}
