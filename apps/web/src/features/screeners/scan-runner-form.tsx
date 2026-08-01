import {
  BACKTEST_STRATEGIES,
  CATALOG_IBEX_LIST_ID,
  DEFAULT_HYBRID_MIN_SCORE,
  DEFAULT_HYBRID_MIN_DATA_QUALITY,
  HYBRID_GATE_PRESET_KEYS,
  KERNEL_TIMEFRAMES,
  STRATEGY_PRESET_CATEGORY_LABELS,
  presetsByCategory,
  scanFieldsFromFundamentalGate,
  strategyDefinitionFromHybrid,
  type BacktestStrategyType,
  type KernelTimeframe,
  type StrategyDefinitionDetailDto,
  type UpsertStrategyDefinitionDto,
} from '@bolsa/shared';

export type ScanSource = 'preset' | 'saved';
export type ScanMode = 'classic' | 'hybrid';

export interface ScanRunnerConfig {
  scanMode: ScanMode;
  scanSource: ScanSource;
  presetKey: BacktestStrategyType;
  savedStrategyId: string;
  listId: string;
  maxResults: number;
  timeframe: KernelTimeframe;
  hybridGatePresetKey: BacktestStrategyType;
  hybridMinScore: number;
  hybridMinDataQuality: number;
  hybridMaxTrailingPe: number | null;
  hybridMinMarketCapMillions: number | null;
  /** Ratio 0–1 (0.15 = 15%). */
  hybridMinRoe: number | null;
  hybridMaxDebtToEquity: number | null;
  hybridMinCurrentRatio: number | null;
  hybridMinAltmanZ: number | null;
  /** Ratio 0–1. */
  hybridMinFcfYield: number | null;
  hybridMinOperatingMargin: number | null;
  hybridMinRevenueGrowth: number | null;
  hybridMinPiotroski: number | null;
  hybridMinDcfUpside: number | null;
  hybridMinGrahamUpside: number | null;
  /** F2.2 — umbrales por sector en evaluación. */
  hybridUseSectorBands: boolean;
}

export interface ScanRunnerFormProps {
  config: ScanRunnerConfig;
  onChange: (patch: Partial<ScanRunnerConfig>) => void;
  lists: Array<{ id: string; name: string; itemCount: number; source: string }>;
  strategies: Array<{ id: string; name: string }>;
  compact?: boolean;
}

export function defaultScanRunnerConfig(): ScanRunnerConfig {
  return {
    scanMode: 'classic',
    scanSource: 'preset',
    presetKey: 'sma_crossover',
    savedStrategyId: '',
    listId: CATALOG_IBEX_LIST_ID,
    maxResults: 50,
    timeframe: '1d',
    hybridGatePresetKey: 'price_above_sma200',
    hybridMinScore: DEFAULT_HYBRID_MIN_SCORE,
    hybridMinDataQuality: DEFAULT_HYBRID_MIN_DATA_QUALITY,
    hybridMaxTrailingPe: null,
    hybridMinMarketCapMillions: null,
    hybridMinRoe: null,
    hybridMaxDebtToEquity: null,
    hybridMinCurrentRatio: null,
    hybridMinAltmanZ: null,
    hybridMinFcfYield: null,
    hybridMinOperatingMargin: null,
    hybridMinRevenueGrowth: null,
    hybridMinPiotroski: null,
    hybridMinDcfUpside: null,
    hybridMinGrahamUpside: null,
    hybridUseSectorBands: false,
  };
}

