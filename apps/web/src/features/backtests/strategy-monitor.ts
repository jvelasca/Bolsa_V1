/**
 * Monitor Finalistas (MVP read-only) — precondición de auto-paper D.
 *
 * Une, sin backend nuevo:
 * - TOP por instrumento (`getInstrumentStrategyTop`)
 * - Cuentas paper con `strategyDefinitionId` + `labEvidence`
 * - Último ítem F3 con origen Finalistas (cola cliente)
 *
 * Soft cap: {@link STRATEGY_MONITOR_MAX} (= Lista AUTO / Fase C).
 *
 * **No ejecuta, no despliega, no unifica** caminos A/B/C/D.
 * UI: `strategy-monitor-panel.tsx` montado en Ayuda → Backtesting.
 *
 * @see PAPER_PATH_MONITOR
 * @see docs/engineering/research-lifecycle.md § Monitor Finalistas MVP
 * @see docs/engineering/backtesting-funnel-handoff-2026-07-29.md
 */

import type {
  InstrumentStrategyTopV1,
  InvestmentAccountDto,
} from '@bolsa/shared';
import { LIST_AUTO_MAX_INSTRUMENTS } from '@/features/backtests/backtest-list-auto';
import type { SupervisedQueueItem } from '@/stores/supervised-f3-queue-store';
import { resolveSupervisedQueueOrigin } from '@/stores/supervised-f3-queue-store';

export const STRATEGY_MONITOR_MAX = LIST_AUTO_MAX_INSTRUMENTS;

export type StrategyMonitorInstrument = {
  id: string;
  symbol: string;
  name?: string;
};

/** Fila de estado para un valor de la lista monitorizada. */
export type StrategyMonitorRow = {
  instrumentId: string;
  symbol: string;
  name?: string;
  timeframe: string;
  top: InstrumentStrategyTopV1 | null;
  topStatus: string | null;
  evidenceLevel: string | null;
  slot1Label: string | null;
  slot1Stars: number | null;
  slot1RunId: string | null;
  slotStrategyIds: string[];
  paperAccount: InvestmentAccountDto | null;
  lastPropose: SupervisedQueueItem | null;
};

/** Soft-cap lista de valores a monitorizar. */
export function sliceMonitorInstruments(
  instruments: StrategyMonitorInstrument[],
  max: number = STRATEGY_MONITOR_MAX,
): StrategyMonitorInstrument[] {
  return instruments.slice(0, Math.max(0, max));
}

/**
 * Cuenta desplegada vinculada a alguna estrategia del TOP (match por `strategyDefinitionId`).
 * Incluye DEMO (`simulated`) y `paper` legacy; ignora cerradas.
 * Premisa 2026-07-31: operativa hoy = DEMO simulated.
 */
export function findPaperForTopSlots(
  accounts: readonly InvestmentAccountDto[],
  strategyIds: readonly string[],
): InvestmentAccountDto | null {
  const idSet = new Set(strategyIds.filter(Boolean));
  if (idSet.size === 0) return null;
  const linked = accounts.filter(
    (a) =>
      (a.type === 'simulated' || a.type === 'paper') &&
      a.status !== 'closed' &&
      a.strategyDefinitionId,
  );
  // Prefer DEMO simulated over reserved paper broker type.
  const demo = linked.find(
    (a) => a.type === 'simulated' && idSet.has(a.strategyDefinitionId!),
  );
  if (demo) return demo;
  return linked.find((a) => idSet.has(a.strategyDefinitionId!)) ?? null;
}

/**
 * Primer ítem de la cola (orden reciente-first del store) con origen Finalistas
 * y símbolo coincidente (case-insensitive).
 */
export function findLastFinalistsPropose(
  queue: readonly SupervisedQueueItem[],
  symbol: string,
): SupervisedQueueItem | null {
  const sym = symbol.trim().toUpperCase();
  if (!sym) return null;
  for (const item of queue) {
    if (resolveSupervisedQueueOrigin(item) !== 'finalists') continue;
    const itemSym = (item.symbol ?? item.payload.symbol ?? '').trim().toUpperCase();
    if (itemSym === sym) return item;
  }
  return null;
}

/** Construye la fila de monitor a partir de TOP + accounts + cola F3. */
export function buildStrategyMonitorRow(opts: {
  instrument: StrategyMonitorInstrument;
  timeframe: string;
  top: InstrumentStrategyTopV1 | null | undefined;
  accounts: readonly InvestmentAccountDto[];
  queue: readonly SupervisedQueueItem[];
}): StrategyMonitorRow {
  const top = opts.top ?? null;
  const slots = top?.slots?.slice().sort((a, b) => a.rank - b.rank) ?? [];
  const slot1 = slots[0] ?? null;
  const slotStrategyIds = slots
    .map((s) => s.strategyDefinitionId)
    .filter((id): id is string => Boolean(id));

  return {
    instrumentId: opts.instrument.id,
    symbol: opts.instrument.symbol,
    name: opts.instrument.name,
    timeframe: top?.timeframe ?? opts.timeframe,
    top,
    topStatus: top?.status ?? null,
    evidenceLevel: top?.evidenceLevel ?? null,
    slot1Label: slot1?.label ?? null,
    slot1Stars: slot1?.stars ?? null,
    slot1RunId: slot1?.runId ?? null,
    slotStrategyIds,
    paperAccount: findPaperForTopSlots(opts.accounts, slotStrategyIds),
    lastPropose: findLastFinalistsPropose(opts.queue, opts.instrument.symbol),
  };
}

/**
 * ¿La query pide abrir el checklist paper?
 * Acepta `1` | `true` | `yes` (case-insensitive).
 */
export function isOpenAnalysisQuery(value: string | null | undefined): boolean {
  if (!value) return false;
  const v = value.trim().toLowerCase();
  return v === '1' || v === 'true' || v === 'yes';
}

/**
 * Deep-link Detalle + checklist («Análisis · paper»).
 * `openAnalysis=1` lo lee el hub (`preferOpenAnalysis`).
 */
export function strategyMonitorChecklistHref(
  instrumentId: string,
  runId: string,
  timeframe = '1d',
): string {
  const params = new URLSearchParams({
    tab: 'run',
    instrumentId,
    runId,
    focus: 'detail',
    openAnalysis: '1',
    timeframe,
  });
  return `/backtests?${params.toString()}`;
}
