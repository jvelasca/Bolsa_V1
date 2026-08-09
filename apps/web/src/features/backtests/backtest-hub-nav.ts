/**
 * Navegación tipo del Hub Backtesting (`/backtests`).
 *
 * Tipo de tab, fuente de run, foco de resultado y utilidades de parsing.
 * Extraído de `backtests-page.tsx` (F4·8) para hacer testeable la lógica pura
 * y reducir el "god component".
 */

export type HubTab = "run" | "history" | "strategies" | "jobs";

export type RunSource = "preset" | "saved";

export type UniverseMode = "single" | "list";

export type ResultFocus =
  | "detail"
  | "fundamental"
  | "coach"
  | "lab"
  | "finalists"
  | "ranking"
  | "list_auto";

/** Vistas de análisis (técnico = legacy `detail`). */
export function isAnalysisResultFocus(focus: ResultFocus): boolean {
  return focus === "detail" || focus === "fundamental";
}

/** Parsea el parámetro de URL `?tab=` a un HubTab válido (default `run`). */
export function parseTab(raw: string | null): HubTab {
  if (raw === "history") return "history";
  if (raw === "strategies") return "strategies";
  if (raw === "jobs") return "jobs";
  // Legacy deep-links (?tab=new) → Run
  if (raw === "new" || raw === "run" || raw == null || raw === "") return "run";
  return "run";
}

/** Verifica si una cadena cruda es un tab válido sin normalizar (útil en guards). */
export function isHubTab(raw: string | null): raw is HubTab {
  return (
    raw === "run" || raw === "history" || raw === "strategies" || raw === "jobs"
  );
}