export function ScanRunnerForm({
  config,
  onChange,
  lists,
  strategies,
  compact = false,
}: ScanRunnerFormProps) {
  const presetGroups = presetsByCategory();
  const selectedList = lists.find((list) => list.id === config.listId);
  const fieldClass = compact
    ? 'mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm'
    : 'mt-1 w-full rounded-md border border-border bg-background px-3 py-2';

  return (
    <div className={compact ? 'space-y-3 text-sm' : 'grid gap-4 md:grid-cols-2'}>
      <label className={compact ? 'block' : 'block md:col-span-1'}>
        Lista
        <select
          value={config.listId}
          onChange={(e) => onChange({ listId: e.target.value })}
          className={fieldClass}
        >
          <option value="">Selecciona lista...</option>
          {lists.map((list) => (
            <option key={list.id} value={list.id}>
              {list.name} ({list.itemCount})
            </option>
          ))}
        </select>
        {selectedList && (
          <p className="mt-1 text-xs text-muted-foreground">
            {selectedList.itemCount} instrumentos · {selectedList.source}
          </p>
        )}
      </label>

      <label className={compact ? 'block' : 'block md:col-span-1'}>
        Timeframe
        <select
          value={config.timeframe}
          onChange={(e) => onChange({ timeframe: e.target.value as KernelTimeframe })}
          className={fieldClass}
        >
          {KERNEL_TIMEFRAMES.map((tf) => (
            <option key={tf} value={tf}>
              {tf === '1d' ? '1 día' : '1 semana'}
            </option>
          ))}
        </select>
      </label>

      <fieldset className={compact ? 'space-y-2' : 'space-y-2 md:col-span-2'}>
        <legend className="text-xs font-medium text-muted-foreground">Modo de rastreo</legend>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="radio"
            checked={config.scanMode === 'classic'}
            onChange={() => onChange({ scanMode: 'classic' })}
          />
          Clásico (señal en última barra)
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="radio"
            checked={config.scanMode === 'hybrid'}
            onChange={() => onChange({ scanMode: 'hybrid', scanSource: 'preset' })}
          />
          Híbrido IA (filtro + rating técnico)
        </label>
      </fieldset>

      {config.scanMode === 'hybrid' ? (
        <div className={compact ? 'space-y-3 md:col-span-2' : 'grid gap-4 md:col-span-2 md:grid-cols-2'}>
          <label className="block">
            Filtro previo (gate)
            <select
              value={config.hybridGatePresetKey}
              onChange={(e) =>
                onChange({ hybridGatePresetKey: e.target.value as BacktestStrategyType })
              }
              className={fieldClass}
            >
              {HYBRID_GATE_PRESET_KEYS.map((key) => (
                <option key={key} value={key}>
                  {BACKTEST_STRATEGIES[key].label}
                </option>
              ))}
            </select>
            <p className="mt-1 text-xs text-muted-foreground">
              {BACKTEST_STRATEGIES[config.hybridGatePresetKey].description}
            </p>
          </label>
          <label className="block">
            Rating mínimo ({config.hybridMinScore})
            <input
              type="range"
              min={40}
              max={85}
              step={5}
              value={config.hybridMinScore}
              onChange={(e) => onChange({ hybridMinScore: Number(e.target.value) })}
              className="mt-2 w-full"
            />
            <p className="mt-1 text-xs text-muted-foreground">
              Ordena por score técnico v1 (tendencia, momentum, volatilidad, reversión).
            </p>
          </label>
          <label className="block">
            Calidad datos mínima ({config.hybridMinDataQuality || 'off'})
            <input
              type="range"
              min={0}
              max={80}
              step={5}
              value={config.hybridMinDataQuality}
              onChange={(e) => onChange({ hybridMinDataQuality: Number(e.target.value) })}
              className="mt-2 w-full"
            />
            <p className="mt-1 text-xs text-muted-foreground">
              0 = sin filtro. Filtra por frescura OHLCV, sync e integridad de barras.
            </p>
          </label>
          <label className="block">
            PER trailing máx. (opcional)
            <input
              type="number"
              min={0}
              step={1}
              placeholder="Ej. 25"
              value={config.hybridMaxTrailingPe ?? ''}
              onChange={(e) =>
                onChange({
                  hybridMaxTrailingPe: e.target.value ? Number(e.target.value) : null,
                })
              }
              className={fieldClass}
            />
          </label>
          <label className="block">
            Cap. mínima en M€ (opcional)
            <input
              type="number"
              min={0}
              step={100}
              placeholder="Ej. 1000"
              value={config.hybridMinMarketCapMillions ?? ''}
              onChange={(e) =>
                onChange({
                  hybridMinMarketCapMillions: e.target.value ? Number(e.target.value) : null,
                })
              }
              className={fieldClass}
            />
          </label>
          <label className="block">
            ROE mín. (ratio, opc.)
            <input
              type="number"
              min={0}
              step={0.01}
              placeholder="Ej. 0.15 (=15%)"
              value={config.hybridMinRoe ?? ''}
              onChange={(e) =>
                onChange({ hybridMinRoe: e.target.value ? Number(e.target.value) : null })
              }
              className={fieldClass}
            />
          </label>
          <label className="block">
            D/E máx. (opc.)
            <input
              type="number"
              min={0}
              step={0.1}
              placeholder="Ej. 1.5"
              value={config.hybridMaxDebtToEquity ?? ''}
              onChange={(e) =>
                onChange({
                  hybridMaxDebtToEquity: e.target.value ? Number(e.target.value) : null,
                })
              }
              className={fieldClass}
            />
          </label>
          <label className="block">
            Altman Z mín. (opc.)
            <input
              type="number"
              min={0}
              step={0.1}
              placeholder="Ej. 2.99"
              value={config.hybridMinAltmanZ ?? ''}
              onChange={(e) =>
                onChange({ hybridMinAltmanZ: e.target.value ? Number(e.target.value) : null })
              }
              className={fieldClass}
            />
          </label>
          <label className="block">
            FCF Yield mín. (ratio, opc.)
            <input
              type="number"
              min={0}
              step={0.005}
              placeholder="Ej. 0.03 (=3%)"
              value={config.hybridMinFcfYield ?? ''}
              onChange={(e) =>
                onChange({ hybridMinFcfYield: e.target.value ? Number(e.target.value) : null })
              }
              className={fieldClass}
            />
          </label>
          <label className="block">
            Current ratio mín. (opc.)
            <input
              type="number"
              min={0}
              step={0.1}
              placeholder="Ej. 1.2"
              value={config.hybridMinCurrentRatio ?? ''}
              onChange={(e) =>
                onChange({
                  hybridMinCurrentRatio: e.target.value ? Number(e.target.value) : null,
                })
              }
              className={fieldClass}
            />
          </label>
          <label className="block">
            Piotroski F mín. (0–9, opc.)
            <input
              type="number"
              min={0}
              max={9}
              step={1}
              placeholder="Ej. 7"
              value={config.hybridMinPiotroski ?? ''}
              onChange={(e) =>
                onChange({
                  hybridMinPiotroski: e.target.value ? Number(e.target.value) : null,
                })
              }
              className={fieldClass}
            />
            <p className="mt-1 text-[10px] text-muted-foreground">
              Solo filtra valores con F-Score completo en snapshot (si falta YoY, quedan fuera).
            </p>
          </label>
          <label className="block">
            DCF upside mín. (ratio, opc.)
            <input
              type="number"
              step={0.05}
              placeholder="Ej. 0.2 (=+20%)"
              value={config.hybridMinDcfUpside ?? ''}
              onChange={(e) =>
                onChange({
                  hybridMinDcfUpside: e.target.value ? Number(e.target.value) : null,
                })
              }
              className={fieldClass}
            />
            <p className="mt-1 text-[10px] text-muted-foreground">
              Modelo FCF 2 etapas (r=10%, g_term=2.5%). Null si FCF≤0.
            </p>
          </label>
          <label className="block">
            Graham upside mín. (ratio, opc.)
            <input
              type="number"
              step={0.05}
              placeholder="Ej. 0.15"
              value={config.hybridMinGrahamUpside ?? ''}
              onChange={(e) =>
                onChange({
                  hybridMinGrahamUpside: e.target.value ? Number(e.target.value) : null,
                })
              }
              className={fieldClass}
            />
          </label>
          <label className="flex items-start gap-2 md:col-span-2">
            <input
              type="checkbox"
              className="mt-1"
              checked={config.hybridUseSectorBands}
              onChange={(e) => onChange({ hybridUseSectorBands: e.target.checked })}
            />
            <span>
              Umbrales por sector (F2.2)
              <p className="mt-1 text-[10px] text-muted-foreground">
                Ajusta PE/ROE/D/E/Altman… según el sector Yahoo. En Financial Services se omiten
                Altman/D/E. Sin sector conocido usa los números de arriba (o defaults del catálogo).
              </p>
            </span>
          </label>
        </div>
      ) : (
      <fieldset className={compact ? 'space-y-2' : 'space-y-2 md:col-span-2'}>
        <legend className="text-xs font-medium text-muted-foreground">Estrategia</legend>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="radio"
            checked={config.scanSource === 'preset'}
            onChange={() => onChange({ scanSource: 'preset' })}
          />
          Preset
        </label>
        {config.scanSource === 'preset' && (
          <select
            value={config.presetKey}
            onChange={(e) => onChange({ presetKey: e.target.value as BacktestStrategyType })}
            className="ml-6 w-[calc(100%-1.5rem)] rounded-md border border-border bg-background px-3 py-2 text-sm"
          >
            {(Object.keys(STRATEGY_PRESET_CATEGORY_LABELS) as Array<
              keyof typeof STRATEGY_PRESET_CATEGORY_LABELS
            >).map((category) => {
              const items = presetGroups[category];
              if (items.length === 0) return null;
              return (
                <optgroup key={category} label={STRATEGY_PRESET_CATEGORY_LABELS[category]}>
                  {items.map((item) => (
                    <option key={item.key} value={item.key} title={item.description}>
                      {item.label}
                    </option>
                  ))}
                </optgroup>
              );
            })}
          </select>
        )}
        <label className="flex items-center gap-2 text-sm">
          <input
            type="radio"
            checked={config.scanSource === 'saved'}
            onChange={() => onChange({ scanSource: 'saved' })}
          />
          Guardada
        </label>
        {config.scanSource === 'saved' && (
          <select
            value={config.savedStrategyId}
            onChange={(e) => onChange({ savedStrategyId: e.target.value })}
            className="ml-6 w-[calc(100%-1.5rem)] rounded-md border border-border bg-background px-3 py-2 text-sm"
          >
            <option value="">Selecciona...</option>
            {strategies.map((strategy) => (
              <option key={strategy.id} value={strategy.id}>
                {strategy.name}
              </option>
            ))}
          </select>
        )}
      </fieldset>
      )}

      <label className={compact ? 'block' : 'block md:col-span-1'}>
        Máx. resultados
        <input
          type="number"
          min={1}
          max={500}
          value={config.maxResults}
          onChange={(e) => onChange({ maxResults: Number(e.target.value) || 50 })}
          className={fieldClass}
        />
      </label>
    </div>
  );
}

