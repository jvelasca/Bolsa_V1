import type { ChartStrategySetupDraft, ChartTimeframe } from "@bolsa/shared";
import {
  PERIOD_PRESET_OPTIONS,
  effectiveDiaD,
  isDiaDInPast,
  type PeriodPreset,
} from "@/features/backtests/backtest-period";
import { BacktestChartImportPanel } from "@/features/backtests/backtest-chart-import-panel";
import type { UniverseMode } from "@/features/backtests/backtest-hub-nav";
import { formatNumber } from "@/lib/format";

interface BacktestWizardAdvancedOptionsProps {
  periodPreset: PeriodPreset;
  onPeriodPresetChange: (next: PeriodPreset) => void;
  customDateFrom: string;
  onCustomDateFromChange: (next: string) => void;
  customDateTo: string;
  onCustomDateToChange: (next: string) => void;
  initialCash: string;
  onInitialCashChange: (next: string) => void;
  runTimeframe: ChartTimeframe;
  onRunTimeframeChange: (next: ChartTimeframe) => void;
  commissionBps: string;
  onCommissionBpsChange: (next: string) => void;
  slippageBps: string;
  onSlippageBpsChange: (next: string) => void;
  diaD: string | null | undefined;
  universeMode: UniverseMode;
  onApplyChartDraft: (draft: ChartStrategySetupDraft) => void;
  onSaveStrategy: (draft: ChartStrategySetupDraft, name: string) => void;
  isSaving: boolean;
}

/** «Opciones avanzadas» del wizard de backtesting: periodo/capital/timeframe/
 * costes + importación desde el gráfico activo. Extraído de `backtests-page.tsx`
 * (feature-slicing F4.8) sin cambiar la semántica de hooks/handlers del padre:
 * transpone los setters inline a callbacks. */
