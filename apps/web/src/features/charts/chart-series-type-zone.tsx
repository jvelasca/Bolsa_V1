import {
  CHART_SERIES_TYPE_MENU_GROUPS,
  CHART_SERIES_TYPE_OPTIONS,
  findChartSeriesTypeOption,
  isChartSeriesTypeImplemented,
  type ChartSeriesType,
} from '@bolsa/shared';
import { ChartCandlestick } from 'lucide-react';

import { ChartBarZonePicker } from '@/features/charts/chart-bar-zone-picker';
import { useChartSeriesTypeFavorites } from '@/features/charts/use-chart-series-type-favorites';

const SERIES_TYPE_OPTIONS = Object.fromEntries(
  Object.values(CHART_SERIES_TYPE_OPTIONS).map((option) => [
    option.id,
    {
      id: option.id,
      label: isChartSeriesTypeImplemented(option.id)
        ? option.label
        : `${option.label} (próximamente)`,
      hint: option.description ?? option.label,
    },
  ]),
) as Record<ChartSeriesType, { id: ChartSeriesType; label: string; hint: string }>;

export function ChartSeriesTypeZone({
  seriesType,
  onSeriesTypeChange,
  className,
}: {
  seriesType: ChartSeriesType;
  onSeriesTypeChange: (next: ChartSeriesType) => void;
  className?: string;
}) {
  const { favorites, toggleFavorite, isFavorite } = useChartSeriesTypeFavorites();

  return (
    <ChartBarZonePicker
      zoneIcon={ChartCandlestick}
      zoneTitle="Estilo"
      zoneHint="Tipo de barra o traza. Icono muestra el estilo activo; estrella = chip opcional."
      activeId={seriesType}
      favorites={favorites}
      menuGroups={CHART_SERIES_TYPE_MENU_GROUPS}
      options={SERIES_TYPE_OPTIONS}
      isFavorite={isFavorite}
      onToggleFavorite={toggleFavorite}
      onSelectOption={(id) => {
        if (isChartSeriesTypeImplemented(id)) onSeriesTypeChange(id);
      }}
      getButtonLabel={(id) => findChartSeriesTypeOption(id).shortLabel}
      isOptionDisabled={(id) => !isChartSeriesTypeImplemented(id)}
      isButtonVisible={(id) => isChartSeriesTypeImplemented(id)}
      className={className}
    />
  );
}
