import type { OhlcvBarDto } from "@bolsa/shared";
import {
  CHART_CURSOR_BAR_MENU_GROUPS,
  CHART_CURSOR_FIELD_LABELS,
  CHART_CURSOR_FIELD_SHORT_LABELS,
  CHART_CURSOR_FIELD_TIPS,
  type ChartCursorBarField,
} from "@bolsa/shared";
import { Crosshair } from "lucide-react";
import { useMemo } from "react";

import { ChartBarZonePicker } from "@/features/charts/chart-bar-zone-picker";
import { ChartBarZoneIconAnchor } from "@/features/charts/chart-bar-zone-rail-button";
import {
  formatBarIntraChangeLabel,
  formatChartBarPrice,
} from "@/features/charts/chart-utils";
import { CHART_BAR_ZONE_ROW_CLASS } from "@/features/charts/chart-bar-zone-styles";
import { useChartCursorFieldFavorites } from "@/features/charts/use-chart-bar-zone-favorites";
import { useChartCursorStore } from "@/stores/chart-cursor-store";
import { cn } from "@/lib/utils";

const MENU_OPTIONS = Object.fromEntries(
  (Object.keys(CHART_CURSOR_FIELD_LABELS) as ChartCursorBarField[]).map(
    (id) => [
      id,
      {
        id,
        label: CHART_CURSOR_FIELD_LABELS[id],
        hint: CHART_CURSOR_FIELD_TIPS[id],
      },
    ],
  ),
) as Record<
  ChartCursorBarField,
  { id: ChartCursorBarField; label: string; hint: string }
>;

const CURSOR_FIELD_BUTTON_CLASS: Record<ChartCursorBarField, string> = {
  open: "w-[4.65rem]",
  high: "w-[4.65rem]",
  low: "w-[4.65rem]",
  close: "w-[4.65rem]",
  changePct: "w-[9.25rem]",
  volume: "w-[4.35rem]",
};

const CURSOR_PRICE_VALUE_CLASS =
  "inline-block w-[3.5rem] truncate text-right tabular-nums text-foreground";
const CURSOR_CHANGE_VALUE_CLASS =
  "inline-block w-[8.25rem] truncate text-right font-medium tabular-nums";
const CURSOR_VOLUME_VALUE_CLASS =
  "inline-block w-[2.25rem] truncate text-right tabular-nums text-foreground";

function formatVolume(value: number): string {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`;
  return String(Math.round(value));
}

function resolveActiveBar(
  bars: OhlcvBarDto[],
  instrumentId: string | undefined,
  hoveredInstrumentId: string | null,
  hoveredBar: OhlcvBarDto | null,
): OhlcvBarDto | null {
  if (instrumentId && hoveredInstrumentId === instrumentId && hoveredBar)
    return hoveredBar;
  return bars.at(-1) ?? null;
}

function OhlcChip({ label, value }: { label: string; value: string }) {
  return (
    <span className="inline-flex w-full items-baseline justify-between gap-0.5 tabular-nums">
      <span className="shrink-0 text-muted-foreground">{label}</span>
      <span className={CURSOR_PRICE_VALUE_CLASS}>{value}</span>
    </span>
  );
}

function renderCursorChip(field: ChartCursorBarField, bar: OhlcvBarDto) {
  switch (field) {
    case "open":
      return <OhlcChip label="O" value={formatChartBarPrice(bar.open)} />;
    case "high":
      return <OhlcChip label="H" value={formatChartBarPrice(bar.high)} />;
    case "low":
      return <OhlcChip label="L" value={formatChartBarPrice(bar.low)} />;
    case "close":
      return <OhlcChip label="C" value={formatChartBarPrice(bar.close)} />;
    case "changePct": {
      const change = formatBarIntraChangeLabel(bar);
      if (!change) {
        return (
          <span className="inline-block w-full truncate text-muted-foreground">
            —
          </span>
        );
      }
      return (
        <span
          className={cn(
            CURSOR_CHANGE_VALUE_CLASS,
            change.isUp ? "text-emerald-500" : "text-red-500",
          )}
        >
          {change.text}
        </span>
      );
    }
    case "volume":
      return (
        <span className="inline-flex w-full items-baseline justify-between gap-0.5 tabular-nums text-muted-foreground">
          <span className="shrink-0">Vol</span>
          <span className={CURSOR_VOLUME_VALUE_CLASS}>
            {formatVolume(bar.volume)}
          </span>
        </span>
      );
    default:
      return null;
  }
}

interface ChartCursorZoneProps {
  instrumentId?: string;
  bars: OhlcvBarDto[];
  className?: string;
}

export function ChartCursorZone({
  instrumentId,
  bars,
  className,
}: ChartCursorZoneProps) {
  const hoveredInstrumentId = useChartCursorStore((s) => s.instrumentId);
  const hoveredBar = useChartCursorStore((s) => s.hoveredBar);
  const { favorites, toggleFavorite, isFavorite, anchor } =
    useChartCursorFieldFavorites();

  const activeBar = useMemo(
    () => resolveActiveBar(bars, instrumentId, hoveredInstrumentId, hoveredBar),
    [bars, hoveredBar, hoveredInstrumentId, instrumentId],
  );

  const usingCursor = Boolean(
    instrumentId && hoveredInstrumentId === instrumentId && hoveredBar,
  );

  const cursorHint = usingCursor
    ? "Mostrando la vela bajo el cursor del gráfico."
    : "Sin cursor sobre el gráfico: se muestra la última vela disponible.";

  if (!activeBar) {
    return (
      <div
        className={cn(CHART_BAR_ZONE_ROW_CLASS, className)}
        title={cursorHint}
      >
        <ChartBarZoneIconAnchor
          icon={Crosshair}
          title="Cursor"
          hint={cursorHint}
          showMenu={false}
          onOpenMenu={() => {}}
        />
      </div>
    );
  }

  return (
    <ChartBarZonePicker
      zoneIcon={Crosshair}
      zoneTitle="Cursor"
      zoneHint={`${cursorHint} O/H/L/C = vela bajo el cursor (timeframe del gráfico). Δ = cierre − apertura de esa vela. Icono = menú y favoritos.`}
      activeId={anchor}
      favorites={favorites}
      menuGroups={CHART_CURSOR_BAR_MENU_GROUPS}
      options={MENU_OPTIONS}
      isFavorite={(id) => id === anchor || isFavorite(id)}
      isFavoriteLocked={(id) => id === anchor}
      onToggleFavorite={toggleFavorite}
      onSelectOption={(id) => {
        if (id !== anchor) toggleFavorite(id);
      }}
      getButtonLabel={(id) =>
        id === "close"
          ? `C ${formatChartBarPrice(activeBar.close)}`
          : CHART_CURSOR_FIELD_SHORT_LABELS[id]
      }
      getButtonClassName={(id) => CURSOR_FIELD_BUTTON_CLASS[id]}
      renderButtonContent={(id) => renderCursorChip(id, activeBar)}
      selectionMode="display"
      className={cn("min-w-0 max-w-full", className)}
    />
  );
}
