import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import {
  CandlestickSeries,
  ColorType,
  createChart,
  createSeriesMarkers,
  CrosshairMode,
  LineStyle,
  type IChartApi,
  type ISeriesApi,
  type ISeriesMarkersPluginApi,
  type MouseEventParams,
  type SeriesMarker,
  type Time,
} from "lightweight-charts";
import { Pause, Play, RotateCcw, SkipBack, SkipForward } from "lucide-react";
import type {
  BacktestRunDetailDto,
  BacktestTradeDto,
  DrawingReplayMarkerDto,
  OhlcvBarDto,
} from "@bolsa/shared";
import {
  BacktestCursorPanel,
  type BacktestCursorSnapshot,
} from "@/features/backtests/backtest-cursor-panel";
import { formatDateDdMmYyyy } from "@/features/backtests/backtest-date-format";
import type {
  BacktestCursorFieldId,
  BacktestCursorPanelPos,
} from "@/features/backtests/backtest-hud-prefs";
import {
  openPositionAt,
  unrealizedFromEntry,
} from "@/features/backtests/backtest-movie-stats";
import {
  barsToChartSeries,
  barTimeToChartTime,
  CHART_THEME,
  formatPrice,
} from "@/features/charts/chart-utils";
import { observeStableSize } from "@/features/charts/chart-stable-resize";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

function snapshotFromBar(
  bar: OhlcvBarDto,
  trades: BacktestRunDetailDto["trades"],
): BacktestCursorSnapshot {
  const open = openPositionAt(trades, bar.timestamp);
  const base: BacktestCursorSnapshot = {
    dateLabel: formatDateDdMmYyyy(bar.timestamp),
    price: bar.close,
    inPosition: Boolean(open),
    open: bar.open,
    high: bar.high,
    low: bar.low,
    close: bar.close,
    volume: bar.volume,
  };
  if (!open) return base;
  const u = unrealizedFromEntry(open, bar.close);
  return {
    ...base,
    inPosition: true,
    entryPrice: open.price,
    pnl: u.pnl,
    pnlPct: u.pct,
  };
}

const REPLAY_SPEEDS = [0.5, 1, 2, 4, 8] as const;
type ReplaySpeed = (typeof REPLAY_SPEEDS)[number];
/** Slower base + hard floor — avoids melting the CPU on long histories. */
const BASE_STEP_MS = 280;
const MIN_STEP_MS = 90;
/** While playing, notify parent at most this often (HUD / equity / trades). */
const CURSOR_EMIT_MS = 140;

function stepSizeForSpeed(speed: ReplaySpeed): number {
  if (speed >= 8) return 6;
  if (speed >= 4) return 3;
  if (speed >= 2) return 2;
  return 1;
}

interface BacktestReplayChartProps {
  detail: BacktestRunDetailDto;
  bars: OhlcvBarDto[];
  drawingMarkers?: DrawingReplayMarkerDto[];
  /** Jump replay so this bar is the last visible (trade ↔ chart sync). */
  focusTimestamp?: string | null;
  /** When true, show the full window with all trade arrows first (Phase B). */
  initialShowAll?: boolean;
  /** Fixed px height, or fill the parent (ResizeObserver). */
  height?: number | "fill";
  /** Last visible bar timestamp — drives live ops list / equity movie sync. */
  onReplayCursorChange?: (
    timestamp: string | null,
    meta: {
      playing: boolean;
      atEnd: boolean;
      barIndex: number;
      barTotal: number;
    },
  ) => void;
  /** Stats / balance HUD en la misma fila que el transporte (wrap si no cabe). */
  movieHud?: ReactNode;
  cursorFavorites: BacktestCursorFieldId[];
  onToggleCursorFavorite: (id: BacktestCursorFieldId) => void;
  cursorPanelPos: BacktestCursorPanelPos;
  onCursorPanelPosChange: (pos: BacktestCursorPanelPos) => void;
  /** Semi: al revelar una barra con trade, pausa y notifica. */
  pauseOnTrade?: boolean;
  onPausedAtTrade?: (trade: BacktestTradeDto) => void;
  /** Incrementar para reanudar tras Aceptar/Rechazar. */
  resumeNonce?: number;
  /**
   * Propuestas de pausa (run Auto completo). Si se omite, usa `detail.trades`.
   * Permite mostrar markers/equity gated y seguir pausando en señales Auto.
   */
  pauseTrades?: BacktestTradeDto[];
}

