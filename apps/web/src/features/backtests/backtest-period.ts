/** Period presets for the “Probar estrategia” wizard (Phase A) + DÍA D (as-of). */

export type PeriodPreset = 'all' | '1y' | '3y' | '5y' | 'custom';

/** Default for IA / research: max synced history (better than a single year). */
export const DEFAULT_PERIOD_PRESET: PeriodPreset = 'all';

export const PERIOD_PRESET_OPTIONS: { value: PeriodPreset; label: string }[] = [
  { value: 'all', label: 'Todo el historial (recomendado IA)' },
  { value: '5y', label: 'Últimos 5 años' },
  { value: '3y', label: 'Últimos 3 años' },
  { value: '1y', label: 'Último año (corto — solo humo rápido)' },
  { value: 'custom', label: 'Personalizado' },
];

export function isoDateUTC(d: Date): string {
  return d.toISOString().slice(0, 10);
}

export function todayIsoDate(): string {
  return isoDateUTC(new Date());
}

/** Fecha D efectiva: diaD válida, o hoy. Nunca futura. */
export function effectiveDiaD(diaD: string | null | undefined): string {
  const today = todayIsoDate();
  const raw = typeof diaD === 'string' ? diaD.trim() : '';
  if (!/^\d{4}-\d{2}-\d{2}$/.test(raw)) return today;
  return raw > today ? today : raw;
}

export function isDiaDInPast(diaD: string | null | undefined): boolean {
  return effectiveDiaD(diaD) < todayIsoDate();
}

export type ResolvedBacktestWindow = {
  dateFrom?: string;
  dateTo?: string;
  /** Used when no date bounds (full history). */
  limit?: number;
};

/**
 * Map UI period → API dateFrom/dateTo or bar limit.
 * `asOfDate` = DÍA D (hoy simulado). Presets 1y/3y/5y se anclan a D, no al calendario real.
 */
export function resolveBacktestWindow(
  preset: PeriodPreset,
  customFrom: string,
  customTo: string,
  asOfDate?: string | null,
): ResolvedBacktestWindow {
  const asOf = effectiveDiaD(asOfDate);
  const today = todayIsoDate();
  const cutFuture = asOf < today;

  if (preset === 'all') {
    if (cutFuture) return { dateTo: asOf, limit: 10_000 };
    return { limit: 10_000 };
  }

  if (preset === 'custom') {
    const to =
      customTo && customTo <= asOf
        ? customTo
        : customTo
          ? asOf
          : cutFuture
            ? asOf
            : undefined;
    return {
      ...(customFrom ? { dateFrom: customFrom } : {}),
      ...(to ? { dateTo: to } : {}),
      limit: 10_000,
    };
  }

  const asOfDateObj = new Date(`${asOf}T12:00:00.000Z`);
  const years = preset === '1y' ? 1 : preset === '3y' ? 3 : 5;
  asOfDateObj.setUTCFullYear(asOfDateObj.getUTCFullYear() - years);
  return {
    dateFrom: isoDateUTC(asOfDateObj),
    dateTo: asOf,
    limit: 10_000,
  };
}
