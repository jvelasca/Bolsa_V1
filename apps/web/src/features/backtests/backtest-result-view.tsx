/**
 * Vista Detalle de un backtest (pestaña Resultado → Detalle).
 *
 * Layout 2026-07-28: scroll vertical; Análisis global + Datos temporales
 * a ancho completo (apilados); tabla de operaciones en `text-xs`.
 */

import type { ReactNode } from "react";
import {
  startTransition,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import type {
  BacktestEquityPointDto,
  BacktestRunDetailDto,
  BacktestTradeDto,
  DrawingReplayMarkerDto,
  OhlcvBarDto,
  ResearchTrialDto,
} from "@bolsa/shared";
import { BACKTEST_STRATEGIES } from "@bolsa/shared";
import {
  buyHoldReturnFromBars,
  excessReturnPct,
  trailingYearReturns,
} from "@/features/backtests/backtest-buy-hold";
import { BacktestEquityChart } from "@/features/backtests/backtest-equity-chart";
import { BacktestReplayChart } from "@/features/backtests/backtest-replay-chart";
import {
  formatDateDdMmYyyy,
  formatDateRangeDdMmYyyy,
} from "@/features/backtests/backtest-date-format";
import { BacktestGlobalBar } from "@/features/backtests/backtest-global-bar";
import type { FinalistHudBadge } from "@/features/backtests/instrument-top-match";
import { BacktestMovieHud } from "@/features/backtests/backtest-movie-hud";
import { computeMovieTradeStats } from "@/features/backtests/backtest-movie-stats";
import { BacktestPaperChecklist } from "@/features/backtests/backtest-paper-checklist";
import { useBacktestHudPrefs } from "@/features/backtests/use-backtest-hud-prefs";
import {
  clampBottomEquityHeightPct,
  clampChartHeightPct,
  clampEquityWidthPct,
  loadBacktestSplitLayout,
  pxToPct,
  saveBacktestSplitLayout,
} from "@/features/backtests/backtest-split-layout";
import { ResearchTrialResultBlock } from "@/features/research/research-trial-result-block";
import { ResearchLabEvidenceSummary } from "@/features/research/research-lab-evidence-summary";
import { formatPct, formatPrice } from "@/features/charts/chart-utils";
import { PanelResizeHandle } from "@/components/layout/panel-resize-handle";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useMediaQuery } from "@/lib/use-media-query";
import { Link } from "react-router-dom";
import {
  VER_EN_ASESOR_LABEL,
  asesorHistoryHref,
} from "@/features/confirm/daily-nav";

type Props = {
  detail: BacktestRunDetailDto;
  bars?: OhlcvBarDto[];
  barsLoading?: boolean;
  barsError?: boolean;
  equityCurve: BacktestEquityPointDto[];
  focusTimestamp: string | null;
  focusedTrade: BacktestTradeDto | null;
  onSelectTrade: (timestamp: string) => void;
  onJumpToTrade: (timestamp: string) => void;
  displayTrialId?: string | null;
  displayMetrics?: Record<string, number | string | null> | null;
  linkedTrial?: ResearchTrialDto | null;
  drawingMarkers?: DrawingReplayMarkerDto[];
  actions?: ReactNode;
  footerNote?: ReactNode;
  /** Fill parent and enable inner splitters (desktop hub). */
  fillHeight?: boolean;
  /** ★ del Finalista si este detalle pertenece al TOP del valor. */
  finalistBadge?: FinalistHudBadge | null;
  /** P4 — deploy paper after checklist. */
  onDeployPaper?: (payload: {
    labEvidence: import("@bolsa/shared").PaperLabEvidenceSnapshot;
  }) => void;
  deployingPaper?: boolean;
  /** Abrir «Análisis · paper · baseline» al llegar desde Finalistas. */
  preferOpenAnalysis?: boolean;
};

function equityAtOrBefore(
  curve: BacktestEquityPointDto[],
  timestamp: string | null,
): BacktestEquityPointDto | null {
  if (!timestamp || curve.length === 0) return null;
  for (let i = curve.length - 1; i >= 0; i -= 1) {
    const point = curve[i]!;
    if (point.timestamp <= timestamp) return point;
  }
  return curve[0] ?? null;
}

