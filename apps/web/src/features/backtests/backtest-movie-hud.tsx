import type { MovieTradeStats } from "@/features/backtests/backtest-movie-stats";
import { formatDateDdMmYyyy } from "@/features/backtests/backtest-date-format";
import { BacktestFavoritesMenu } from "@/features/backtests/backtest-favorites-menu";
import {
  BACKTEST_TEMPORAL_FIELD_OPTIONS,
  type BacktestTemporalFieldId,
} from "@/features/backtests/backtest-hud-prefs";
import { BacktestStatDonut } from "@/features/backtests/backtest-stat-donut";
import { formatPct, formatPrice } from "@/features/charts/chart-utils";
import { cn } from "@/lib/utils";

type Props = {
  cursorTimestamp: string | null;
  barIndex: number;
  barTotal: number;
  playing: boolean;
  atEnd: boolean;
  balance: number | null;
  returnPct: number | null;
  stats: MovieTradeStats;
  totalOps: number;
  /** Close of the bar under the replay cursor — for open-position mark. */
  markPrice?: number | null;
  /** Compact single-row strip (next to transport controls). */
  inline?: boolean;
  favorites: BacktestTemporalFieldId[];
  onToggleFavorite: (id: BacktestTemporalFieldId) => void;
};

function StatChip({
  label,
  value,
  tone = "neutral",
}: {
  label: string;
  value: string;
  tone?: "neutral" | "good" | "bad" | "live";
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-xs",
        tone === "good" &&
          "border-emerald-500/30 bg-emerald-500/10 text-emerald-300",
        tone === "bad" && "border-rose-500/30 bg-rose-500/10 text-rose-300",
        tone === "live" && "border-sky-500/30 bg-sky-500/10 text-sky-300",
        tone === "neutral" &&
          "border-border/60 bg-muted/30 text-muted-foreground",
      )}
    >
      <span className="font-normal opacity-90">{label}</span>
      <span className="font-normal tabular-nums text-foreground">{value}</span>
    </span>
  );
}

