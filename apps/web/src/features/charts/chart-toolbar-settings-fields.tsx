import type { ChartToolbarGlobalConfig } from "@bolsa/shared";
import {
  CHART_CURSOR_BAR_ANCHOR,
  CHART_CURSOR_FIELD_LABELS,
  CHART_INSTRUMENT_BAR_ANCHOR,
  CHART_INSTRUMENT_FIELD_LABELS,
  CHART_SERIES_TYPE_MENU,
  CHART_TIMEFRAME_OPTIONS,
  CHART_TOOLBAR_CHART_VISIBILITY_LABELS,
  DEFAULT_CHART_CURSOR_FIELD_FAVORITES,
  DEFAULT_CHART_INSTRUMENT_FIELD_FAVORITES,
  DEFAULT_CHART_SERIES_TYPE_FAVORITES,
  DEFAULT_CHART_TIMEFRAME_FAVORITES,
  DEFAULT_INDICATOR_TEMPLATE_FAVORITES,
  findChartSeriesTypeOption,
  findChartTimeframeOption,
  isChartSeriesTypeImplemented,
  type ChartCursorBarField,
  type ChartInstrumentBarField,
  type ChartSeriesType,
  type ChartTimeframe,
} from "@bolsa/shared";

import { Button } from "@/components/ui/button";
import { FieldRow, checkboxClassName } from "@/components/ui/dialog";

export function ColorField({
  value,
  transparentLabel = "Transparente",
  onChange,
}: {
  value: string;
  transparentLabel?: string;
  onChange: (value: string) => void;
}) {
  const isTransparent = value === "transparent";
  return (
    <div className="flex items-center gap-2">
      <input
        type="color"
        className="h-9 w-12 cursor-pointer rounded border border-border bg-background"
        value={isTransparent ? "#1e293b" : value}
        disabled={isTransparent}
        onChange={(event) => onChange(event.target.value)}
      />
      <label className="flex items-center gap-2 text-xs">
        <input
          type="checkbox"
          className={checkboxClassName}
          checked={isTransparent}
          onChange={(event) =>
            onChange(event.target.checked ? "transparent" : "#1e293b")
          }
        />
        {transparentLabel}
      </label>
    </div>
  );
}

export function FavoritesWorkspaceSection({
  draft,
  onChange,
}: {
  draft: ChartToolbarGlobalConfig;
  onChange: (next: ChartToolbarGlobalConfig) => void;
}) {
  function resetFavorites() {
    onChange({
      ...draft,
      timeframeFavorites: [...DEFAULT_CHART_TIMEFRAME_FAVORITES],
      seriesTypeFavorites: [...DEFAULT_CHART_SERIES_TYPE_FAVORITES],
      indicatorTemplateFavorites: [...DEFAULT_INDICATOR_TEMPLATE_FAVORITES],
      instrumentFieldFavorites: [...DEFAULT_CHART_INSTRUMENT_FIELD_FAVORITES],
      cursorFieldFavorites: [...DEFAULT_CHART_CURSOR_FIELD_FAVORITES],
    });
  }

  return (
    <section className="space-y-3">
      <div>
        <p className="text-xs font-medium text-foreground">
          Accesos directos (favoritos)
        </p>
        <p className="mt-1 text-[11px] text-muted-foreground">
          El icono de cada zona muestra el valor activo (p. ej. 1D, Velas). Usa
          la <strong>estrella</strong> en el menú para fijar chips de acceso
          rápido opcionales.
        </p>
      </div>

      <div className="space-y-2 rounded-md border border-border bg-muted/10 p-2 text-[11px]">
        <p className="font-medium text-foreground">Escala</p>
        <p className="text-muted-foreground">
          {draft.timeframeFavorites.length > 0
            ? draft.timeframeFavorites
                .map((tf) => findChartTimeframeOption(tf).label)
                .join(" · ")
            : "Sin chips (solo icono con escala activa)"}
        </p>
        <p className="font-medium text-foreground">Estilo</p>
        <p className="text-muted-foreground">
          {draft.seriesTypeFavorites.length > 0
            ? draft.seriesTypeFavorites
                .map((id) => findChartSeriesTypeOption(id).shortLabel)
                .join(" · ")
            : "Sin chips (solo icono con estilo activo)"}
        </p>
        <p className="font-medium text-foreground">Plantillas</p>
        <p className="text-muted-foreground">
          {draft.indicatorTemplateFavorites.length > 0
            ? `${draft.indicatorTemplateFavorites.length} chip(s)`
            : "Sin chips (solo icono con plantilla activa)"}
        </p>
        <p className="font-medium text-foreground">Valor</p>
        <p className="text-muted-foreground">
          {draft.instrumentFieldFavorites
            .filter((id) => id !== CHART_INSTRUMENT_BAR_ANCHOR)
            .map(
              (id) =>
                CHART_INSTRUMENT_FIELD_LABELS[id as ChartInstrumentBarField],
            )
            .join(" · ") || "Solo ancla"}
        </p>
        <p className="font-medium text-foreground">Cursor</p>
        <p className="text-muted-foreground">
          {draft.cursorFieldFavorites
            .filter((id) => id !== CHART_CURSOR_BAR_ANCHOR)
            .map((id) => CHART_CURSOR_FIELD_LABELS[id as ChartCursorBarField])
            .join(" · ") || "Solo ancla"}
        </p>
      </div>

      <Button
        type="button"
        variant="outline"
        size="sm"
        onClick={resetFavorites}
      >
        Restaurar favoritos por defecto
      </Button>
    </section>
  );
}