export function scanRequestFromConfig(config: ScanRunnerConfig) {
  const base = {
    universe: { listId: config.listId },
    maxResults: config.maxResults,
    timeframe: config.timeframe,
  };

  if (config.scanMode === 'hybrid') {
    const gateLabel = BACKTEST_STRATEGIES[config.hybridGatePresetKey].label;
    return {
      ...base,
      definition: strategyDefinitionFromHybrid({
        name: `Híbrido · ${gateLabel} · ≥${config.hybridMinScore}`,
        gatePresetKey: config.hybridGatePresetKey,
        minScore: config.hybridMinScore,
        instrumentIds: [],
        timeframe: config.timeframe,
        maxTrailingPe: config.hybridMaxTrailingPe,
        minMarketCapMillions: config.hybridMinMarketCapMillions,
        minRoe: config.hybridMinRoe,
        maxDebtToEquity: config.hybridMaxDebtToEquity,
        minCurrentRatio: config.hybridMinCurrentRatio,
        minAltmanZ: config.hybridMinAltmanZ,
        minFcfYield: config.hybridMinFcfYield,
        minOperatingMargin: config.hybridMinOperatingMargin,
        minRevenueGrowth: config.hybridMinRevenueGrowth,
        minPiotroski: config.hybridMinPiotroski,
        minDcfUpside: config.hybridMinDcfUpside,
        minGrahamUpside: config.hybridMinGrahamUpside,
        useSectorBands: config.hybridUseSectorBands,
        minDataQuality: config.hybridMinDataQuality,
      }),
    };
  }

  return {
    ...base,
    ...(config.scanSource === 'saved'
      ? { strategyDefinitionId: config.savedStrategyId }
      : { presetKey: config.presetKey }),
  };
}