export function BacktestWizardAdvancedOptions({
  periodPreset,
  onPeriodPresetChange,
  customDateFrom,
  onCustomDateFromChange,
  customDateTo,
  onCustomDateToChange,
  initialCash,
  onInitialCashChange,
  runTimeframe,
  onRunTimeframeChange,
  commissionBps,
  onCommissionBpsChange,
  slippageBps,
  onSlippageBpsChange,
  diaD,
  universeMode,
  onApplyChartDraft,
  onSaveStrategy,
  isSaving,
}: BacktestWizardAdvancedOptionsProps) {
  const cashDisplay = formatNumber(Number(initialCash || 0));
  return (
    <details className="rounded-md border border-border/60 bg-muted/15">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-2 px-2.5 py-1.5 text-[11px] text-muted-foreground marker:content-none [&::-webkit-details-marker]:hidden">
        <span className="font-medium text-foreground/80">
          Opciones avanzadas
        </span>
        <span className="min-w-0 truncate tabular-nums opacity-80">
          {isDiaDInPast(diaD) ? `DÍA D ${effectiveDiaD(diaD)} · ` : ""}
          {PERIOD_PRESET_OPTIONS.find((o) => o.value === periodPreset)?.label ??
            periodPreset}
          {" · "}
          {cashDisplay} €{" · "}
          {runTimeframe}
          {(Number(commissionBps) > 0 || Number(slippageBps) > 0) &&
            ` · ${commissionBps}/${slippageBps} bps`}
        </span>
      </summary>
      <div className="space-y-2.5 border-t border-border/50 px-2.5 py-2.5">
        <label
          className="block text-[11px] font-medium"
          title="Para análisis con IA: usa todo el historial sincronizado (máx. 10 000 velas). Un solo año sirve para humo rápido, pero overfittea fácil. Luego puedes validar en un subperiodo (p. ej. último año)."
        >
          Periodo
          <select
            value={periodPreset}
            onChange={(e) =>
              onPeriodPresetChange(e.target.value as PeriodPreset)
            }
            className="mt-1 w-full rounded-md border border-border bg-background px-2 py-1.5 text-xs"
          >
            {PERIOD_PRESET_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </label>
        {isDiaDInPast(diaD) ? (
          <p className="rounded border border-red-600/50 bg-red-600/10 px-2 py-1 text-[10px] font-medium leading-snug text-red-800 dark:text-red-300">
            Periodo anclado a DÍA D {effectiveDiaD(diaD)} (no al calendario de
            hoy).
          </p>
        ) : null}
        {periodPreset === "1y" && (
          <p className="text-[10px] leading-snug text-amber-700 dark:text-amber-400">
            Periodo corto: útil para una prueba rápida; no basta para declarar
            una estrategia sólida. Mejor «Todo el historial» o ≥3–5 años.
          </p>
        )}
        {periodPreset === "custom" && (
          <div className="grid grid-cols-2 gap-2">
            <label className="block text-[11px] font-medium">
              Desde
              <input
                type="date"
                value={customDateFrom}
                onChange={(e) => onCustomDateFromChange(e.target.value)}
                className="mt-1 w-full rounded-md border border-border bg-background px-2 py-1.5 text-xs"
              />
            </label>
            <label className="block text-[11px] font-medium">
              Hasta
              <input
                type="date"
                value={customDateTo}
                onChange={(e) => onCustomDateToChange(e.target.value)}
                className="mt-1 w-full rounded-md border border-border bg-background px-2 py-1.5 text-xs"
              />
            </label>
          </div>
        )}

        <label
          className="block text-[11px] font-medium"
          title="Dinero virtual al empezar cada prueba. En una lista, CADA valor arranca con ese mismo capital (no se reparte). En cada compra se invierte casi todo el efectivo disponible (acciones enteras); al vender, el resultado vuelve a caja y la siguiente compra reinvierte ese capital actualizado."
        >
          Capital inicial (€)
          <input
            type="text"
            inputMode="numeric"
            pattern="[0-9]*"
            name="bolsa-backtest-initial-cash"
            autoComplete="off"
            autoCorrect="off"
            autoCapitalize="off"
            spellCheck={false}
            list="bolsa-no-cash-suggestions"
            value={initialCash}
            onChange={(e) => {
              onInitialCashChange(e.target.value.replace(/[^\d]/g, ""));
            }}
            className="mt-1 w-full rounded-md border border-border bg-background px-2 py-1.5 text-xs"
          />
          <datalist id="bolsa-no-cash-suggestions" />
        </label>
        <p className="text-[10px] leading-snug text-muted-foreground">
          {universeMode === "list"
            ? `Cada valor simula aparte con ${cashDisplay} € (no es cartera multi-activo).`
            : "Compra = máximo de acciones enteras; venta = vuelve a caja (reinversión)."}
        </p>

        <label
          className="block text-[11px] font-medium"
          title="Frecuencia de las velas. Diario (1d) es el más habitual."
        >
          Timeframe
          <select
            value={runTimeframe}
            onChange={(e) =>
              onRunTimeframeChange(e.target.value as ChartTimeframe)
            }
            className="mt-1 w-full rounded-md border border-border bg-background px-2 py-1.5 text-xs"
          >
            <option value="1d">1 día</option>
            <option value="1h">1 hora</option>
            <option value="4h">4 horas</option>
            <option value="1wk">1 semana</option>
          </select>
        </label>

        <div className="grid grid-cols-2 gap-2">
          <label
            className="block text-[11px] font-medium"
            title="Coste por operación en puntos básicos (1 bps = 0,01%)."
          >
            Comisión (bps)
            <input
              type="number"
              min="0"
              step="1"
              value={commissionBps}
              onChange={(e) => onCommissionBpsChange(e.target.value)}
              className="mt-1 w-full rounded-md border border-border bg-background px-2 py-1.5 text-xs"
            />
          </label>
          <label
            className="block text-[11px] font-medium"
            title="Deslizamiento de precio al ejecutar la orden, en puntos básicos."
          >
            Slippage (bps)
            <input
              type="number"
              min="0"
              step="1"
              value={slippageBps}
              onChange={(e) => onSlippageBpsChange(e.target.value)}
              className="mt-1 w-full rounded-md border border-border bg-background px-2 py-1.5 text-xs"
            />
          </label>
        </div>

        <BacktestChartImportPanel
          onApply={onApplyChartDraft}
          onSaveStrategy={onSaveStrategy}
          isSaving={isSaving}
        />
      </div>
    </details>
  );
}