function dayKey(timestamp: string): string {
  return timestamp.slice(0, 10);
}

function barsInRunWindow(
  bars: OhlcvBarDto[],
  detail: BacktestRunDetailDto,
): OhlcvBarDto[] {
  const from = dayKey(detail.firstDate);
  const to = dayKey(detail.lastDate);
  const inWindow = bars.filter((bar) => {
    const day = dayKey(bar.timestamp);
    return day >= from && day <= to;
  });
  return inWindow.length > 0 ? inWindow : bars;
}

/** Exact match, else last bar at or before timestamp, else 0. */
export function indexForTimestamp(
  bars: OhlcvBarDto[],
  timestamp: string,
): number {
  const exact = bars.findIndex((bar) => bar.timestamp === timestamp);
  if (exact >= 0) return exact;
  let best = -1;
  for (let i = 0; i < bars.length; i += 1) {
    if (bars[i]!.timestamp <= timestamp) best = i;
    else break;
  }
  return Math.max(0, best);
}

export function BacktestReplayChart({
  detail,
  bars,
  drawingMarkers = [],
  focusTimestamp = null,
  initialShowAll = true,
  height = 320,
  onReplayCursorChange,
  movieHud,
  cursorFavorites,
  onToggleCursorFavorite,
  cursorPanelPos,
  onCursorPanelPosChange,
  pauseOnTrade = false,
  onPausedAtTrade,
  resumeNonce = 0,
  pauseTrades,
}: BacktestReplayChartProps) {
  const runBars = useMemo(() => barsInRunWindow(bars, detail), [bars, detail]);
  const fillParent = height === "fill";
  const [measuredHeight, setMeasuredHeight] = useState(280);
  const chartHeight = fillParent ? measuredHeight : height;

  const startCount = useCallback(
    (length: number) => {
      if (length <= 0) return 1;
      // After «Probar»: show the full window (last bar / 100%). ▶ from the end restarts at 1.
      if (initialShowAll) return length;
      return 1;
    },
    [initialShowAll],
  );

  const [visibleCount, setVisibleCount] = useState(() =>
    startCount(runBars.length),
  );
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState<ReplaySpeed>(1);
  const [cursorSnapshot, setCursorSnapshot] =
    useState<BacktestCursorSnapshot | null>(null);

  const shellRef = useRef<HTMLDivElement>(null);
  const surfaceRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const runBarsRef = useRef(runBars);
  runBarsRef.current = runBars;
  const proposalTrades = pauseTrades ?? detail.trades;
  const tradesRef = useRef(proposalTrades);
  tradesRef.current = proposalTrades;
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const markersRef = useRef<ISeriesMarkersPluginApi<Time> | null>(null);
  const markersCacheRef = useRef<SeriesMarker<Time>[]>([]);
  const prevVisibleCountRef = useRef(0);
  const lastFocusRef = useRef<string | null>(null);
  const playingRef = useRef(false);
  const lastCursorEmitRef = useRef(0);
  const cursorEmitTimerRef = useRef<number | null>(null);
  const visibleCountRef = useRef(visibleCount);
  visibleCountRef.current = visibleCount;
  const onCursorRef = useRef(onReplayCursorChange);
  onCursorRef.current = onReplayCursorChange;
  playingRef.current = playing;
  const pauseOnTradeRef = useRef(pauseOnTrade);
  pauseOnTradeRef.current = pauseOnTrade;
  const onPausedAtTradeRef = useRef(onPausedAtTrade);
  onPausedAtTradeRef.current = onPausedAtTrade;
  const gatedTradeIdsRef = useRef<Set<string>>(new Set());

  const tradeByTime = useMemo(() => {
    const map = new Map<string, (typeof detail.trades)[number]>();
    for (const trade of detail.trades) map.set(trade.timestamp, trade);
    return map;
  }, [detail]);

  const drawingByTime = useMemo(() => {
    const map = new Map<string, DrawingReplayMarkerDto[]>();
    for (const marker of drawingMarkers) {
      const list = map.get(marker.timestamp) ?? [];
      list.push(marker);
      map.set(marker.timestamp, list);
    }
    return map;
  }, [drawingMarkers]);

  useEffect(() => {
    if (!fillParent) return undefined;
    const shell = shellRef.current;
    if (!shell) return undefined;
    const apply = () => {
      const next = Math.max(180, Math.floor(shell.clientHeight));
      setMeasuredHeight((prev) => (Math.abs(prev - next) < 2 ? prev : next));
    };
    apply();
    const ro = new ResizeObserver(apply);
    ro.observe(shell);
    return () => ro.disconnect();
  }, [fillParent, detail.id]);

  useEffect(() => {
    setVisibleCount(startCount(runBars.length));
    setPlaying(false);
    lastFocusRef.current = null;
    prevVisibleCountRef.current = 0;
    markersCacheRef.current = [];
    gatedTradeIdsRef.current = new Set();
  }, [detail.id, runBars.length, startCount]);

  useEffect(() => {
    if (resumeNonce <= 0) return;
    setPlaying(true);
  }, [resumeNonce]);

  useEffect(() => {
    if (!focusTimestamp || runBars.length === 0) return;
    if (focusTimestamp === lastFocusRef.current) return;
    lastFocusRef.current = focusTimestamp;
    const index = indexForTimestamp(runBars, focusTimestamp);
    if (index < 0) return;
    const target = index + 1;
    // Movie sync: selecting the just-revealed trade must not pause/rewind playback.
    if (playingRef.current) return;
    setPlaying(false);
    setVisibleCount(Math.max(1, target));
  }, [focusTimestamp, runBars]);

  // Create chart once per run / bar set — height updates via applyOptions (no remount flicker).
  useEffect(() => {
    const container = containerRef.current;
    if (!container || runBars.length === 0) return undefined;

    const chart = createChart(container, {
      width: Math.max(1, container.clientWidth),
      height: Math.max(160, chartHeight),
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#94a3b8",
        fontSize: 11,
      },
      grid: {
        vertLines: { color: CHART_THEME.gridColor },
        horzLines: { color: CHART_THEME.gridColor },
      },
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false },
      localization: {
        locale: "es-ES",
        timeFormatter: (time: Time) => {
          if (typeof time === "string") return formatDateDdMmYyyy(time);
          if (typeof time === "number") {
            return formatDateDdMmYyyy(new Date(time * 1000).toISOString());
          }
          return `${String(time.day).padStart(2, "0")}/${String(time.month).padStart(2, "0")}/${time.year}`;
        },
        priceFormatter: (price: number) => formatPrice(price),
      },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: {
          visible: true,
          labelVisible: true,
          width: 1,
          style: LineStyle.Solid,
          color: "rgba(56, 189, 248, 0.65)",
          labelBackgroundColor: "#0f172a",
        },
        horzLine: {
          visible: true,
          labelVisible: true,
          width: 1,
          style: LineStyle.Solid,
          color: "rgba(56, 189, 248, 0.65)",
          labelBackgroundColor: "#0f172a",
        },
      },
    });

    const series = chart.addSeries(CandlestickSeries, {
      upColor: CHART_THEME.upColor,
      downColor: CHART_THEME.downColor,
      borderVisible: false,
      wickUpColor: CHART_THEME.upColor,
      wickDownColor: CHART_THEME.downColor,
    });

    chartRef.current = chart;
    seriesRef.current = series;
    markersRef.current = createSeriesMarkers(series, []);

    const onCrosshair = (param: MouseEventParams<Time>) => {
      // While the movie plays, the crosshair is driven by the replay date — ignore mouse.
      if (playingRef.current) return;

      if (
        param.point == null ||
        param.time == null ||
        param.point.x < 0 ||
        param.point.y < 0
      ) {
        return;
      }

      const logical = chart.timeScale().coordinateToLogical(param.point.x);
      if (logical == null) return;
      const idx = Math.max(
        0,
        Math.min(runBarsRef.current.length - 1, Math.round(logical)),
      );
      const bar = runBarsRef.current[idx];
      if (!bar) return;
      setCursorSnapshot(snapshotFromBar(bar, tradesRef.current));
    };

    chart.subscribeCrosshairMove(onCrosshair);

    const stopResize = observeStableSize(container, (width, nextHeight) => {
      chart.applyOptions({
        width: Math.max(1, width),
        height: Math.max(160, nextHeight),
      });
    });

    return () => {
      chart.unsubscribeCrosshairMove(onCrosshair);
      stopResize();
      markersRef.current = null;
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- remount only when run/bars change
  }, [detail.id, runBars.length]);

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart || !fillParent) return;
    chart.applyOptions({ height: Math.max(160, chartHeight) });
  }, [chartHeight, fillParent]);

  const clampedCount = Math.min(visibleCount, runBars.length);
  const lastVisibleTimestamp = runBars[clampedCount - 1]?.timestamp;
  const atEnd = clampedCount >= runBars.length && runBars.length > 0;

  const buildMarkersUpTo = useCallback(
    (count: number): SeriesMarker<Time>[] => {
      const markers: SeriesMarker<Time>[] = [];
      for (let i = 0; i < count; i += 1) {
        const bar = runBars[i];
        if (!bar) continue;
        const trade = tradeByTime.get(bar.timestamp);
        if (trade) {
          const focused = focusTimestamp === bar.timestamp;
          markers.push({
            time: barTimeToChartTime(bar.timestamp) as Time,
            position: trade.type === "buy" ? "belowBar" : "aboveBar",
            color: focused
              ? "#fbbf24"
              : trade.type === "buy"
                ? CHART_THEME.upColor
                : CHART_THEME.downColor,
            shape: trade.type === "buy" ? "arrowUp" : "arrowDown",
            text: focused
              ? trade.type === "buy"
                ? "B★"
                : "S★"
              : trade.type === "buy"
                ? "B"
                : "S",
          });
        }
        const drawings = drawingByTime.get(bar.timestamp);
        if (drawings) {
          for (const marker of drawings) {
            markers.push({
              time: barTimeToChartTime(marker.timestamp) as Time,
              position: marker.direction === "up" ? "belowBar" : "aboveBar",
              color: marker.direction === "up" ? "#a855f7" : "#f59e0b",
              shape: "circle",
              text: marker.direction === "up" ? "↑" : "↓",
            });
          }
        }
      }
      return markers;
    },
    [drawingByTime, focusTimestamp, runBars, tradeByTime],
  );

  const emitCursor = useCallback(
    (force = false) => {
      const push = () => {
        const count = Math.min(visibleCountRef.current, runBars.length);
        onCursorRef.current?.(runBars[count - 1]?.timestamp ?? null, {
          playing: playingRef.current,
          atEnd: count >= runBars.length && runBars.length > 0,
          barIndex: count,
          barTotal: runBars.length,
        });
        lastCursorEmitRef.current = performance.now();
      };

      if (!force && playingRef.current) {
        const elapsed = performance.now() - lastCursorEmitRef.current;
        if (elapsed < CURSOR_EMIT_MS) {
          if (cursorEmitTimerRef.current == null) {
            cursorEmitTimerRef.current = window.setTimeout(() => {
              cursorEmitTimerRef.current = null;
              push();
            }, CURSOR_EMIT_MS - elapsed);
          }
          return;
        }
      } else if (cursorEmitTimerRef.current != null) {
        window.clearTimeout(cursorEmitTimerRef.current);
        cursorEmitTimerRef.current = null;
      }

      push();
    },
    [runBars],
  );

  useEffect(() => {
    emitCursor(!playing);
  }, [emitCursor, playing, visibleCount]);

  useEffect(() => {
    return () => {
      if (cursorEmitTimerRef.current != null) {
        window.clearTimeout(cursorEmitTimerRef.current);
      }
    };
  }, []);

  // Chart data: incremental update() while playing; full setData only on jumps.
  useEffect(() => {
    const chart = chartRef.current;
    const series = seriesRef.current;
    if (!chart || !series || runBars.length === 0 || clampedCount <= 0) return;

    const prev = prevVisibleCountRef.current;
    const canIncremental =
      playingRef.current &&
      prev > 0 &&
      clampedCount > prev &&
      clampedCount - prev <= 8;

    const showAllRevealed = () => {
      // Critical: scrollToRealTime zooms to ~2 candles. Show the full movie so far.
      chart.timeScale().setVisibleLogicalRange({
        from: -0.5,
        to: Math.max(clampedCount - 0.5, 0.5),
      });
    };

    if (canIncremental) {
      for (let i = prev; i < clampedCount; i += 1) {
        const bar = runBars[i];
        if (!bar) continue;
        const candle = barsToChartSeries([bar])[0]!;
        series.update(candle);

        const trade = tradeByTime.get(bar.timestamp);
        if (trade) {
          markersCacheRef.current = [
            ...markersCacheRef.current,
            {
              time: barTimeToChartTime(bar.timestamp) as Time,
              position: trade.type === "buy" ? "belowBar" : "aboveBar",
              color:
                trade.type === "buy"
                  ? CHART_THEME.upColor
                  : CHART_THEME.downColor,
              shape: trade.type === "buy" ? "arrowUp" : "arrowDown",
              text: trade.type === "buy" ? "B" : "S",
            },
          ];
        }
        const drawings = drawingByTime.get(bar.timestamp);
        if (drawings) {
          for (const marker of drawings) {
            markersCacheRef.current = [
              ...markersCacheRef.current,
              {
                time: barTimeToChartTime(marker.timestamp) as Time,
                position: marker.direction === "up" ? "belowBar" : "aboveBar",
                color: marker.direction === "up" ? "#a855f7" : "#f59e0b",
                shape: "circle",
                text: marker.direction === "up" ? "↑" : "↓",
              },
            ];
          }
        }
      }
      markersRef.current?.setMarkers(markersCacheRef.current);
      showAllRevealed();
    } else if (prev === clampedCount && prev > 0) {
      // Focus/markers only — do not rewrite candle data.
      markersCacheRef.current = buildMarkersUpTo(clampedCount);
      markersRef.current?.setMarkers(markersCacheRef.current);
    } else {
      const visibleBars = runBars.slice(0, clampedCount);
      series.setData(barsToChartSeries(visibleBars));
      markersCacheRef.current = buildMarkersUpTo(clampedCount);
      if (markersRef.current) {
        markersRef.current.setMarkers(markersCacheRef.current);
      } else {
        markersRef.current = createSeriesMarkers(
          series,
          markersCacheRef.current,
        );
      }
      showAllRevealed();
    }

    prevVisibleCountRef.current = clampedCount;
  }, [
    buildMarkersUpTo,
    clampedCount,
    drawingByTime,
    focusTimestamp,
    playing,
    runBars,
    tradeByTime,
  ]);

  // When paused / scrubbing, keep the floating panel on the last revealed bar
  // (mouse hover can override via subscribeCrosshairMove).
  useEffect(() => {
    if (playing || runBars.length === 0 || clampedCount <= 0) return;
    const bar = runBars[clampedCount - 1];
    if (bar) setCursorSnapshot(snapshotFromBar(bar, detail.trades));
  }, [clampedCount, detail.trades, playing, runBars]);

  // During playback, pin the chart crosshair + tip to the current movie bar.
  useEffect(() => {
    if (!playing || runBars.length === 0 || clampedCount <= 0) return undefined;

    const bar = runBars[clampedCount - 1];
    if (!bar) return undefined;

    const apply = () => {
      const chart = chartRef.current;
      const series = seriesRef.current;
      if (!chart || !series || !playingRef.current) return;

      const time = barTimeToChartTime(bar.timestamp) as Time;
      chart.setCrosshairPosition(bar.close, time, series);
      setCursorSnapshot(snapshotFromBar(bar, tradesRef.current));
    };

    // Wait a frame so setVisibleLogicalRange has updated coordinates.
    const frame = window.requestAnimationFrame(apply);
    return () => window.cancelAnimationFrame(frame);
  }, [clampedCount, playing, runBars]);

  useEffect(() => {
    if (!playing || runBars.length === 0) return undefined;
    const stepMs = Math.max(MIN_STEP_MS, Math.round(BASE_STEP_MS / speed));
    const jump = stepSizeForSpeed(speed);
    const timer = window.setInterval(() => {
      setVisibleCount((current) => {
        if (current >= runBars.length) {
          setPlaying(false);
          return runBars.length;
        }
        const target = Math.min(runBars.length, current + jump);
        if (pauseOnTradeRef.current) {
          for (let i = current; i < target; i += 1) {
            const bar = runBarsRef.current[i];
            if (!bar) continue;
            const trade = tradesRef.current.find(
              (t) => t.timestamp === bar.timestamp,
            );
            if (trade && !gatedTradeIdsRef.current.has(trade.id)) {
              gatedTradeIdsRef.current.add(trade.id);
              setPlaying(false);
              onPausedAtTradeRef.current?.(trade);
              return i + 1;
            }
          }
        }
        return target;
      });
    }, stepMs);
    return () => window.clearInterval(timer);
  }, [playing, runBars.length, speed]);

  const togglePlay = useCallback(() => {
    setPlaying((wasPlaying) => {
      if (wasPlaying) return false;
      // At the end (typical after "Ver todo") → restart movie from the beginning.
      setVisibleCount((current) => (current >= runBars.length ? 1 : current));
      return true;
    });
  }, [runBars.length]);

  const step = useCallback(
    (delta: number) => {
      setPlaying(false);
      setVisibleCount((current) =>
        Math.max(1, Math.min(runBars.length, current + delta)),
      );
    },
    [runBars.length],
  );

  if (runBars.length === 0) {
    return (
      <p className="rounded-lg border border-dashed border-border p-4 text-sm text-muted-foreground">
        No hay barras OHLCV en el período del run ({detail.firstDate} →{" "}
        {detail.lastDate}).
      </p>
    );
  }

  const controls = (
    <div className="w-full min-w-0 space-y-1.5 rounded-xl border border-sky-500/25 bg-gradient-to-r from-sky-500/10 via-card/80 to-card/50 px-2.5 py-2 shadow-sm">
      <div className="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1.5">
        <div className="flex shrink-0 flex-col gap-0.5">
          <span className="px-0.5 text-[9px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
            Datos temporales
          </span>
          <div className="flex shrink-0 flex-wrap items-center gap-1">
            <Button
              type="button"
              size="sm"
              variant="outline"
              className="h-8 w-8 p-0"
              aria-label={
                playing
                  ? "Pausar replay"
                  : atEnd
                    ? "Reproducir desde el inicio"
                    : "Reproducir replay"
              }
              onClick={togglePlay}
            >
              {playing ? (
                <Pause className="h-4 w-4" />
              ) : (
                <Play className="h-4 w-4" />
              )}
            </Button>
            <Button
              type="button"
              size="sm"
              variant="outline"
              className="h-8 w-8 p-0"
              aria-label="Barra anterior"
              onClick={() => step(-1)}
            >
              <SkipBack className="h-4 w-4" />
            </Button>
            <Button
              type="button"
              size="sm"
              variant="outline"
              className="h-8 w-8 p-0"
              aria-label="Barra siguiente"
              onClick={() => step(1)}
            >
              <SkipForward className="h-4 w-4" />
            </Button>
            <Button
              type="button"
              size="sm"
              variant="outline"
              className="h-8 w-8 p-0"
              aria-label="Reiniciar replay"
              onClick={() => {
                setPlaying(false);
                setVisibleCount(1);
              }}
            >
              <RotateCcw className="h-4 w-4" />
            </Button>
            <Button
              type="button"
              size="sm"
              variant="ghost"
              className="h-8 px-2 text-xs"
              disabled={atEnd && !playing}
              onClick={() => {
                setPlaying(false);
                setVisibleCount(runBars.length);
              }}
            >
              Todo
            </Button>
            <label className="flex items-center gap-1 text-[11px] text-muted-foreground">
              <select
                value={speed}
                aria-label="Velocidad de reproducción"
                className="h-8 rounded-md border border-border bg-background px-1.5 text-foreground"
                onChange={(event) =>
                  setSpeed(Number(event.target.value) as ReplaySpeed)
                }
              >
                {REPLAY_SPEEDS.map((value) => (
                  <option key={value} value={value}>
                    ×{value}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </div>

        {movieHud ? (
          <div className="min-w-0 flex-1 basis-[min(100%,22rem)]">
            {movieHud}
          </div>
        ) : (
          <span className="ml-auto text-base font-semibold tabular-nums text-foreground">
            {formatDateDdMmYyyy(lastVisibleTimestamp)}
          </span>
        )}
      </div>

      <input
        type="range"
        min={1}
        max={runBars.length}
        value={clampedCount}
        className={cn("w-full accent-sky-500")}
        aria-label="Posición del replay"
        onChange={(event) => {
          setPlaying(false);
          setVisibleCount(Number(event.target.value));
        }}
      />
    </div>
  );

  const chartSurface = (
    <div ref={surfaceRef} className="relative h-full w-full cursor-crosshair">
      <div
        ref={containerRef}
        className="h-full w-full overflow-hidden rounded-xl border border-border/80 bg-card/40"
        aria-label="Replay manual del backtest sobre velas"
      />
      <BacktestCursorPanel
        snapshot={cursorSnapshot}
        favorites={cursorFavorites}
        onToggleFavorite={onToggleCursorFavorite}
        position={cursorPanelPos}
        onPositionChange={onCursorPanelPosChange}
        boundsRef={surfaceRef}
      />
    </div>
  );

  if (fillParent) {
    return (
      <div className="flex h-full min-h-0 flex-col gap-1.5">
        <div className="shrink-0">{controls}</div>
        <div ref={shellRef} className="min-h-0 flex-1">
          {chartSurface}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-1.5">
      {controls}
      <div style={{ height: chartHeight }}>{chartSurface}</div>
    </div>
  );
}