export function canRunScan(config: ScanRunnerConfig): boolean {
  if (!config.listId) return false;
  if (config.scanMode === 'hybrid') return Boolean(config.hybridGatePresetKey);
  return config.scanSource === 'preset' || Boolean(config.savedStrategyId);
}

export function strategyUpsertFromScanConfig(
  config: ScanRunnerConfig,
  name: string,
): UpsertStrategyDefinitionDto | null {
  if (config.scanMode !== 'hybrid') return null;
  const gateLabel = BACKTEST_STRATEGIES[config.hybridGatePresetKey].label;
  return {
    name: name.trim(),
    definition: strategyDefinitionFromHybrid({
      name: `Híbrido · ${gateLabel} · ≥${config.hybridMinScore}`,
      gatePresetKey: config.hybridGatePresetKey,
      minScore: config.hybridMinScore,
      instrumentIds: [],
      timeframe: config.timeframe,
      maxTrailingPe: config.hybridMaxTrailingPe,
      minMarketCapMillions: config.hybridMinMarketCapMillions,
      minRoe: config.hybridMinRoe,
      maxDebtToEquity: config.hybridMaxDebtToEquity,
      minCurrentRatio: config.hybridMinCurrentRatio,
      minAltmanZ: config.hybridMinAltmanZ,
      minFcfYield: config.hybridMinFcfYield,
      minOperatingMargin: config.hybridMinOperatingMargin,
      minRevenueGrowth: config.hybridMinRevenueGrowth,
      minPiotroski: config.hybridMinPiotroski,
      minDcfUpside: config.hybridMinDcfUpside,
      minGrahamUpside: config.hybridMinGrahamUpside,
      useSectorBands: config.hybridUseSectorBands,
      minDataQuality: config.hybridMinDataQuality,
    }),
  };
}

export function scanConfigFromStrategyDefinition(
  strategy: StrategyDefinitionDetailDto,
  base: Partial<ScanRunnerConfig> = {},
): ScanRunnerConfig {
  const config: ScanRunnerConfig = { ...defaultScanRunnerConfig(), ...base };
  if (strategy.kind === 'hybrid' && strategy.definition.hybrid) {
    const hybrid = strategy.definition.hybrid;
    const fundamentalFields = scanFieldsFromFundamentalGate(hybrid.fundamentalGate);
    return {
      ...config,
      scanMode: 'hybrid',
      scanSource: 'saved',
      savedStrategyId: strategy.id,
      hybridGatePresetKey: hybrid.gatePresetKey ?? config.hybridGatePresetKey,
      hybridMinScore: hybrid.aiScorer?.minScore ?? DEFAULT_HYBRID_MIN_SCORE,
      hybridMinDataQuality: hybrid.minDataQuality ?? DEFAULT_HYBRID_MIN_DATA_QUALITY,
      ...fundamentalFields,
    };
  }
  return {
    ...config,
    scanMode: 'classic',
    scanSource: 'saved',
    savedStrategyId: strategy.id,
    presetKey: strategy.presetKey ?? config.presetKey,
  };
}
