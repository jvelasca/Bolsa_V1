/**
 * Lista AUTO: bucle externo del ciclo completo (1 valor) sobre una watchlist.
 *
 * Entrada: Universo modo **Lista** + Play con `fullCycleOnPlay` ON.
 * Átomo: mismo embudo Coach→Lab→Coach²→Finalistas (`backtest-assistant-full-cycle.ts`).
 * Soft cap: {@link LIST_AUTO_MAX_INSTRUMENTS} (alineado con Fase C «Probar lista»).
 *
 * Controles de campaña:
 * - **Pausa:** el ticker en curso termina; no se arranca el siguiente hasta Reanudar.
 *   La pausa **persiste** en localStorage (`backtest-list-auto-persist.ts`) y se
 *   restaura al reiniciar la app (Reanudar manual; no auto-arranca).
 * - **Stop:** aborta ya (cancela cola + in-flight); conserva filas ya settled en el tablero.
 * - **Frescura:** si Finalistas active tienen stamp de datos igual → `skip_fresh` (omitido).
 *
 * **No es Fase C:** «Probar lista» = 1 estrategia × N valores → ranking
 * (`backtest-batch-run.ts`). Lista AUTO = N embudos secuenciales.
 *
 * Orquestación: `backtests-page.tsx` (`listAutoRef`, `queueListAutoTicker`,
 * `settleFullCycle`). Cancel: Stop / ↻ del Asistente (`abortListAutoCampaign`).
 *
 * @see docs/engineering/list-auto-ops-2026-07-29.md
 * @see docs/engineering/session-handoff-2026-07-30.md
 * @see docs/engineering/research-lifecycle.md § Lista AUTO
 */

/** Soft cap IBEX-sized; compartido con Probar lista / Monitor. */
export const LIST_AUTO_MAX_INSTRUMENTS = 40;

/** Motivo de cierre de un ciclo 1-valor dentro de la campaña. */
export type FullCycleSettleReason =
  | 'saved'
  | 'skip_lab'
  | 'skip_finalists'
  /** Datos de entrada iguales al stamp de Finalistas → no re-analizar. */
  | 'skip_fresh';

/** Estado mutable de la campaña (fuente de verdad en ref de página). */
export type ListAutoCampaign = {
  listId: string;
  instrumentIds: string[];
  index: number;
  aborted: boolean;
  /** Tras settle del actual: no encolar siguiente hasta resume. */
  paused: boolean;
  /** Ignora skip_fresh en tickers restantes. */
  forceRescan: boolean;
};

/** Recorta la cola al soft cap. */
export function sliceListAutoInstrumentIds(
  ids: string[],
  max: number = LIST_AUTO_MAX_INSTRUMENTS,
): string[] {
  return ids.slice(0, Math.max(0, max));
}

/**
 * Consentimiento explícito cuando la lista supera el soft cap (S&P 500, FTSE…).
 * Sin diálogo si `total <= max`. `confirmFn` inyectable en tests.
 */
export function confirmListAutoOverCap(
  total: number,
  max: number = LIST_AUTO_MAX_INSTRUMENTS,
  confirmFn: (message: string) => boolean = (msg) => window.confirm(msg),
): boolean {
  if (total <= max) return true;
  return confirmFn(
    `La lista tiene ${total} valores. Lista AUTO usará como máximo ${max} (los primeros de la lista).\n\n` +
      `No lanza ${total} embudos. ¿Continuar?`,
  );
}

/** Aviso UI cuando la cola se truncará. */
export function listAutoOverCapWarning(
  total: number,
  max: number = LIST_AUTO_MAX_INSTRUMENTS,
): string | null {
  if (total <= max) return null;
  return `La lista tiene ${total} valores · Play usará los primeros ${max} (confirmación al lanzar).`;
}

/** True si el ticker ya tiene Finalistas (TOP con slots). */
export function instrumentHasFinalistSlots(top: {
  slots?: { rank?: number }[] | null;
} | null | undefined): boolean {
  return (top?.slots?.length ?? 0) > 0;
}

/**
 * Filtro opcional: deja solo IDs sin Finalistas TOP.
 * Fallo de red → se incluye el id (mejor analizar de más que saltar en silencio).
 */
export async function filterListAutoIdsWithoutFinalists(
  ids: string[],
  fetchTop: (instrumentId: string) => Promise<{ data: { slots?: unknown[] | null } | null }>,
): Promise<string[]> {
  const results = await Promise.all(
    ids.map(async (id) => {
      try {
        const res = await fetchTop(id);
        return instrumentHasFinalistSlots(res.data) ? null : id;
      } catch {
        return id;
      }
    }),
  );
  return results.filter((id): id is string => Boolean(id));
}

/** Crea campaña con cola ya acotada; `index` inicia en 0. */
export function createListAutoCampaign(opts: {
  listId: string;
  instrumentIds: string[];
  max?: number;
  forceRescan?: boolean;
}): ListAutoCampaign {
  return {
    listId: opts.listId,
    instrumentIds: sliceListAutoInstrumentIds(opts.instrumentIds, opts.max),
    index: 0,
    aborted: false,
    paused: false,
    forceRescan: Boolean(opts.forceRescan),
  };
}

/** `true` si `index` ya pasó el último ticker. */
export function isListAutoComplete(campaign: ListAutoCampaign): boolean {
  return campaign.index >= campaign.instrumentIds.length;
}

/**
 * Tras settle de un ticker: índice del siguiente, o `null` si abortada / fin.
 * No muta la campaña (la UI decide). Preferir {@link advanceListAutoAfterSettle}.
 */
