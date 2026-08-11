import type { InstrumentDto } from "@bolsa/shared";
import {
  CHART_INSTRUMENT_BAR_MENU_GROUPS,
  CHART_INSTRUMENT_FIELD_LABELS,
  CHART_INSTRUMENT_FIELD_SHORT_LABELS,
  CHART_INSTRUMENT_FIELD_TIPS,
  type ChartInstrumentBarField,
} from "@bolsa/shared";
import { Landmark } from "lucide-react";

import { ChartBarZoneIconAnchor } from "@/features/charts/chart-bar-zone-rail-button";
import { ChartBarZonePicker } from "@/features/charts/chart-bar-zone-picker";
import {
  CHART_BAR_ZONE_CHIP_MUTED,
  CHART_BAR_ZONE_ROW_CLASS,
  CHART_BAR_ZONE_VALUE_CLASS,
} from "@/features/charts/chart-bar-zone-styles";
import { useChartInstrumentFieldFavorites } from "@/features/charts/use-chart-bar-zone-favorites";
import { cn } from "@/lib/utils";

const MENU_OPTIONS = Object.fromEntries(
  (Object.keys(CHART_INSTRUMENT_FIELD_LABELS) as ChartInstrumentBarField[]).map(
    (id) => [
      id,
      {
        id,
        label: CHART_INSTRUMENT_FIELD_LABELS[id],
        hint: CHART_INSTRUMENT_FIELD_TIPS[id],
      },
    ],
  ),
) as Record<
  ChartInstrumentBarField,
  { id: ChartInstrumentBarField; label: string; hint: string }
>;

function renderInstrumentChip(
  field: ChartInstrumentBarField,
  instrument: InstrumentDto,
  listLabel?: string,
) {
  switch (field) {
    case "symbol":
      return (
        <span className={cn("font-semibold", CHART_BAR_ZONE_VALUE_CLASS)}>
          {instrument.symbol}
        </span>
      );
    case "name":
      return (
        <span className={cn("truncate", CHART_BAR_ZONE_CHIP_MUTED)}>
          {instrument.name}
        </span>
      );
    case "yahooSymbol":
      return (
        <span className={CHART_BAR_ZONE_CHIP_MUTED}>
          {instrument.yahooSymbol}
        </span>
      );
    case "exchange":
      return (
        <span className={CHART_BAR_ZONE_CHIP_MUTED}>{instrument.exchange}</span>
      );
    case "sector":
      return (
        <span className={CHART_BAR_ZONE_CHIP_MUTED}>
          {instrument.sector ?? "—"}
        </span>
      );
    case "listSource":
      return listLabel ? (
        <span className="truncate text-primary">{listLabel}</span>
      ) : (
        <span className={CHART_BAR_ZONE_CHIP_MUTED}>—</span>
      );
    default:
      return null;
  }
}

interface ChartInstrumentZoneProps {
  instrument?: InstrumentDto;
  listLabel?: string;
  className?: string;
}

export function ChartInstrumentZone({
  instrument,
  listLabel,
  className,
}: ChartInstrumentZoneProps) {
  const { favorites, toggleFavorite, isFavorite, anchor } =
    useChartInstrumentFieldFavorites();

  if (!instrument) {
    return (
      <div
        className={cn(CHART_BAR_ZONE_ROW_CLASS, className)}
        title="Metadatos del valor cotizado en este gráfico."
      >
        <ChartBarZoneIconAnchor
          icon={Landmark}
          title="Valor"
          hint="Metadatos del valor cotizado en este gráfico."
          showMenu={false}
          onOpenMenu={() => {}}
        />
      </div>
    );
  }

  return (
    <ChartBarZonePicker
      zoneIcon={Landmark}
      zoneTitle="Valor"
      zoneHint="Metadatos del instrumento: símbolo, nombre, mercado, lista de origen… Icono = menú y favoritos."
      activeId={anchor}
      favorites={favorites}
      menuGroups={CHART_INSTRUMENT_BAR_MENU_GROUPS}
      options={MENU_OPTIONS}
      isFavorite={(id) => id === anchor || isFavorite(id)}
      isFavoriteLocked={(id) => id === anchor}
      onToggleFavorite={toggleFavorite}
      onSelectOption={(id) => {
        if (id !== anchor) toggleFavorite(id);
      }}
      getButtonLabel={(id) =>
        id === "symbol"
          ? instrument.symbol
          : CHART_INSTRUMENT_FIELD_SHORT_LABELS[id]
      }
      renderButtonContent={(id) =>
        renderInstrumentChip(id, instrument, listLabel)
      }
      selectionMode="display"
      className={className}
    />
  );
}
