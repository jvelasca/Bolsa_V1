import { GripVertical } from "lucide-react";
import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type RefObject,
} from "react";
import { BacktestFavoritesMenu } from "@/features/backtests/backtest-favorites-menu";
import {
  BACKTEST_CURSOR_FIELD_OPTIONS,
  type BacktestCursorFieldId,
  type BacktestCursorPanelPos,
} from "@/features/backtests/backtest-hud-prefs";
import { formatPct, formatPrice } from "@/features/charts/chart-utils";
import { cn } from "@/lib/utils";

export type BacktestCursorSnapshot = {
  dateLabel: string;
  price: number;
  inPosition: boolean;
  entryPrice?: number;
  pnl?: number;
  pnlPct?: number;
  open?: number;
  high?: number;
  low?: number;
  close?: number;
  volume?: number | null;
};

type Props = {
  snapshot: BacktestCursorSnapshot | null;
  favorites: BacktestCursorFieldId[];
  onToggleFavorite: (id: BacktestCursorFieldId) => void;
  position: BacktestCursorPanelPos;
  onPositionChange: (pos: BacktestCursorPanelPos) => void;
  /** Bounds container (chart surface). */
  boundsRef: RefObject<HTMLElement | null>;
};

function Row({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: "good" | "bad" | "neutral";
}) {
  return (
    <div className="flex items-baseline justify-between gap-3 text-[11px] leading-snug">
      <span className="text-muted-foreground">{label}</span>
      <span
        className={cn(
          "tabular-nums font-medium",
          tone === "good" && "text-emerald-400",
          tone === "bad" && "text-rose-400",
          tone === "neutral" && "text-foreground",
          !tone && "text-foreground",
        )}
      >
        {value}
      </span>
    </div>
  );
}