export function nextListAutoIndex(campaign: ListAutoCampaign): number | null {
  if (campaign.aborted) return null;
  const next = campaign.index + 1;
  if (next >= campaign.instrumentIds.length) return null;
  return next;
}

export type ListAutoAdvanceResult = 'done' | 'next' | 'aborted' | 'paused';

/**
 * Avanza la campaña tras cerrar el ciclo del ticker actual.
 * Si `paused`, mueve `index` al siguiente pero no lo arranca (`paused`).
 */
export function advanceListAutoAfterSettle(
  campaign: ListAutoCampaign,
): ListAutoAdvanceResult {
  if (campaign.aborted) return 'aborted';
  const next = nextListAutoIndex(campaign);
  if (next == null) {
    campaign.index = campaign.instrumentIds.length;
    return 'done';
  }
  campaign.index = next;
  if (campaign.paused) return 'paused';
  return 'next';
}

export function pauseListAutoCampaign(campaign: ListAutoCampaign): void {
  campaign.paused = true;
}

export function resumeListAutoCampaign(campaign: ListAutoCampaign): void {
  campaign.paused = false;
}

export function stopListAutoCampaign(campaign: ListAutoCampaign): void {
  campaign.aborted = true;
  campaign.paused = false;
}

/** Etiqueta de progreso en el rail (`Lista AUTO 3/35 · SAN`). */
export function listAutoProgressLabel(opts: {
  index: number;
  total: number;
  symbol: string;
}): string {
  return `Lista AUTO ${opts.index + 1}/${opts.total} · ${opts.symbol}`;
}

/**
 * Resumen compacto para la barra de estado Trading / badge nav.
 * Ej.: `Lista AUTO 3/19 · SAN · Lab…` · `Lista AUTO 3/19 · SAN · pausa`
 */
export function formatListAutoStatusBarSummary(opts: {
  index: number;
  total: number;
  symbol: string;
  paused?: boolean;
  detail?: string | null;
  listName?: string | null;
}): string {
  const base = listAutoProgressLabel({
    index: Math.max(0, opts.index),
    total: Math.max(1, opts.total),
    symbol: opts.symbol.trim() || '…',
  });
  if (opts.paused) return `${base} · pausa`;
  const phase = shortenListAutoPhase(opts.detail);
  const listBit =
    opts.listName && opts.listName.trim() && opts.listName.trim() !== 'IBEX 35'
      ? ` · ${opts.listName.trim()}`
      : '';
  return phase ? `${base} · ${phase}${listBit}` : `${base}${listBit}`;
}

/** Extrae fase corta del mensaje del rail (evita repetir «Lista AUTO…»). */
export function shortenListAutoPhase(detail: string | null | undefined): string | null {
  if (!detail?.trim()) return null;
  let s = detail.trim();
  s = s.replace(/^Lista AUTO[^:]*:\s*/i, '');
  s = s.replace(/^Lista AUTO\s+\d+\/\d+\s*·\s*\S+\s*[:·]?\s*/i, '');
  // Primera cláusula útil
  const cut = s.split(/[·|]/)[0]?.trim() ?? s;
  const short = cut.length > 36 ? `${cut.slice(0, 34)}…` : cut;
  return short || null;
}

/** Mensaje al completar la campaña. */
export function listAutoDoneStatus(total: number): string {
  return `Lista AUTO ✓ ${total} valor(es). Finalistas por ticker en Mis estrategias / Finalistas.`;
}

export function listAutoPausedStatus(opts: {
  index: number;
  total: number;
  symbol: string;
}): string {
  return `${listAutoProgressLabel(opts)} · en pausa. Reanudar para continuar.`;
}

/** Título Play: lista AUTO vs ciclo 1 valor vs paso a paso. */
export function listAutoPlayTitle(opts: {
  fullCycleOnPlay: boolean;
  listMode: boolean;
}): string {
  if (!opts.fullCycleOnPlay) return 'Play: ejecutar siguiente paso';
  if (opts.listMode) {
    return `Play: lista AUTO (ciclo completo × cada valor, máx. ${LIST_AUTO_MAX_INSTRUMENTS})`;
  }
  return 'Play: ciclo completo (Coach → Lab → Coach² → Finalistas)';
}

/**
 * Copy del panel Lista (modo Universo=Lista).
 * Play ≠ «Probar lista»: no pide elegir una estrategia.
 */
export function listAutoUniverseHint(): string {
  return (
    'Play lanza el embudo completo por cada valor: todas las genéricas ∪ Finalistas de ese ticker. ' +
    'No hace falta seleccionar una estrategia. Clic en un miembro o fila del tablero → pestaña Valor. ' +
    'Pausa / Stop gestionan la campaña; si los datos no cambiaron, se omite el valor (frescura).'
  );
}

/** Resumen corto para el título del wizard en modo lista. */
export function listModeWizardTitle(fullCycleOnPlay: boolean): string {
  return fullCycleOnPlay
    ? 'Lista AUTO · Play (sin elegir estrategia)'
    : 'Lista · activa ciclo completo para Lista AUTO';
}

/** ¿Play debe arrancar Lista AUTO en lugar del ciclo/paso de un valor? */
export function shouldStartListAuto(opts: {
  universeMode: 'single' | 'list';
  fullCycleOnPlay: boolean;
  listId: string | null | undefined;
  instrumentCount: number;
}): boolean {
  return (
    opts.universeMode === 'list' &&
    opts.fullCycleOnPlay &&
    Boolean(opts.listId) &&
    opts.instrumentCount > 0
  );
}
