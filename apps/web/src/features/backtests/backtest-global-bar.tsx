import type { ReactNode } from 'react';
import type { MovieTradeStats } from '@/features/backtests/backtest-movie-stats';
import type { TrailingYearReturns } from '@/features/backtests/backtest-buy-hold';
import type { FinalistHudBadge } from '@/features/backtests/instrument-top-match';
import { formatDateRangeDdMmYyyy } from '@/features/backtests/backtest-date-format';
import { BacktestFavoritesMenu } from '@/features/backtests/backtest-favorites-menu';
import { BacktestFutureStars } from '@/features/backtests/backtest-future-stars';
import {
  BACKTEST_GLOBAL_FIELD_OPTIONS,
  type BacktestGlobalFieldId,
} from '@/features/backtests/backtest-hud-prefs';
import { BacktestStatDonut } from '@/features/backtests/backtest-stat-donut';
import { formatPct, formatPrice } from '@/features/charts/chart-utils';
import { cn } from '@/lib/utils';

type Props = {
  symbol: string;
  strategyLabel: string;
  firstDate: string;
  lastDate: string;
  initialCash: number;
  finalEquity: number;
  totalReturnPct: number;
  maxDrawdownPct: number;
  tradeCount: number;
  excessPct: number | null;
  beatBuyHold: boolean | null;
  finalStats: MovieTradeStats;
  /** Últimos ~12m (estrategia / B&H / Δ); a la derecha, antes de acciones. */
  trailingYear?: TrailingYearReturns | null;
  /** Si el detalle es un Finalista del valor: ★ del TOP persistido. */
  finalistBadge?: FinalistHudBadge | null;
  actions?: ReactNode;
  favorites: BacktestGlobalFieldId[];
  onToggleFavorite: (id: BacktestGlobalFieldId) => void;
};

const DD_HELP =
  'Drawdown máximo (DD): la mayor caída del patrimonio desde un pico hasta el valle siguiente. Indica el peor tramo de pérdidas del periodo.';
const BH_HELP =
  'vs B&H (buy & hold): diferencia frente a haber comprado el valor al inicio y mantenido hasta el final. Positivo = la estrategia lo bató; negativo = lo hizo peor.';
const TRAILING_HELP =
  'Últimos ~12 meses (ventana móvil hasta el final del backtest): retorno de la estrategia, buy & hold del valor en la misma ventana, y diferencia (Δ). Requiere historial ≥ ~1 año.';

function Pill({
  children,
  tone = 'neutral',
  title,
}: {
  children: ReactNode;
  tone?: 'neutral' | 'good' | 'bad';
  title?: string;
}) {
  return (
    <span
      title={title}
      className={cn(
        'inline-flex items-center gap-0.5 rounded-md border px-2 py-0.5 text-xs tabular-nums',
        title && 'cursor-help',
        tone === 'good' && 'border-emerald-500/35 bg-emerald-500/10 text-emerald-300',
        tone === 'bad' && 'border-rose-500/35 bg-rose-500/10 text-rose-300',
        tone === 'neutral' && 'border-border/70 bg-background/50 text-muted-foreground',
      )}
    >
      {children}
    </span>
  );
}

/**
 * Franja Análisis global (Detalle). Métricas + acciones en la misma fila
 * (wrap solo si no caben). Resultado anual (~12m) a la derecha.
 */