export function BacktestResultView({
  detail,
  bars,
  barsLoading,
  barsError,
  equityCurve,
  focusTimestamp,
  onSelectTrade,
  onJumpToTrade,
  displayTrialId,
  displayMetrics,
  linkedTrial,
  drawingMarkers = [],
  actions,
  footerNote,
  fillHeight = false,
  finalistBadge = null,
  onDeployPaper,
  deployingPaper = false,
  preferOpenAnalysis = false,
}: Props) {
  const isWideBottom = useMediaQuery("(min-width: 720px)");
  const [analysisOpen, setAnalysisOpen] = useState(preferOpenAnalysis);
  const {
    prefs: hudPrefs,
    toggleGlobalFavorite,
    toggleTemporalFavorite,
    toggleCursorFavorite,
    setCursorPanelPos,
  } = useBacktestHudPrefs();
  const strategyLabel =
    BACKTEST_STRATEGIES[detail.strategyType as keyof typeof BACKTEST_STRATEGIES]
      ?.label ?? detail.strategyType;

  useEffect(() => {
    if (preferOpenAnalysis) setAnalysisOpen(true);
  }, [preferOpenAnalysis, detail.id]);

  const metricBuyHold = (() => {
    const raw =
      displayMetrics?.buyHoldReturnPct ??
      linkedTrial?.isMetrics?.buyHoldReturnPct;
    return typeof raw === "number" && Number.isFinite(raw) ? raw : null;
  })();
  const buyHoldPct =
    metricBuyHold ??
    buyHoldReturnFromBars(bars, detail.firstDate, detail.lastDate);
  const excessPct =
    (typeof displayMetrics?.excessReturnPct === "number"
      ? displayMetrics.excessReturnPct
      : null) ?? excessReturnPct(detail.totalReturnPct, buyHoldPct);
  const beatBuyHold = excessPct != null ? excessPct > 0 : null;
  const trailingYear = useMemo(
    () => trailingYearReturns(equityCurve, bars),
    [equityCurve, bars],
  );

  const stored = loadBacktestSplitLayout();
  const [chartPct, setChartPct] = useState(stored.chartHeightPct);
  const [equityPct, setEquityPct] = useState(stored.equityWidthPct);
  const [bottomEquityPct, setBottomEquityPct] = useState(
    stored.bottomEquityHeightPct,
  );
  const pendingChart = useRef(stored.chartHeightPct);
  const pendingEquity = useRef(stored.equityWidthPct);
  const pendingBottomEquity = useRef(stored.bottomEquityHeightPct);
  const bodyRef = useRef<HTMLDivElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const tradesListRef = useRef<HTMLDivElement>(null);
  const lastAutoFocusRef = useRef<string | null>(null);

  const [replayCursor, setReplayCursor] = useState<string | null>(null);
  const [replayPlaying, setReplayPlaying] = useState(false);
  const [replayAtEnd, setReplayAtEnd] = useState(true);
  const [replayBarIndex, setReplayBarIndex] = useState(0);
  const [replayBarTotal, setReplayBarTotal] = useState(0);

  const handleReplayCursorChange = useCallback(
    (
      timestamp: string | null,
      meta: {
        playing: boolean;
        atEnd: boolean;
        barIndex: number;
        barTotal: number;
      },
    ) => {
      // Low-priority UI sync so the candle chart stays smooth while playing.
      startTransition(() => {
        setReplayCursor(timestamp);
        setReplayPlaying(meta.playing);
        setReplayAtEnd(meta.atEnd);
        setReplayBarIndex(meta.barIndex);
        setReplayBarTotal(meta.barTotal);
      });
    },
    [],
  );

  const revealedTrades = useMemo(() => {
    if (replayCursor == null) return detail.trades;
    return detail.trades.filter((trade) => trade.timestamp <= replayCursor);
  }, [detail.trades, replayCursor]);

  const latestRevealedTrade = revealedTrades[revealedTrades.length - 1] ?? null;

  const liveEquityPoint = useMemo(
    () => equityAtOrBefore(equityCurve, replayCursor),
    [equityCurve, replayCursor],
  );
  const liveEquity = liveEquityPoint?.equity ?? null;
  const liveReturnPct =
    liveEquity != null && detail.initialCash > 0
      ? ((liveEquity - detail.initialCash) / detail.initialCash) * 100
      : null;
  const markPrice = useMemo(() => {
    if (!bars?.length || !replayCursor) {
      return bars && bars.length > 0 ? bars[bars.length - 1]!.close : null;
    }
    for (let i = bars.length - 1; i >= 0; i -= 1) {
      if (bars[i]!.timestamp <= replayCursor) return bars[i]!.close;
    }
    return bars[0]?.close ?? null;
  }, [bars, replayCursor]);
  const movieStats = useMemo(
    () => computeMovieTradeStats(detail.trades, replayCursor),
    [detail.trades, replayCursor],
  );
  const finalMovieStats = useMemo(
    () => computeMovieTradeStats(detail.trades, null),
    [detail.trades],
  );

  // Highlight + scroll the latest revealed op (also while playing).
  useEffect(() => {
    if (!latestRevealedTrade) return;
    if (replayAtEnd && !replayPlaying) return;
    if (lastAutoFocusRef.current === latestRevealedTrade.timestamp) return;
    lastAutoFocusRef.current = latestRevealedTrade.timestamp;
    onSelectTrade(latestRevealedTrade.timestamp);
  }, [latestRevealedTrade, onSelectTrade, replayAtEnd, replayPlaying]);

  useEffect(() => {
    if (!latestRevealedTrade) return;
    if (replayAtEnd && !replayPlaying) return;
    const row = tradesListRef.current?.querySelector<HTMLElement>(
      `[data-trade-id="${latestRevealedTrade.id}"]`,
    );
    row?.scrollIntoView({
      block: "nearest",
      behavior: replayPlaying ? "auto" : "smooth",
    });
  }, [latestRevealedTrade, replayAtEnd, replayPlaying]);

  useEffect(() => {
    lastAutoFocusRef.current = null;
    setReplayCursor(null);
    setReplayPlaying(false);
    setReplayAtEnd(false);
  }, [detail.id]);

  useEffect(() => {
    pendingChart.current = chartPct;
  }, [chartPct]);
  useEffect(() => {
    pendingEquity.current = equityPct;
  }, [equityPct]);
  useEffect(() => {
    pendingBottomEquity.current = bottomEquityPct;
  }, [bottomEquityPct]);

  const persist = useCallback(
    (
      patch: Partial<{
        chartHeightPct: number;
        equityWidthPct: number;
        bottomEquityHeightPct: number;
      }>,
    ) => {
      const current = loadBacktestSplitLayout();
      saveBacktestSplitLayout({ ...current, ...patch });
    },
    [],
  );

  const adjustChartHeight = useCallback((deltaPx: number) => {
    const height = bodyRef.current?.getBoundingClientRect().height ?? 0;
    if (height <= 0) return;
    const next = clampChartHeightPct(
      pendingChart.current + pxToPct(deltaPx, height),
    );
    pendingChart.current = next;
    setChartPct(next);
  }, []);

  const adjustEquityWidth = useCallback((deltaPx: number) => {
    const width = bottomRef.current?.getBoundingClientRect().width ?? 0;
    if (width <= 0) return;
    const next = clampEquityWidthPct(
      pendingEquity.current + pxToPct(deltaPx, width),
    );
    pendingEquity.current = next;
    setEquityPct(next);
  }, []);

  const adjustBottomEquityHeight = useCallback((deltaPx: number) => {
    const height = bottomRef.current?.getBoundingClientRect().height ?? 0;
    if (height <= 0) return;
    const next = clampBottomEquityHeightPct(
      pendingBottomEquity.current + pxToPct(deltaPx, height),
    );
    pendingBottomEquity.current = next;
    setBottomEquityPct(next);
  }, []);

  const globalBar = (
    <BacktestGlobalBar
      symbol={detail.symbol}
      strategyLabel={strategyLabel}
      firstDate={detail.firstDate}
      lastDate={detail.lastDate}
      initialCash={detail.initialCash}
      finalEquity={detail.finalEquity}
      totalReturnPct={detail.totalReturnPct}
      maxDrawdownPct={detail.maxDrawdownPct}
      tradeCount={detail.tradeCount}
      excessPct={excessPct}
      beatBuyHold={beatBuyHold}
      finalStats={finalMovieStats}
      trailingYear={trailingYear}
      finalistBadge={finalistBadge}
      actions={actions}
      favorites={hudPrefs.globalFavorites}
      onToggleFavorite={toggleGlobalFavorite}
    />
  );

  const chartBlock = (
    <section
      id="backtest-replay"
      className="flex h-full min-h-0 w-full min-w-0 flex-1 flex-col"
    >
      {barsError && !(bars && bars.length > 0) && (
        <p className="text-sm text-destructive">
          No se pudo cargar el histórico del valor. Prueba a sincronizar el
          instrumento o vuelve a abrir el detalle.
        </p>
      )}
      {!barsLoading && !barsError && bars && bars.length === 0 && (
        <p className="text-sm text-muted-foreground">
          Sin barras OHLCV para pintar el gráfico en este periodo.
        </p>
      )}
      {barsLoading && !(bars && bars.length > 0) && (
        <p className="text-sm text-muted-foreground">Cargando gráfico…</p>
      )}
      {!barsError && bars && bars.length > 0 && (
        <div className="min-h-0 min-w-0 flex-1">
          <BacktestReplayChart
            key={detail.id}
            detail={detail}
            bars={bars}
            drawingMarkers={drawingMarkers}
            focusTimestamp={focusTimestamp}
            initialShowAll
            height={fillHeight ? "fill" : 320}
            onReplayCursorChange={handleReplayCursorChange}
            cursorFavorites={hudPrefs.cursorFavorites}
            onToggleCursorFavorite={toggleCursorFavorite}
            cursorPanelPos={hudPrefs.cursorPanelPos}
            onCursorPanelPosChange={setCursorPanelPos}
            movieHud={
              <BacktestMovieHud
                inline
                cursorTimestamp={replayCursor}
                barIndex={replayBarIndex}
                barTotal={replayBarTotal || detail.barCount}
                playing={replayPlaying}
                atEnd={replayAtEnd}
                balance={
                  liveEquity ??
                  (replayAtEnd || replayCursor == null
                    ? detail.finalEquity
                    : detail.initialCash)
                }
                returnPct={
                  liveReturnPct ??
                  (replayAtEnd || replayCursor == null
                    ? detail.totalReturnPct
                    : 0)
                }
                stats={movieStats}
                totalOps={detail.tradeCount}
                markPrice={markPrice}
                favorites={hudPrefs.temporalFavorites}
                onToggleFavorite={toggleTemporalFavorite}
              />
            }
          />
        </div>
      )}
    </section>
  );

  const tradesTable =
    detail.trades.length === 0 ? (
      <p className="rounded-lg border border-dashed border-border p-3 text-xs text-muted-foreground">
        No hubo señales en este periodo (sin compras ni ventas).
      </p>
    ) : revealedTrades.length === 0 ? (
      <p className="rounded-lg border border-dashed border-border p-3 text-xs text-muted-foreground">
        Aún no hay operaciones en esta fecha. Pulsa ▶ o avanza el barrido.
      </p>
    ) : (
      <div
        ref={tradesListRef}
        className="min-h-[200px] flex-1 overflow-x-hidden overflow-y-auto overscroll-contain rounded-lg border border-border"
      >
        <table className="w-full text-xs">
          <thead className="sticky top-0 z-[1] bg-card text-left text-muted-foreground">
            <tr>
              <th className="p-2 font-medium">Fecha</th>
              <th className="p-2 font-medium">Tipo</th>
              <th className="p-2 font-medium">Precio</th>
              <th className="p-2 font-medium">Motivo</th>
            </tr>
          </thead>
          <tbody>
            {revealedTrades.map((trade) => {
              const focused = focusTimestamp === trade.timestamp;
              const isLatest = latestRevealedTrade?.id === trade.id;
              const liveHighlight = isLatest && (replayPlaying || !replayAtEnd);
              return (
                <tr
                  key={trade.id}
                  data-trade-id={trade.id}
                  className={cn(
                    "cursor-pointer border-t border-border/50 transition-colors hover:bg-muted/40",
                    focused &&
                      "bg-amber-500/10 ring-1 ring-inset ring-amber-400/40",
                    liveHighlight && !focused && "bg-sky-500/15",
                    liveHighlight && focused && "bg-amber-500/15",
                  )}
                  onClick={() => onSelectTrade(trade.timestamp)}
                  onDoubleClick={() => onJumpToTrade(trade.timestamp)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") {
                      event.preventDefault();
                      onJumpToTrade(trade.timestamp);
                    }
                  }}
                  tabIndex={0}
                  role="button"
                  aria-label={`Seleccionar ${trade.type} en ${trade.timestamp}`}
                  aria-pressed={focused}
                >
                  <td className="p-2 font-mono tabular-nums">
                    {formatDateDdMmYyyy(trade.timestamp)}
                  </td>
                  <td
                    className={cn(
                      "p-2",
                      trade.type === "buy"
                        ? "text-success"
                        : "text-destructive",
                    )}
                  >
                    {trade.type === "buy" ? "COMPRA" : "VENTA"}
                  </td>
                  <td className="p-2 tabular-nums">
                    {formatPrice(trade.price)}
                  </td>
                  <td className="max-w-[10rem] truncate p-2 text-muted-foreground">
                    {trade.reason?.summary ?? "—"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    );

  const bottomRow = (
    <div
      ref={bottomRef}
      className={cn(
        "flex w-full min-w-0 gap-0 overflow-hidden",
        isWideBottom ? "min-h-[280px] flex-row" : "min-h-[420px] flex-col",
        fillHeight ? "flex-none" : "min-h-0 flex-1",
      )}
      style={fillHeight ? { height: isWideBottom ? 320 : 480 } : undefined}
    >
      <section
        className={cn(
          "flex min-h-0 flex-col gap-1.5 overflow-hidden",
          isWideBottom ? "shrink-0 self-stretch" : "shrink-0",
        )}
        style={
          isWideBottom
            ? { width: `${clampEquityWidthPct(equityPct)}%` }
            : { height: `${clampBottomEquityHeightPct(bottomEquityPct)}%` }
        }
      >
        <h3
          className="shrink-0 text-sm font-medium text-foreground"
          title="Patrimonio hasta la fecha del barrido. Arrastra el separador para redimensionar. Escala derecha: rueda con botón o arrastre = zoom vertical."
        >
          Evolución del dinero
        </h3>
        {equityCurve.length > 0 ? (
          <div className="min-h-0 flex-1">
            <BacktestEquityChart
              points={equityCurve}
              trades={revealedTrades}
              initialCash={detail.initialCash}
              focusTimestamp={focusTimestamp}
              untilTimestamp={replayCursor}
              height={fillHeight ? "fill" : 200}
            />
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">
            Sin curva de patrimonio en este run.
          </p>
        )}
      </section>

      {isWideBottom ? (
        <PanelResizeHandle
          label="Redimensionar patrimonio y operaciones"
          orientation="vertical"
          onDrag={adjustEquityWidth}
          onDragEnd={() => persist({ equityWidthPct: pendingEquity.current })}
          className="mx-1"
        />
      ) : (
        <PanelResizeHandle
          label="Redimensionar patrimonio y lista de operaciones"
          orientation="horizontal"
          onDrag={adjustBottomEquityHeight}
          onDragEnd={() =>
            persist({ bottomEquityHeightPct: pendingBottomEquity.current })
          }
        />
      )}

      <section
        className={cn(
          "flex min-h-0 flex-1 flex-col gap-2 overflow-hidden text-xs",
          !isWideBottom && "min-h-[240px]",
        )}
      >
        <div className="flex shrink-0 flex-wrap items-center justify-between gap-2">
          <h3
            className="text-xs font-medium text-foreground"
            title="Aparecen al llegar su fecha en el barrido. Clic marca el gráfico; doble clic salta el replay."
          >
            Operaciones
          </h3>
          <p className="tabular-nums text-muted-foreground">
            {replayPlaying ? (
              <span className="text-sky-400">
                EN VIVO · {revealedTrades.length}/{detail.tradeCount} ·{" "}
                {replayCursor ?? "…"}
              </span>
            ) : (
              <>
                {revealedTrades.length}/{detail.tradeCount}
                {replayCursor ? ` · hasta ${replayCursor}` : ""}
              </>
            )}
          </p>
        </div>
        {tradesTable}
      </section>
    </div>
  );

  const analysis = (
    <details
      className="shrink-0 rounded-lg border border-border/70 px-3 py-2"
      open={analysisOpen}
      onToggle={(e) => setAnalysisOpen(e.currentTarget.open)}
    >
      <summary className="cursor-pointer text-sm text-muted-foreground">
        Análisis · paper · baseline
        <span className="ml-1 text-xs">(checklist, trial, ratios)</span>
      </summary>
      <div className="mt-3 space-y-3">
        {buyHoldPct != null && (
          <div className="rounded-lg border border-border bg-muted/25 px-3 py-2 text-xs">
            <p className="font-medium text-foreground">Baseline buy & hold</p>
            <p className="mt-1 tabular-nums text-muted-foreground">
              B&H {formatPct(buyHoldPct)} · estrategia{" "}
              {formatPct(detail.totalReturnPct)}
              {excessPct != null ? ` · exceso ${formatPct(excessPct)}` : ""}
              {" · "}
              {finalMovieStats.winners} ganadoras / {finalMovieStats.losers}{" "}
              perdedoras
              {" · "}
              ganado {formatPrice(finalMovieStats.moneyWon)} / perdido{" "}
              {formatPrice(finalMovieStats.moneyLost)}
            </p>
          </div>
        )}
        {onDeployPaper && (
          <BacktestPaperChecklist
            detail={detail}
            excessReturnPct={excessPct}
            buyHoldReturnPct={buyHoldPct}
            linkedTrial={linkedTrial}
            deploying={deployingPaper}
            onDeploy={onDeployPaper}
          />
        )}
        <ResearchTrialResultBlock
          trialId={displayTrialId}
          metrics={displayMetrics}
          trial={linkedTrial}
          fallback={{
            totalReturnPct: detail.totalReturnPct,
            maxDrawdownPct: detail.maxDrawdownPct,
            commissionBps: detail.commissionBps,
            slippageBps: detail.slippageBps,
          }}
        />
        <p className="text-xs text-muted-foreground">
          Periodo: {formatDateRangeDdMmYyyy(detail.firstDate, detail.lastDate)}{" "}
          · {detail.barCount} barras
          {detail.timeframe ? ` · TF ${detail.timeframe}` : ""}
        </p>
        {footerNote}
      </div>
    </details>
  );

  const researchChip =
    displayTrialId != null && displayTrialId !== "" ? (
      <div className="flex flex-wrap items-center gap-2 text-[11px]">
        <Link
          to={asesorHistoryHref(displayTrialId)}
          className={cn(
            buttonVariants({ variant: "outline", size: "sm" }),
            "h-7 text-[11px]",
          )}
        >
          {VER_EN_ASESOR_LABEL}
        </Link>
        {linkedTrial ? (
          <span className="min-w-0 truncate text-muted-foreground">
            <ResearchLabEvidenceSummary trial={linkedTrial} variant="cell" />
          </span>
        ) : (
          <span className="font-mono text-muted-foreground">
            {displayTrialId.slice(0, 10)}…
          </span>
        )}
      </div>
    ) : null;

  if (!fillHeight) {
    return (
      <div className="flex w-full min-w-0 flex-col gap-3">
        <div className="w-full min-w-0">{globalBar}</div>
        {researchChip}
        <div className="min-h-[280px] w-full min-w-0">{chartBlock}</div>
        <div className="min-h-[240px] w-full min-w-0">{bottomRow}</div>
        {analysis}
      </div>
    );
  }

  /** Altura del gráfico en px (el panel entero hace scroll vertical). */
  const chartHeightPx = Math.round(
    200 + (clampChartHeightPct(chartPct) / 100) * 320,
  );

  return (
    <div
      className="h-full min-h-0 overflow-y-auto overscroll-contain"
      title="Desplaza verticalmente para ver gráfico, patrimonio y operaciones"
    >
      <div className="flex w-full min-w-0 flex-col gap-2 pb-4">
        <div className="w-full min-w-0 shrink-0">{globalBar}</div>
        {researchChip}
        <div
          ref={bodyRef}
          className="flex w-full shrink-0 flex-col overflow-hidden"
          style={{ height: chartHeightPx }}
        >
          {chartBlock}
        </div>
        <PanelResizeHandle
          label="Redimensionar altura del gráfico (el resto se ve con scroll)"
          orientation="horizontal"
          onDrag={adjustChartHeight}
          onDragEnd={() => persist({ chartHeightPct: pendingChart.current })}
        />
        {bottomRow}
        <div className="w-full shrink-0 border-t border-border/50 pt-1">
          {analysis}
        </div>
      </div>
    </div>
  );
}