export function DefaultTimeframeSelect({
  value,
  onChange,
}: {
  value: ChartTimeframe;
  onChange: (timeframe: ChartTimeframe) => void;
}) {
  return (
    <select
      className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
      value={value}
      onChange={(event) => onChange(event.target.value as ChartTimeframe)}
    >
      {CHART_TIMEFRAME_OPTIONS.map((option) => (
        <option key={option.id} value={option.id}>
          {option.label}
        </option>
      ))}
    </select>
  );
}

export function DefaultSeriesTypeSelect({
  value,
  onChange,
}: {
  value: ChartSeriesType;
  onChange: (seriesType: ChartSeriesType) => void;
}) {
  const options = CHART_SERIES_TYPE_MENU.filter(
    (entry): entry is { kind: "type"; id: ChartSeriesType } =>
      entry.kind === "type" && isChartSeriesTypeImplemented(entry.id),
  );
  return (
    <select
      className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
      value={value}
      onChange={(event) => onChange(event.target.value as ChartSeriesType)}
    >
      {options.map((entry) => (
        <option key={entry.id} value={entry.id}>
          {findChartSeriesTypeOption(entry.id).label}
        </option>
      ))}
    </select>
  );
}

/** Defaults del workspace para la barra de datos (gráficos nuevos y herencia). */
export function DataBarWorkspaceDefaultsSection({
  draft,
  onChange,
}: {
  draft: ChartToolbarGlobalConfig;
  onChange: (next: ChartToolbarGlobalConfig) => void;
}) {
  return (
    <section className="space-y-3">
      <div>
        <p className="text-xs font-medium text-foreground">
          Defaults del workspace
        </p>
        <p className="mt-1 text-[11px] text-muted-foreground">
          Valores que heredan los gráficos nuevos y los tabs con «usar valores
          por defecto».
        </p>
      </div>

      <FieldRow label="Timeframe inicial (Escala)">
        <DefaultTimeframeSelect
          value={draft.defaultTimeframe}
          onChange={(defaultTimeframe) =>
            onChange({ ...draft, defaultTimeframe })
          }
        />
      </FieldRow>

      <FieldRow label="Estilo inicial (tipo de barra)">
        <DefaultSeriesTypeSelect
          value={draft.defaultSeriesType}
          onChange={(defaultSeriesType) =>
            onChange({ ...draft, defaultSeriesType })
          }
        />
      </FieldRow>

      <FieldRow label="Fondo de la barra de datos">
        <ColorField
          value={draft.appearance.chartBarBackground}
          onChange={(chartBarBackground) =>
            onChange({
              ...draft,
              appearance: { ...draft.appearance, chartBarBackground },
            })
          }
        />
      </FieldRow>

      <div className="space-y-2">
        <p className="text-xs font-medium text-foreground">
          Distribución por defecto
        </p>
        <label className="flex items-center gap-2 text-xs">
          <input
            type="checkbox"
            className={checkboxClassName}
            checked={draft.chartLayoutDefaults.wrapRows}
            onChange={() =>
              onChange({
                ...draft,
                chartLayoutDefaults: {
                  ...draft.chartLayoutDefaults,
                  wrapRows: !draft.chartLayoutDefaults.wrapRows,
                },
              })
            }
          />
          Apilar zonas en varias filas si no caben (sin scroll horizontal)
        </label>
      </div>

      <div className="space-y-2">
        <p className="text-xs font-medium text-foreground">
          Visibilidad por defecto
        </p>
        <div className="grid grid-cols-2 gap-1.5">
          {(
            Object.keys(CHART_TOOLBAR_CHART_VISIBILITY_LABELS) as Array<
              keyof typeof CHART_TOOLBAR_CHART_VISIBILITY_LABELS
            >
          )
            .filter((key) => key !== "settingsButton")
            .map((key) => (
              <label key={key} className="flex items-center gap-2 text-xs">
                <input
                  type="checkbox"
                  className={checkboxClassName}
                  checked={draft.chartVisibilityDefaults[key]}
                  onChange={() =>
                    onChange({
                      ...draft,
                      chartVisibilityDefaults: {
                        ...draft.chartVisibilityDefaults,
                        [key]: !draft.chartVisibilityDefaults[key],
                      },
                    })
                  }
                />
                {CHART_TOOLBAR_CHART_VISIBILITY_LABELS[key]}
              </label>
            ))}
        </div>
      </div>
    </section>
  );
}