/** Draggable floating panel for candle / position data (does not follow the crosshair tip). */
export function BacktestCursorPanel({
  snapshot,
  favorites,
  onToggleFavorite,
  position,
  onPositionChange,
  boundsRef,
}: Props) {
  const panelRef = useRef<HTMLDivElement>(null);
  const [dragging, setDragging] = useState(false);
  const [localPos, setLocalPos] = useState(position);
  const dragOffset = useRef({ x: 0, y: 0 });
  const show = (id: BacktestCursorFieldId) => favorites.includes(id);

  useEffect(() => {
    if (!dragging) setLocalPos(position);
  }, [dragging, position]);

  const clampToBounds = useCallback(
    (x: number, y: number): BacktestCursorPanelPos => {
      const bounds = boundsRef.current;
      const panel = panelRef.current;
      if (!bounds || !panel) return { x: Math.max(0, x), y: Math.max(0, y) };
      const maxX = Math.max(0, bounds.clientWidth - panel.offsetWidth - 4);
      const maxY = Math.max(0, bounds.clientHeight - panel.offsetHeight - 4);
      return {
        x: Math.min(maxX, Math.max(0, x)),
        y: Math.min(maxY, Math.max(0, y)),
      };
    },
    [boundsRef],
  );

  useEffect(() => {
    if (!dragging) return undefined;
    const onMove = (event: PointerEvent) => {
      const bounds = boundsRef.current;
      if (!bounds) return;
      const rect = bounds.getBoundingClientRect();
      setLocalPos(
        clampToBounds(
          event.clientX - rect.left - dragOffset.current.x,
          event.clientY - rect.top - dragOffset.current.y,
        ),
      );
    };
    const onUp = () => {
      setDragging(false);
      setLocalPos((current) => {
        const next = clampToBounds(current.x, current.y);
        onPositionChange(next);
        return next;
      });
    };
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    return () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
    };
  }, [boundsRef, clampToBounds, dragging, onPositionChange]);

  // Keep panel inside bounds when chart resizes.
  useEffect(() => {
    const bounds = boundsRef.current;
    if (!bounds) return undefined;
    const ro = new ResizeObserver(() => {
      setLocalPos((current) => {
        const next = clampToBounds(current.x, current.y);
        if (next.x !== current.x || next.y !== current.y)
          onPositionChange(next);
        return next;
      });
    });
    ro.observe(bounds);
    return () => ro.disconnect();
  }, [boundsRef, clampToBounds, onPositionChange]);

  const changePct =
    snapshot?.open != null && snapshot.open > 0 && snapshot.close != null
      ? ((snapshot.close - snapshot.open) / snapshot.open) * 100
      : null;

  const pnlTone =
    snapshot?.pnl == null
      ? undefined
      : snapshot.pnl >= 0
        ? ("good" as const)
        : ("bad" as const);

  return (
    <div
      ref={panelRef}
      className={cn(
        "absolute z-30 w-[200px] rounded-lg border bg-slate-950/94 shadow-xl backdrop-blur-sm",
        snapshot?.inPosition
          ? (snapshot.pnl ?? 0) >= 0
            ? "border-emerald-400/40"
            : "border-rose-400/40"
          : "border-sky-400/35",
        dragging && "cursor-grabbing",
      )}
      style={{ left: localPos.x, top: localPos.y }}
      onPointerDown={(event) => event.stopPropagation()}
    >
      <div
        className="flex cursor-grab items-center gap-1 border-b border-border/50 px-1.5 py-1 active:cursor-grabbing"
        onPointerDown={(event) => {
          if ((event.target as HTMLElement).closest("button")) return;
          const bounds = boundsRef.current;
          if (!bounds) return;
          const boundsRect = bounds.getBoundingClientRect();
          dragOffset.current = {
            x: event.clientX - boundsRect.left - localPos.x,
            y: event.clientY - boundsRect.top - localPos.y,
          };
          setDragging(true);
          event.preventDefault();
        }}
      >
        <GripVertical
          className="h-3.5 w-3.5 shrink-0 text-muted-foreground"
          aria-hidden
        />
        <p className="min-w-0 flex-1 truncate text-[10px] font-semibold uppercase tracking-[0.1em] text-muted-foreground">
          Vela · posición
        </p>
        <BacktestFavoritesMenu
          title="Datos del cursor"
          hint="Elige qué campos muestra este panel. Arrastra el panel para colocarlo."
          options={BACKTEST_CURSOR_FIELD_OPTIONS}
          favorites={favorites}
          onToggleFavorite={onToggleFavorite}
          align="right"
        />
      </div>

      <div className="space-y-1 px-2.5 py-2">
        {!snapshot ? (
          <p className="text-[11px] text-muted-foreground">
            Pasa el ratón o pulsa ▶ para ver la vela.
          </p>
        ) : (
          <>
            {show("date") && (
              <p className="text-[12px] font-semibold tabular-nums text-sky-200">
                {snapshot.dateLabel}
              </p>
            )}
            {show("price") && (
              <Row label="Precio" value={formatPrice(snapshot.price)} />
            )}
            {show("position") && (
              <Row
                label="Posición"
                value={snapshot.inPosition ? "Comprado" : "Sin posición"}
                tone={snapshot.inPosition ? "good" : "neutral"}
              />
            )}
            {show("entryPrice") &&
              snapshot.inPosition &&
              snapshot.entryPrice != null && (
                <Row label="Compra" value={formatPrice(snapshot.entryPrice)} />
              )}
            {show("pnl") && snapshot.inPosition && snapshot.pnl != null && (
              <Row
                label="Beneficio"
                value={`${snapshot.pnl >= 0 ? "+" : ""}${formatPrice(snapshot.pnl)}${
                  snapshot.pnlPct != null
                    ? ` · ${snapshot.pnlPct >= 0 ? "+" : ""}${snapshot.pnlPct.toFixed(1)}%`
                    : ""
                }`}
                tone={pnlTone}
              />
            )}
            {show("open") && snapshot.open != null && (
              <Row label="O" value={formatPrice(snapshot.open)} />
            )}
            {show("high") && snapshot.high != null && (
              <Row label="H" value={formatPrice(snapshot.high)} />
            )}
            {show("low") && snapshot.low != null && (
              <Row label="L" value={formatPrice(snapshot.low)} />
            )}
            {show("close") && snapshot.close != null && (
              <Row label="C" value={formatPrice(snapshot.close)} />
            )}
            {show("changePct") && changePct != null && (
              <Row
                label="Δ vela"
                value={formatPct(changePct)}
                tone={changePct >= 0 ? "good" : "bad"}
              />
            )}
            {show("volume") && (
              <Row
                label="Vol"
                value={
                  snapshot.volume != null && Number.isFinite(snapshot.volume)
                    ? snapshot.volume.toLocaleString("es-ES")
                    : "—"
                }
              />
            )}
          </>
        )}
      </div>
    </div>
  );
}
