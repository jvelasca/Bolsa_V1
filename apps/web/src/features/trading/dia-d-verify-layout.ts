/**
 * Layout prefs Verify D→hoy (informe lateral + splits) — localStorage.
 * Premisa UI: preferencias en el dispositivo ([UI_PREFS_LOCALSTORAGE.md](../../UI_PREFS_LOCALSTORAGE.md)).
 */

export const DIA_D_VERIFY_LAYOUT_KEY = 'bolsa-dia-d-verify-layout-v1';

export type DiaDVerifyLayoutPrefs = {
  /** Informe lateral abierto. */
  reportOpen: boolean;
  /** Ancho del informe (solo desktop horizontal), %. */
  reportWidthPct: number;
  /** Altura del bloque película+informe vs equity+ops (apilado), %. */
  movieHeightPct: number;
  /** Ancho equity vs operaciones en la franja inferior (desktop), %. */
  equityWidthPct: number;
};

export const DEFAULT_DIA_D_VERIFY_LAYOUT: DiaDVerifyLayoutPrefs = {
  reportOpen: true,
  reportWidthPct: 28,
  movieHeightPct: 58,
  equityWidthPct: 52,
};

export function clampReportWidthPct(v: number): number {
  return Math.min(45, Math.max(18, v));
}

export function clampMovieHeightPct(v: number): number {
  return Math.min(78, Math.max(32, v));
}

export function clampEquityWidthPct(v: number): number {
  return Math.min(75, Math.max(25, v));
}

export function loadDiaDVerifyLayout(): DiaDVerifyLayoutPrefs {
  try {
    const raw = localStorage.getItem(DIA_D_VERIFY_LAYOUT_KEY);
    if (!raw) return { ...DEFAULT_DIA_D_VERIFY_LAYOUT };
    const o = JSON.parse(raw) as Partial<DiaDVerifyLayoutPrefs>;
    return {
      reportOpen: typeof o.reportOpen === 'boolean' ? o.reportOpen : true,
      reportWidthPct: clampReportWidthPct(
        typeof o.reportWidthPct === 'number' ? o.reportWidthPct : DEFAULT_DIA_D_VERIFY_LAYOUT.reportWidthPct,
      ),
      movieHeightPct: clampMovieHeightPct(
        typeof o.movieHeightPct === 'number' ? o.movieHeightPct : DEFAULT_DIA_D_VERIFY_LAYOUT.movieHeightPct,
      ),
      equityWidthPct: clampEquityWidthPct(
        typeof o.equityWidthPct === 'number' ? o.equityWidthPct : DEFAULT_DIA_D_VERIFY_LAYOUT.equityWidthPct,
      ),
    };
  } catch {
    return { ...DEFAULT_DIA_D_VERIFY_LAYOUT };
  }
}

export function saveDiaDVerifyLayout(prefs: DiaDVerifyLayoutPrefs): void {
  try {
    localStorage.setItem(DIA_D_VERIFY_LAYOUT_KEY, JSON.stringify(prefs));
  } catch {
    /* quota */
  }
}