export function BacktestMovieHud({
  cursorTimestamp,
  barIndex,
  barTotal,
  playing,
  atEnd,
  balance,
  returnPct,
  stats,
  totalOps,
  markPrice = null,
  inline = false,
  favorites,
  onToggleFavorite,
}: Props) {
  const live = playing || !atEnd;
  const closed = stats.winners + stats.losers;
  const winPct = closed > 0 ? Math.round((stats.winners / closed) * 100) : 0;
  const show = (id: BacktestTemporalFieldId) => favorites.includes(id);

  const lastIsOpen = Boolean(stats.openEntry);
  const unrealizedPct =
    lastIsOpen &&
    stats.openEntry &&
    markPrice != null &&
    stats.openEntry.price > 0
      ? ((markPrice - stats.openEntry.price) / stats.openEntry.price) * 100
      : null;
  const unrealizedPnl =
    lastIsOpen && stats.openEntry && markPrice != null
      ? (markPrice - stats.openEntry.price) * stats.openEntry.quantity
      : null;

  const positionChip =
    lastIsOpen && stats.openEntry ? (
      <StatChip
        label="Posición"
        value={
          unrealizedPct == null || unrealizedPnl == null
            ? `Comprado @ ${formatPrice(stats.openEntry.price)}`
            : `Comprado @ ${formatPrice(stats.openEntry.price)} · ${unrealizedPnl >= 0 ? "+" : ""}${formatPrice(unrealizedPnl)} (${unrealizedPct >= 0 ? "+" : ""}${unrealizedPct.toFixed(1)}%)`
        }
        tone={
          unrealizedPct == null ? "live" : unrealizedPct >= 0 ? "good" : "bad"
        }
      />
    ) : (
      <StatChip label="Posición" value="Sin posición" />
    );

  const lastChip =
    !lastIsOpen && stats.lastClosedPnl != null ? (
      <StatChip
        label="Última"
        value={`Cerrada ${formatPrice(stats.lastClosedPnl)}`}
        tone={stats.lastClosedPnl >= 0 ? "good" : "bad"}
      />
    ) : null;

  const chips = (
    <>
      {show("position") && positionChip}
      {show("opsCount") && (
        <StatChip label="Efectuadas" value={`${stats.opsCount}/${totalOps}`} />
      )}
      {show("closedCount") && (
        <StatChip label="Cerradas" value={String(stats.closedCount)} />
      )}
      {show("closedNet") && (
        <StatChip
          label="Neto"
          value={formatPrice(stats.closedNet)}
          tone={stats.closedNet >= 0 ? "good" : "bad"}
        />
      )}
      {show("lastClosed") && lastChip}
    </>
  );

  const winLossDonut = show("winLossDonut") ? (
    <BacktestStatDonut
      positive={stats.winners}
      negative={stats.losers}
      positiveCaption={`${stats.winners} gan.`}
      negativeCaption={`${stats.losers} perd.`}
      centerLabel={closed > 0 ? `${winPct}%` : "—"}
      title={`${stats.winners} operaciones ganadoras (${winPct}%) · ${stats.losers} perdedoras (${closed > 0 ? 100 - winPct : 0}%)`}
    />
  ) : null;

  const moneyTotal = stats.moneyWon + stats.moneyLost;
  const moneyWinPct =
    moneyTotal > 0 ? Math.round((stats.moneyWon / moneyTotal) * 100) : 0;
  const moneyDonut = show("moneyDonut") ? (
    <BacktestStatDonut
      positive={stats.moneyWon}
      negative={stats.moneyLost}
      positiveCaption={`+${formatPrice(stats.moneyWon)}`}
      negativeCaption={`−${formatPrice(stats.moneyLost)}`}
      centerLabel={moneyTotal > 0 ? `${moneyWinPct}%` : "—"}
      title={`Dinero en ganadoras ${formatPrice(stats.moneyWon)} (${moneyWinPct}%) · en perdedoras ${formatPrice(stats.moneyLost)} (${moneyTotal > 0 ? 100 - moneyWinPct : 0}%)`}
    />
  ) : null;

  const menu = (
    <BacktestFavoritesMenu
      title="Datos temporales"
      hint="Campos visibles durante la reproducción / barrido."
      options={BACKTEST_TEMPORAL_FIELD_OPTIONS}
      favorites={favorites}
      onToggleFavorite={onToggleFavorite}
    />
  );

  if (inline) {
    return (
      <div className="flex min-w-0 flex-1 flex-wrap items-center gap-x-2.5 gap-y-1">
        {show("date") && (
          <div className="min-w-[7.5rem]">
            <p
              className="flex items-center gap-0.5 text-[9px] font-semibold uppercase tracking-[0.12em] text-muted-foreground"
              title="Estado en la fecha del barrido. El panel flotante del gráfico detalla la vela y la posición. (…) = favoritos."
            >
              {playing ? "En vivo" : atEnd ? "Fin del barrido" : "Cursor"}
              <span className="ml-1 font-normal normal-case tracking-normal tabular-nums opacity-80">
                {barIndex}/{barTotal}
              </span>
              {menu}
            </p>
            <p className="text-base font-semibold leading-tight tabular-nums tracking-tight text-foreground">
              {formatDateDdMmYyyy(cursorTimestamp)}
            </p>
          </div>
        )}

        {!show("date") && <div className="shrink-0">{menu}</div>}

        {show("balance") && (
          <>
            <div className="h-8 w-px shrink-0 bg-border/70" aria-hidden />
            <div className="min-w-[5.5rem]">
              <p className="text-[9px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
                Balance
              </p>
              <p className="text-sm font-semibold leading-tight tabular-nums text-foreground">
                {balance != null ? formatPrice(balance) : "—"}
                {returnPct != null && (
                  <span
                    className={cn(
                      "ml-1.5 text-xs",
                      returnPct >= 0 ? "text-emerald-400" : "text-rose-400",
                    )}
                  >
                    {formatPct(returnPct)}
                  </span>
                )}
              </p>
            </div>
          </>
        )}

        {winLossDonut}
        {moneyDonut}

        <div className="flex min-w-0 flex-wrap items-center gap-1">{chips}</div>
      </div>
    );
  }

  return (
    <div
      className={cn(
        "rounded-xl border px-3 py-2 shadow-sm",
        live
          ? "border-sky-500/35 bg-gradient-to-br from-sky-500/10 via-card/80 to-emerald-500/5"
          : "border-border/70 bg-card/70",
      )}
    >
      <div className="flex flex-wrap items-center gap-3">
        <div className="min-w-0">
          <p className="flex items-center gap-0.5 text-[10px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
            {playing
              ? "Película en vivo"
              : atEnd
                ? "Resultado completo"
                : "Barrido"}
            {menu}
          </p>
          {show("date") && (
            <p className="text-lg font-semibold tabular-nums text-foreground">
              {formatDateDdMmYyyy(cursorTimestamp)}
            </p>
          )}
        </div>
        {winLossDonut}
        {moneyDonut}
        <div className="flex flex-wrap gap-1">{chips}</div>
      </div>
    </div>
  );
}