export function BacktestGlobalBar({
  symbol,
  strategyLabel,
  firstDate,
  lastDate,
  initialCash,
  finalEquity,
  totalReturnPct,
  maxDrawdownPct,
  tradeCount,
  excessPct,
  beatBuyHold,
  finalStats,
  trailingYear = null,
  finalistBadge = null,
  actions,
  favorites,
  onToggleFavorite,
}: Props) {
  const won = totalReturnPct >= 0;
  const closed = finalStats.winners + finalStats.losers;
  const winPct = closed > 0 ? Math.round((finalStats.winners / closed) * 100) : 0;
  const moneyTotal = finalStats.moneyWon + finalStats.moneyLost;
  const moneyWinPct = moneyTotal > 0 ? Math.round((finalStats.moneyWon / moneyTotal) * 100) : 0;
  const show = (id: BacktestGlobalFieldId) => favorites.includes(id);
  const trailingWon = trailingYear != null && trailingYear.strategyPct >= 0;
  const trailingBeat = trailingYear != null && trailingYear.excessPct > 0;

  return (
    <div
      className={cn(
        'flex w-full min-w-0 flex-wrap items-center gap-x-3 gap-y-1.5 rounded-xl border px-3 py-2 shadow-sm',
        won
          ? 'border-emerald-500/30 bg-gradient-to-r from-emerald-500/10 via-card/80 to-card/40'
          : 'border-rose-500/30 bg-gradient-to-r from-rose-500/10 via-card/80 to-card/40',
      )}
    >
      <div className="min-w-0">
        <p className="flex items-center gap-0.5 text-[10px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
          <span title="Resultado final del periodo completo. (…) elige favoritos visibles.">
            Análisis global
          </span>
          <BacktestFavoritesMenu
            title="Análisis global"
            hint="Campos visibles en la barra de resultado final."
            options={BACKTEST_GLOBAL_FIELD_OPTIONS}
            favorites={favorites}
            onToggleFavorite={onToggleFavorite}
          />
        </p>
        {show('identity') && (
          <>
            <p className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-0.5 text-sm font-medium text-foreground">
              <span className="truncate">
                {symbol}
                <span className="mx-1.5 text-muted-foreground">·</span>
                {strategyLabel}
              </span>
              {finalistBadge && (
                <span className="inline-flex shrink-0 items-center gap-1.5">
                  <span
                    className="rounded border border-amber-500/35 bg-amber-500/10 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-200"
                    title={`Finalista #${finalistBadge.rank} · score ${finalistBadge.score}/100 · ${finalistBadge.source} · ${finalistBadge.evidenceLevel}`}
                  >
                    TOP #{finalistBadge.rank}
                  </span>
                  <BacktestFutureStars
                    stars={finalistBadge.stars}
                    capped={finalistBadge.starsCapped}
                    size="sm"
                    titlePrefix={`Finalista #${finalistBadge.rank}`}
                  />
                </span>
              )}
            </p>
            <p className="text-[11px] tabular-nums text-muted-foreground">
              {formatDateRangeDdMmYyyy(firstDate, lastDate)}
            </p>
          </>
        )}
        {!show('identity') && finalistBadge && (
          <div className="mt-0.5 flex items-center gap-1.5">
            <span className="rounded border border-amber-500/35 bg-amber-500/10 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-200">
              TOP #{finalistBadge.rank}
            </span>
            <BacktestFutureStars
              stars={finalistBadge.stars}
              capped={finalistBadge.starsCapped}
              size="sm"
              titlePrefix={`Finalista #${finalistBadge.rank}`}
            />
          </div>
        )}
      </div>

      {show('result') && (
        <>
          <div className="hidden h-9 w-px shrink-0 bg-border/70 sm:block" aria-hidden />
          <div className="min-w-[7rem]">
            <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
              Resultado
            </p>
            <p
              className={cn(
                'text-lg font-semibold leading-tight tabular-nums',
                won ? 'text-emerald-400' : 'text-rose-400',
              )}
            >
              {formatPct(totalReturnPct)}
            </p>
            {show('cashFlow') && (
              <p className="text-[11px] tabular-nums text-muted-foreground">
                {formatPrice(initialCash)} → {formatPrice(finalEquity)}
              </p>
            )}
          </div>
        </>
      )}

      {show('winLossDonut') && (
        <BacktestStatDonut
          positive={finalStats.winners}
          negative={finalStats.losers}
          positiveCaption={`${finalStats.winners} gan.`}
          negativeCaption={`${finalStats.losers} perd.`}
          centerLabel={closed > 0 ? `${winPct}%` : '—'}
          title={`${finalStats.winners} operaciones ganadoras (${winPct}%) · ${finalStats.losers} perdedoras`}
        />
      )}
      {show('moneyDonut') && (
        <BacktestStatDonut
          positive={finalStats.moneyWon}
          negative={finalStats.moneyLost}
          positiveCaption={`+${formatPrice(finalStats.moneyWon)}`}
          negativeCaption={`−${formatPrice(finalStats.moneyLost)}`}
          centerLabel={moneyTotal > 0 ? `${moneyWinPct}%` : '—'}
          title={`Dinero en ganadoras ${formatPrice(finalStats.moneyWon)} · en perdedoras ${formatPrice(finalStats.moneyLost)}`}
        />
      )}

      <div className="flex flex-wrap items-center gap-1.5">
        {show('drawdown') && (
          <Pill tone="bad" title={DD_HELP}>
            DD {formatPct(maxDrawdownPct)}
          </Pill>
        )}
        {show('vsBuyHold') && excessPct != null && (
          <Pill tone={beatBuyHold ? 'good' : 'bad'} title={BH_HELP}>
            vs B&H {formatPct(excessPct)}
          </Pill>
        )}
        {show('opsSummary') && (
          <Pill>
            {tradeCount} ops · {finalStats.closedCount} cerradas
          </Pill>
        )}
        {show('closedNet') && (
          <Pill tone={finalStats.closedNet >= 0 ? 'good' : 'bad'}>
            Neto ops {formatPrice(finalStats.closedNet)}
          </Pill>
        )}
      </div>

      <div className="ml-auto flex min-w-0 flex-wrap items-center justify-end gap-x-3 gap-y-1.5">
        {trailingYear && (
          <>
            <div className="hidden h-9 w-px shrink-0 bg-border/70 sm:block" aria-hidden />
            <div className="min-w-0 text-right" title={TRAILING_HELP}>
              <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
                Últimos 12m
              </p>
              <p
                className={cn(
                  'text-sm font-semibold leading-tight tabular-nums',
                  trailingWon ? 'text-emerald-400' : 'text-rose-400',
                )}
              >
                {formatPct(trailingYear.strategyPct)}
              </p>
              <p className="text-[11px] tabular-nums text-muted-foreground">
                B&H {formatPct(trailingYear.buyHoldPct)}
                <span className="mx-1 text-border">·</span>
                <span className={trailingBeat ? 'text-emerald-400' : 'text-rose-400'}>
                  Δ {formatPct(trailingYear.excessPct)}
                </span>
              </p>
            </div>
          </>
        )}
        {actions && (
          <div className="flex min-w-0 flex-wrap items-center justify-end gap-1.5">{actions}</div>
        )}
      </div>
    </div>
  );
}
