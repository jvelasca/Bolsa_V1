/**
 * Catálogo unificado de indicadores técnicos (universo canónico).
 *
 * Separación (auditorías + RFC-000/001/005):
 * - Indicator  → familia matemática (`IND-RSI`) — ESTE fichero
 * - Feature    → instancia parametrizada (`feat_rsi_14_close`) — Feature Registry
 * - ChartDef   → representación gráfica (`rsi`) — `indicators-catalog.ts`
 *
 * Dependencia única Feature → Indicator (`indicator_id` = IND-*).
 * Este universo NO lista FeatureDefs ni `featureParityRefs` / `featureFamilyId`.
 *
 * @see docs/CHART_INDICATORS.md
 * @see docs/rfc/001-artifact-catalog.md (lifecycle)
 * @see docs/rfc/005-feature-registry.md
 */

/** Lifecycle alineado a RFC-001 Artifact Catalog. */
export type IndicatorLifecycle =
  | "draft"
  | "planned"
  | "implemented"
  | "validated"
  | "production"
  | "deprecated";

export type IndicatorUniverseCategory =
  | "moving_average"
  | "trend"
  | "momentum"
  | "volatility"
  | "volume"
  | "cycle"
  | "channel"
  | "statistical"
  | "market_structure"
  | "price"
  | "other"
  | "ai_platform";

export type IndicatorInputKind =
  | "ohlcv"
  | "price"
  | "volume"
  | "indicator"
  | "market_data"
  | "macro"
  | "cot"
  | "options"
  | "fundamental"
  | "custom";

export type IndicatorOutputKind =
  | "scalar"
  | "bands"
  | "oscillator"
  | "signal"
  | "multi_series"
  | "histogram"
  | "zones";

/** Forma geométrica para render (UI / export). Independiente de `category`. */
export type IndicatorOutputShape =
  | "single_line"
  | "multi_line"
  | "histogram"
  | "bands"
  | "channel"
  | "scatter"
  | "markers"
  | "signal_only"
  | "polyline"
  | "heatmap";

export type IndicatorScaleType =
  | "price"
  | "percentage"
  | "oscillator"
  | "free"
  | "volume";

export type IndicatorPanelKind = "overlay" | "sub";

export type IndicatorComplexity = "low" | "medium" | "high" | "very_high";

export type IndicatorSupportSurface =
  | "chart"
  | "screener"
  | "feature"
  | "backtest"
  | "alerts"
  | "strategy"
  | "ai";

export interface IndicatorOrigin {
  xtb?: boolean;
  prorealtime?: boolean;
  taLib?: boolean;
  pandasTa?: boolean;
  vectorbt?: boolean;
}

export interface IndicatorUniverseEntry {
  /**
   * Familia matemática / de búsqueda (MOVING_AVERAGE, MACD, RSI…).
   * Varias implementaciones (`IND-SMA`, `IND-EMA`) comparten familia.
   */
  familyId: string;
  /** ID canónico estable de la implementación. Ej. IND-RSI — no cambiar. */
  canonicalId: string;
  name: string;
  /** Código corto tipo XTB (%R, MACD…) si aplica. */
  xtbCode?: string;
  /** Alias / nombres ProRealTime y otros (documentación / búsqueda). */
  prtAliases?: string[];
  category: IndicatorUniverseCategory;
  /** Orígenes formales para filtros (XTB / PRT / TA-Lib…). */
  origin: IndicatorOrigin;
  status: IndicatorLifecycle;
  inputTypes: IndicatorInputKind[];
  outputType: IndicatorOutputKind;
  /** Forma de render (single_line, bands, markers…). */
  outputShape: IndicatorOutputShape;
  /**
   * Claves de salida canónicas (render / Feature Registry / IA).
   * Ej. MACD: macd, signal, histogram · BB: upper, mid, lower.
   */
  outputKeys: string[];
  /** Número de salidas (= outputKeys.length). */
  outputs: number;
  /** Decimales tipicos en UI. */
  displayPrecision: number;
  /** Escala semántica del eje. */
  scaleType: IndicatorScaleType;
  /** Paneles donde tiene sentido mostrar el indicador. */
  supportedPanels: IndicatorPanelKind[];
  /** Panel por defecto. */
  defaultPanel: IndicatorPanelKind;
  /**
   * @deprecated Preferir `defaultPanel` / `supportedPanels`.
   * Se mantiene sincronizado con `defaultPanel` para callers legacy.
   */
  chartPanel?: IndicatorPanelKind;
  /** Dependencias canónicas (p. ej. StochRSI → IND-RSI). */
  dependencies: string[];
  /** Coste relativo de cómputo (IA / realtime). */
  complexity: IndicatorComplexity;
  /** Superficies de producto donde aplica. */
  supports: IndicatorSupportSurface[];
  defaultParams: Record<string, number | boolean | string>;
  /**
   * Id en `IndicatorDefinition` del gráfico (legacy).
   * Vacío si aún no hay UI/compute.
   */
  chartDefinitionId?: string;
  /**
   * Causalidad como feature de backtest/research (semántica F-IND-1).
   *
   * `false` ⇒ la salida usa datos futuros (depende de barras posteriores a `i`):
   * NO puede usarse como feature de señales en backtest (look-ahead). Ej:
   * Ichimoku `chikou` (`bars[i+displacement].close`) y fractals Williams
   * (`bars[index±2]`, centrados en `i-2`).
   *
   * OJO: "dibujado desplazado / visualizationOffset>0" NO equivale a "datos
   * futuros / causal=false". spanA/spanB del Ichimoku se dibujan desplazados
   * 26 barras hacia delante pero usan tenkan/kijun de `i-26` (datos ya
   * disponibles) ⇒ SON causales como feature.
   */
  causal: boolean;
  /**
   * Barras posteriores necesarias para confirmar el valor en la barra `i`.
   * 0 si la salida es causal en la barra actual. Ej. fractal Williams ⇐
   * 2 (se centra en `i-2`, confirma en `i+2`).
   */
  confirmationLag: number;
  /**
   * Desplazamiento de DIBUJO respecto a la barra real (solo visualización).
   * Puede ser >0 sin que el indicador deje de ser causal (ej. spanA/spanB de
   * Ichimoku = 26). NO es un indicador de look-ahead.
   */
  visualizationOffset: number;
  /**
   * Salidas (claves) de este indicador que NO son causales aunque la familia
   * como conjunto lo sea. Ej. Ichimoku: `['chikou']`.
   */
  nonCausalOutputKeys?: string[];
  notes?: string;
}

export const INDICATOR_UNIVERSE_SYNC = {
  asOf: "2026-07-22",
  strategy:
    "Universo IND-* + familyId + metadatos UI/IA; Feature Registry posee instancias (Feature→IND).",
  targets: {
    xtbNativeApprox: 39,
    prtNativeApprox: 100,
    universeTargetApprox: 130,
  },
} as const;

export const INDICATOR_LIFECYCLE_LABEL: Record<IndicatorLifecycle, string> = {
  draft: "Borrador",
  planned: "Planificado",
  implemented: "Implementado",
  validated: "Validado",
  production: "Producción",
  deprecated: "Deprecado",
};

const CHART_READY_SUPPORTS: IndicatorSupportSurface[] = [
  "chart",
  "screener",
  "feature",
  "backtest",
  "alerts",
  "strategy",
  "ai",
];

const PLANNED_SUPPORTS: IndicatorSupportSurface[] = ["chart"];

function defaultFamilyId(
  canonicalId: string,
  category: IndicatorUniverseCategory,
): string {
  if (category === "moving_average") return "MOVING_AVERAGE";
  if (category === "ai_platform") return "AI_PLATFORM";
  if (canonicalId.startsWith("IND-")) return canonicalId.slice(4);
  return canonicalId;
}

function synthesizeOutputKeys(
  count: number,
  outputType: IndicatorOutputKind,
): string[] {
  if (count <= 1) return ["main"];
  if (outputType === "bands" && count === 3) return ["upper", "mid", "lower"];
  if (outputType === "histogram" && count === 1) return ["main"];
  return Array.from({ length: count }, (_, i) =>
    i === 0 ? "main" : `out${i}`,
  );
}

function defaultOutputShape(
  outputType: IndicatorOutputKind,
  outputKeys: string[],
): IndicatorOutputShape {
  switch (outputType) {
    case "bands":
      return "bands";
    case "histogram":
      return "histogram";
    case "signal":
      return outputKeys.length > 1 ? "markers" : "signal_only";
    case "zones":
      return "heatmap";
    case "oscillator":
      return outputKeys.length > 1 ? "multi_line" : "single_line";
    case "multi_series":
      return "multi_line";
    case "scalar":
    default:
      return "single_line";
  }
}

function defaultScaleType(
  outputType: IndicatorOutputKind,
  category: IndicatorUniverseCategory,
): IndicatorScaleType {
  if (category === "volume" || outputType === "histogram") return "volume";
  if (outputType === "oscillator") return "oscillator";
  if (
    category === "moving_average" ||
    category === "channel" ||
    category === "trend"
  ) {
    return "price";
  }
  if (category === "momentum") return "oscillator";
  return "free";
}

function defaultPrecision(
  scaleType: IndicatorScaleType,
  category: IndicatorUniverseCategory,
): number {
  if (scaleType === "volume") return 0;
  if (scaleType === "oscillator" || scaleType === "percentage") return 2;
  if (category === "volatility") return 4;
  if (scaleType === "price") return 4;
  return 2;
}

function defaultComplexity(
  category: IndicatorUniverseCategory,
): IndicatorComplexity {
  if (category === "market_structure") return "high";
  if (category === "ai_platform") return "medium";
  if (category === "moving_average" || category === "volume") return "low";
  return "medium";
}

type EntryInput = Omit<
  IndicatorUniverseEntry,
  | "origin"
  | "inputTypes"
  | "defaultParams"
  | "familyId"
  | "outputKeys"
  | "outputs"
  | "outputShape"
  | "displayPrecision"
  | "scaleType"
  | "supportedPanels"
  | "defaultPanel"
  | "dependencies"
  | "complexity"
  | "supports"
  | "causal"
  | "confirmationLag"
  | "visualizationOffset"
  | "nonCausalOutputKeys"
> & {
  familyId?: string;
  origin?: IndicatorOrigin;
  inputTypes?: IndicatorInputKind[];
  defaultParams?: Record<string, number | boolean | string>;
  outputKeys?: string[];
  outputs?: number;
  outputShape?: IndicatorOutputShape;
  displayPrecision?: number;
  scaleType?: IndicatorScaleType;
  supportedPanels?: IndicatorPanelKind[];
  defaultPanel?: IndicatorPanelKind;
  /** Legacy alias → defaultPanel. */
  chartPanel?: IndicatorPanelKind;
  dependencies?: string[];
  complexity?: IndicatorComplexity;
  supports?: IndicatorSupportSurface[];
  /**
   * Opcionales en la entrada para indicadores `planned`/`draft`, cuyo
   * comportamiento causal aún no se ha confirmado. Al omitirlos se aplica el
   * default de la clase causal. Los indicadores `implemented`/`production`
   * DEBEN declararlos explícitamente conforme a F-IND-1.
   */
  causal?: boolean;
  confirmationLag?: number;
  visualizationOffset?: number;
  nonCausalOutputKeys?: string[];
};

function entry(partial: EntryInput): IndicatorUniverseEntry {
  const {
    origin,
    inputTypes,
    defaultParams,
    familyId,
    outputKeys: explicitKeys,
    outputs: outputCount,
    outputType,
    outputShape: explicitShape,
    displayPrecision: explicitPrecision,
    scaleType: explicitScale,
    supportedPanels: explicitPanels,
    defaultPanel: explicitDefaultPanel,
    chartPanel,
    dependencies,
    complexity: explicitComplexity,
    supports: explicitSupports,
    canonicalId,
    category,
    status,
    causal: causalInput,
    confirmationLag: confirmationLagInput,
    visualizationOffset: visualizationOffsetInput,
    nonCausalOutputKeys,
    ...rest
  } = partial;
  /**
   * Default causal para planned/draft (aún no auditado). Implemented/production
   * lo declaran explícitamente; aquí solo asegura que el tipo de salida sea
   * siempre completo.
   */
  const causal = causalInput ?? true;
  const confirmationLag = confirmationLagInput ?? 0;
  const visualizationOffset = visualizationOffsetInput ?? 0;
  const outputKeys =
    explicitKeys ?? synthesizeOutputKeys(outputCount ?? 1, outputType);
  const scaleType = explicitScale ?? defaultScaleType(outputType, category);
  const defaultPanel = explicitDefaultPanel ?? chartPanel ?? "sub";
  const supportedPanels =
    explicitPanels ??
    (defaultPanel === "overlay"
      ? (["overlay", "sub"] as IndicatorPanelKind[])
      : ["sub"]);
  const ready =
    status === "implemented" ||
    status === "validated" ||
    status === "production";
  return {
    ...rest,
    canonicalId,
    category,
    status,
    outputType,
    familyId: familyId ?? defaultFamilyId(canonicalId, category),
    origin: origin ?? {},
    inputTypes: inputTypes ?? ["ohlcv"],
    defaultParams: defaultParams ?? {},
    outputKeys,
    outputs: outputKeys.length,
    outputShape: explicitShape ?? defaultOutputShape(outputType, outputKeys),
    scaleType,
    displayPrecision:
      explicitPrecision ?? defaultPrecision(scaleType, category),
    supportedPanels,
    defaultPanel,
    chartPanel: defaultPanel,
    dependencies: dependencies ?? [],
    complexity: explicitComplexity ?? defaultComplexity(category),
    supports:
      explicitSupports ?? (ready ? CHART_READY_SUPPORTS : PLANNED_SUPPORTS),
    causal,
    confirmationLag,
    visualizationOffset,
    nonCausalOutputKeys,
  };
}

/**
 * Universo canónico (~XTB + oleadas PRT + plataforma).
 * Ampliar aquí; FeatureDefs nuevos van solo al Feature Registry.
 */
export const INDICATOR_UNIVERSE: IndicatorUniverseEntry[] = [
  // ── Producción (chart + features) ─────────────────────────────────────
  entry({
    canonicalId: "IND-VOL",
    name: "Volume",
    xtbCode: "VOL",
    prtAliases: ["Volume"],
    category: "volume",
    origin: { xtb: true, prorealtime: true, taLib: true, pandasTa: true },
    status: "production",
    causal: true,
    confirmationLag: 0,
    visualizationOffset: 0,
    inputTypes: ["ohlcv", "volume"],
    outputType: "histogram",
    outputShape: "histogram",
    scaleType: "volume",
    displayPrecision: 0,
    complexity: "low",
    outputs: 1,
    chartDefinitionId: "volume",
    chartPanel: "overlay",
  }),
  entry({
    canonicalId: "IND-SMA",
    name: "Simple Moving Average",
    xtbCode: "SMA",
    prtAliases: ["Simple Moving Average (SMA)"],
    category: "moving_average",
    origin: {
      xtb: true,
      prorealtime: true,
      taLib: true,
      pandasTa: true,
      vectorbt: true,
    },
    status: "production",
    causal: true,
    confirmationLag: 0,
    visualizationOffset: 0,
    outputType: "scalar",
    outputs: 1,
    defaultParams: { period: 20 },
    chartDefinitionId: "sma",
    chartPanel: "overlay",
  }),
  entry({
    canonicalId: "IND-EMA",
    name: "Exponential Moving Average",
    xtbCode: "EMA",
    prtAliases: ["Exponential Moving Average (EMA)"],
    category: "moving_average",
    origin: {
      xtb: true,
      prorealtime: true,
      taLib: true,
      pandasTa: true,
      vectorbt: true,
    },
    status: "production",
    causal: true,
    confirmationLag: 0,
    visualizationOffset: 0,
    outputType: "scalar",
    outputs: 1,
    defaultParams: { period: 20 },
    chartDefinitionId: "ema",
    chartPanel: "overlay",
  }),
  entry({
    canonicalId: "IND-LWMA",
    name: "Linear Weighted Moving Average",
    xtbCode: "LWMA",
    prtAliases: [
      "Weighted Moving Average (WMA)",
      "Linear Weighted Moving Average (LWMA)",
    ],
    category: "moving_average",
    origin: { xtb: true, prorealtime: true, taLib: true, pandasTa: true },
    status: "production",
    causal: true,
    confirmationLag: 0,
    visualizationOffset: 0,
    outputType: "scalar",
    outputs: 1,
    defaultParams: { period: 20 },
    chartDefinitionId: "wma",
    chartPanel: "overlay",
    notes: "Chart id legacy `wma` ≡ LWMA/WMA.",
  }),
  entry({
    canonicalId: "IND-BB",
    name: "Bollinger Bands",
    xtbCode: "BB",
    prtAliases: ["Bollinger Bands", "Bollinger Band Width", "Bollinger %B"],
    category: "volatility",
    familyId: "BOLLINGER",
    origin: {
      xtb: true,
      prorealtime: true,
      taLib: true,
      pandasTa: true,
      vectorbt: true,
    },
    status: "production",
    outputType: "bands",
    outputKeys: ["upper", "mid", "lower"],
    outputShape: "bands",
    scaleType: "price",
    displayPrecision: 4,
    complexity: "low",
    causal: true,
    confirmationLag: 0,
    visualizationOffset: 0,
    defaultParams: { period: 20, stdDev: 2 },
    chartDefinitionId: "bb",
    chartPanel: "overlay",
  }),
  entry({
    canonicalId: "IND-RSI",
    name: "Relative Strength Index",
    xtbCode: "RSI",
    prtAliases: ["RSI"],
    category: "momentum",
    familyId: "RSI",
    origin: {
      xtb: true,
      prorealtime: true,
      taLib: true,
      pandasTa: true,
      vectorbt: true,
    },
    status: "production",
    outputType: "oscillator",
    outputKeys: ["main"],
    outputShape: "single_line",
    scaleType: "oscillator",
    displayPrecision: 2,
    complexity: "low",
    causal: true,
    confirmationLag: 0,
    visualizationOffset: 0,
    defaultParams: { period: 14 },
    chartDefinitionId: "rsi",
    chartPanel: "sub",
  }),
  entry({
    canonicalId: "IND-MACD",
    name: "Moving Average Convergence Divergence",
    xtbCode: "MACD",
    prtAliases: ["MACD"],
    category: "momentum",
    familyId: "MACD",
    origin: {
      xtb: true,
      prorealtime: true,
      taLib: true,
      pandasTa: true,
      vectorbt: true,
    },
    status: "production",
    outputType: "multi_series",
    outputKeys: ["macd", "signal", "histogram"],
    outputShape: "multi_line",
    scaleType: "free",
    displayPrecision: 4,
    complexity: "medium",
    causal: true,
    confirmationLag: 0,
    visualizationOffset: 0,
    defaultParams: { fastPeriod: 12, slowPeriod: 26, signalPeriod: 9 },
    chartDefinitionId: "macd",
    chartPanel: "sub",
    notes:
      "Compute chart actual: línea MACD; señal/histograma pendientes de series UI.",
  }),
  entry({
    canonicalId: "IND-SO",
    name: "Stochastic Oscillator",
    xtbCode: "SO",
    prtAliases: ["Stochastic"],
    category: "momentum",
    familyId: "STOCHASTIC",
    origin: { xtb: true, prorealtime: true, taLib: true, pandasTa: true },
    status: "production",
    outputType: "oscillator",
    outputKeys: ["main", "signal"],
    causal: true,
    confirmationLag: 0,
    visualizationOffset: 0,
    defaultParams: { kPeriod: 14, dPeriod: 3 },
    chartDefinitionId: "stoch",
    chartPanel: "sub",
  }),
  entry({
    canonicalId: "IND-ATR",
    name: "Average True Range",
    xtbCode: "ATR",
    prtAliases: ["ATR"],
    category: "volatility",
    origin: {
      xtb: true,
      prorealtime: true,
      taLib: true,
      pandasTa: true,
      vectorbt: true,
    },
    status: "production",
    outputType: "scalar",
    outputs: 1,
    displayPrecision: 4,
    scaleType: "price",
    complexity: "low",
    causal: true,
    confirmationLag: 0,
    visualizationOffset: 0,
    defaultParams: { period: 14 },
    chartDefinitionId: "atr",
    chartPanel: "sub",
  }),
  entry({
    canonicalId: "IND-CCI",
    name: "Commodity Channel Index",
    xtbCode: "CCI",
    prtAliases: ["CCI"],
    category: "momentum",
    origin: { xtb: true, prorealtime: true, taLib: true, pandasTa: true },
    status: "production",
    outputType: "scalar",
    outputs: 1,
    causal: true,
    confirmationLag: 0,
    visualizationOffset: 0,
    defaultParams: { period: 20 },
    chartDefinitionId: "cci",
    chartPanel: "sub",
  }),

  // ── Plataforma / IA ───────────────────────────────────────────────────
  entry({
    canonicalId: "IND-AI-TECH-RATING",
    name: "Technical rating (platform)",
    category: "ai_platform",
    origin: {},
    status: "implemented",
    causal: true,
    confirmationLag: 0,
    visualizationOffset: 0,
    inputTypes: ["ohlcv"],
    outputType: "scalar",
    outputs: 1,
    defaultParams: { warmupBars: 50, showComponents: false },
    chartDefinitionId: "technical_rating_v1",
    chartPanel: "sub",
  }),
  entry({
    canonicalId: "IND-AI-DATA-QUALITY",
    name: "OHLCV data quality",
    category: "ai_platform",
    origin: {},
    status: "implemented",
    causal: true,
    confirmationLag: 0,
    visualizationOffset: 0,
    outputType: "scalar",
    outputs: 1,
    defaultParams: { gapLookback: 90 },
    chartDefinitionId: "bar_data_quality_v1",
    chartPanel: "sub",
  }),
  entry({
    canonicalId: "IND-AI-GLOBAL-SCORE",
    name: "Global AI score",
    category: "ai_platform",
    origin: {},
    status: "implemented",
    causal: true,
    confirmationLag: 0,
    visualizationOffset: 0,
    outputType: "scalar",
    outputs: 1,
    defaultParams: { warmupBars: 50, setupWeight: 70, dataWeight: 30 },
    chartDefinitionId: "ai_global_score_v1",
    chartPanel: "sub",
  }),
  entry({
    canonicalId: "IND-AI-HYBRID-STRATEGY",
    name: "Hybrid strategy score",
    category: "ai_platform",
    origin: {},
    status: "implemented",
    outputType: "multi_series",
    outputKeys: ["main", "minScore", "gate"],
    causal: true,
    confirmationLag: 0,
    visualizationOffset: 0,
    defaultParams: {
      warmupBars: 50,
      minScore: 60,
      showMinScoreLine: true,
      showGateLine: true,
    },
    chartDefinitionId: "strategy_hybrid_score_v1",
    chartPanel: "sub",
  }),

  // ── Oleada 1 XTB (prioridad implementación) ───────────────────────────
  entry({
    canonicalId: "IND-WILLR",
    name: "Williams %R",
    xtbCode: "%R",
    prtAliases: ["Williams %R"],
    category: "momentum",
    origin: { xtb: true, prorealtime: true, taLib: true, pandasTa: true },
    status: "implemented",
    causal: true,
    confirmationLag: 0,
    visualizationOffset: 0,
    outputType: "scalar",
    outputs: 1,
    defaultParams: { period: 14 },
    chartDefinitionId: "willr",
    chartPanel: "sub",
    notes: "Oleada 1 — típico -20 / -80.",
  }),
  entry({
    canonicalId: "IND-MOM",
    name: "Momentum",
    xtbCode: "MOM",
    prtAliases: ["Momentum"],
    category: "momentum",
    origin: { xtb: true, prorealtime: true, taLib: true, pandasTa: true },
    status: "implemented",
    causal: true,
    confirmationLag: 0,
    visualizationOffset: 0,
    outputType: "scalar",
    outputs: 1,
    defaultParams: { period: 10 },
    chartDefinitionId: "mom",
    chartPanel: "sub",
    notes: "Oleada 1.",
  }),
  entry({
    canonicalId: "IND-SD",
    name: "Standard Deviation",
    xtbCode: "SD",
    prtAliases: ["Standard Deviation"],
    category: "statistical",
    origin: { xtb: true, prorealtime: true, taLib: true, pandasTa: true },
    status: "implemented",
    causal: true,
    confirmationLag: 0,
    visualizationOffset: 0,
    outputType: "scalar",
    outputs: 1,
    defaultParams: { period: 20 },
    chartDefinitionId: "sd",
    chartPanel: "sub",
    notes: "Oleada 1.",
  }),
  entry({
    canonicalId: "IND-DC",
    name: "Donchian Channel",
    xtbCode: "DC",
    prtAliases: ["Donchian Channel", "Price Channel"],
    category: "channel",
    familyId: "DONCHIAN",
    origin: { xtb: true, prorealtime: true, pandasTa: true },
    status: "implemented",
    outputType: "bands",
    outputKeys: ["upper", "mid", "lower"],
    outputShape: "channel",
    scaleType: "price",
    displayPrecision: 4,
    complexity: "low",
    causal: true,
    confirmationLag: 0,
    visualizationOffset: 0,
    defaultParams: { period: 20 },
    chartDefinitionId: "dc",
    chartPanel: "overlay",
    notes: "Oleada 1.",
  }),

  // ── Resto XTB (planned) ───────────────────────────────────────────────
  entry({
    canonicalId: "IND-ACC",
    name: "Accelerator Oscillator",
    xtbCode: "ACC",
    prtAliases: ["Accelerator Oscillator"],
    category: "momentum",
    origin: { xtb: true, prorealtime: true },
    status: "planned",
    outputType: "histogram",
    outputs: 1,
    chartPanel: "sub",
  }),
  entry({
    canonicalId: "IND-ADX",
    name: "Average Directional Movement Index",
    xtbCode: "ADX",
    prtAliases: ["ADX", "DMI"],
    category: "trend",
    familyId: "ADX",
    origin: { xtb: true, prorealtime: true, taLib: true, pandasTa: true },
    status: "implemented",
    outputType: "multi_series",
    outputKeys: ["main", "plus_di", "minus_di"],
    outputShape: "multi_line",
    scaleType: "oscillator",
    displayPrecision: 1,
    complexity: "medium",
    causal: true,
    confirmationLag: 0,
    visualizationOffset: 0,
    defaultParams: { period: 14 },
    chartDefinitionId: "adx",
    chartPanel: "sub",
    notes: "Oleada 2 — ADX +DI −DI.",
  }),
  entry({
    canonicalId: "IND-ALI",
    name: "Alligator",
    xtbCode: "ALI",
    prtAliases: ["Alligator"],
    category: "trend",
    familyId: "ALLIGATOR",
    origin: { xtb: true, prorealtime: true },
    status: "implemented",
    outputType: "multi_series",
    outputKeys: ["jaw", "teeth", "lips"],
    outputShape: "multi_line",
    scaleType: "price",
    complexity: "medium",
    causal: true,
    confirmationLag: 0,
    visualizationOffset: 0,
    chartDefinitionId: "ali",
    chartPanel: "overlay",
    notes: "Oleada 3.",
  }),
  entry({
    canonicalId: "IND-AWE",
    name: "Awesome Oscillator",
    xtbCode: "AWE",
    prtAliases: ["Awesome Oscillator"],
    category: "momentum",
    origin: { xtb: true, prorealtime: true },
    status: "planned",
    outputType: "histogram",
    outputs: 1,
    chartPanel: "sub",
  }),
  entry({
    canonicalId: "IND-BEARS",
    name: "Bears Power",
    xtbCode: "BEARS",
    prtAliases: ["Bears Power", "Elder Ray"],
    category: "momentum",
    origin: { xtb: true, prorealtime: true },
    status: "implemented",
    outputType: "scalar",
    outputs: 1,
    scaleType: "free",
    complexity: "low",
    causal: true,
    confirmationLag: 0,
    visualizationOffset: 0,
    defaultParams: { period: 13 },
    chartDefinitionId: "bears",
    chartPanel: "sub",
    notes: "Oleada 3 — Elder Ray.",
  }),
  entry({
    canonicalId: "IND-BULLS",
    name: "Bulls Power",
    xtbCode: "BULLS",
    prtAliases: ["Bulls Power", "Elder Ray"],
    category: "momentum",
    origin: { xtb: true, prorealtime: true },
    status: "implemented",
    outputType: "scalar",
    outputs: 1,
    scaleType: "free",
    complexity: "low",
    causal: true,
    confirmationLag: 0,
    visualizationOffset: 0,
    defaultParams: { period: 13 },
    chartDefinitionId: "bulls",
    chartPanel: "sub",
    notes: "Oleada 3 — Elder Ray.",
  }),
  entry({
    canonicalId: "IND-COT",
    name: "Commitments of Traders",
    xtbCode: "COT",
    category: "other",
    origin: { xtb: true },
    status: "planned",
    inputTypes: ["cot"],
    outputType: "multi_series",
    outputs: 2,
    notes: "Requiere fuente COT.",
  }),
  entry({
    canonicalId: "IND-CT",
    name: "Curtis Theory",
    xtbCode: "CT",
    category: "other",
    origin: { xtb: true },
    status: "draft",
    outputType: "scalar",
    outputs: 1,
    notes: "Propietario XTB — validar fórmula pública.",
  }),
  entry({
    canonicalId: "IND-ENV",
    name: "Envelopes",
    xtbCode: "ENV",
    prtAliases: ["Envelopes"],
    category: "volatility",
    origin: { xtb: true, prorealtime: true },
    status: "planned",
    outputType: "bands",
    outputs: 2,
    defaultParams: { period: 20, percent: 2.5 },
    chartPanel: "overlay",
  }),
  entry({
    canonicalId: "IND-FR",
    name: "Fractals",
    xtbCode: "FR",
    prtAliases: ["Fractals"],
    category: "trend",
    origin: { xtb: true, prorealtime: true },
    status: "implemented",
    causal: false,
    confirmationLag: 2,
    visualizationOffset: 0,
    outputType: "signal",
    outputKeys: ["up", "down"],
    outputShape: "markers",
    scaleType: "price",
    complexity: "medium",
    chartDefinitionId: "fr",
    chartPanel: "overlay",
    notes: "Oleada 3.",
  }),
  entry({
    canonicalId: "IND-HMA",
    name: "Hull Moving Average",
    xtbCode: "HMA",
    prtAliases: ["Hull Moving Average"],
    category: "moving_average",
    origin: { xtb: true, prorealtime: true, pandasTa: true },
    status: "planned",
    outputType: "scalar",
    outputs: 1,
    defaultParams: { period: 20 },
    chartPanel: "overlay",
  }),
  entry({
    canonicalId: "IND-ICH",
    name: "Ichimoku",
    xtbCode: "ICH",
    prtAliases: ["Ichimoku"],
    category: "trend",
    familyId: "ICHIMOKU",
    origin: { xtb: true, prorealtime: true, pandasTa: true },
    status: "implemented",
    // Familia causal: tenkan/kijun/spanA/spanB usan datos de `i-26` (ya disponibles).
    // Solo `chikou` NO es causal (escribe `bars[i+26].close`, datos futuros).
    causal: true,
    confirmationLag: 0,
    visualizationOffset: 26, // desplazamiento solo de DIBUJO; no implica look-ahead
    nonCausalOutputKeys: ["chikou"],
    outputType: "multi_series",
    outputKeys: ["tenkan", "kijun", "spanA", "spanB", "chikou"],
    outputShape: "multi_line",
    scaleType: "price",
    displayPrecision: 4,
    complexity: "medium",
    defaultParams: {
      tenkanPeriod: 9,
      kijunPeriod: 26,
      senkouBPeriod: 52,
      displacement: 26,
    },
    chartDefinitionId: "ich",
    chartPanel: "overlay",
    notes: "Oleada 3.",
  }),
  entry({
    canonicalId: "IND-KEL",
    name: "Keltner Channel",
    xtbCode: "KEL",
    prtAliases: ["Keltner Channel"],
    category: "channel",
    origin: { xtb: true, prorealtime: true, pandasTa: true },
    status: "planned",
    outputType: "bands",
    outputs: 3,
    defaultParams: { period: 20, atrPeriod: 10, multiplier: 2 },
    chartPanel: "overlay",
  }),
  entry({
    canonicalId: "IND-MAR",
    name: "Moving Average Ribbon",
    xtbCode: "MAR",
    prtAliases: ["Moving Average Ribbon", "Rainbow Moving Average"],
    category: "moving_average",
    origin: { xtb: true, prorealtime: true },
    status: "planned",
    outputType: "multi_series",
    outputs: 6,
    chartPanel: "overlay",
  }),
  entry({
    canonicalId: "IND-PIVOT",
    name: "Pivot Points",
    xtbCode: "PIVOT",
    prtAliases: ["Pivot Points"],
    category: "market_structure",
    origin: { xtb: true, prorealtime: true },
    status: "planned",
    outputType: "zones",
    outputs: 7,
    chartPanel: "overlay",
  }),
  entry({
    canonicalId: "IND-SAR",
    name: "Parabolic SAR",
    xtbCode: "SAR",
    prtAliases: ["Parabolic SAR"],
    category: "trend",
    origin: { xtb: true, prorealtime: true, taLib: true, pandasTa: true },
    status: "implemented",
    outputType: "signal",
    outputs: 1,
    outputShape: "markers",
    scaleType: "price",
    complexity: "medium",
    causal: true,
    confirmationLag: 0,
    visualizationOffset: 0,
    defaultParams: { step: 0.02, maxAf: 0.2 },
    chartDefinitionId: "sar",
    chartPanel: "overlay",
    notes: "Oleada 3.",
  }),
  entry({
    canonicalId: "IND-SEA",
    name: "Seasonality",
    xtbCode: "SEA",
    prtAliases: ["Seasonality"],
    category: "other",
    origin: { xtb: true, prorealtime: true },
    status: "planned",
    inputTypes: ["ohlcv", "market_data"],
    outputType: "multi_series",
    outputs: 1,
  }),
  entry({
    canonicalId: "IND-SEAHIST",
    name: "Seasonality Histogram",
    xtbCode: "SEAHIST",
    category: "other",
    origin: { xtb: true },
    status: "planned",
    outputType: "histogram",
    outputs: 1,
  }),
  entry({
    canonicalId: "IND-SMMA",
    name: "Smoothed Moving Average",
    xtbCode: "SMMA",
    prtAliases: ["Smoothed Moving Average"],
    category: "moving_average",
    origin: { xtb: true, prorealtime: true },
    status: "planned",
    outputType: "scalar",
    outputs: 1,
    defaultParams: { period: 20 },
    chartPanel: "overlay",
  }),
  entry({
    canonicalId: "IND-SRSI",
    name: "Stochastic RSI",
    xtbCode: "SRSI",
    prtAliases: ["Stochastic RSI"],
    category: "momentum",
    familyId: "STOCHASTIC_RSI",
    origin: { xtb: true, prorealtime: true, pandasTa: true },
    status: "implemented",
    inputTypes: ["ohlcv", "indicator"],
    outputType: "oscillator",
    outputKeys: ["main", "signal"],
    outputShape: "multi_line",
    scaleType: "oscillator",
    displayPrecision: 2,
    complexity: "medium",
    causal: true,
    confirmationLag: 0,
    visualizationOffset: 0,
    dependencies: ["IND-RSI"],
    defaultParams: { rsiPeriod: 14, stochPeriod: 14, kPeriod: 3, dPeriod: 3 },
    chartDefinitionId: "srsi",
    chartPanel: "sub",
    notes: "Oleada 2.",
  }),
  entry({
    canonicalId: "IND-ST",
    name: "SuperTrend",
    xtbCode: "ST",
    prtAliases: ["SuperTrend"],
    category: "trend",
    familyId: "SUPERTREND",
    origin: { xtb: true, prorealtime: true, pandasTa: true },
    status: "implemented",
    outputType: "signal",
    outputKeys: ["main"],
    outputShape: "signal_only",
    scaleType: "price",
    displayPrecision: 4,
    complexity: "medium",
    causal: true,
    confirmationLag: 0,
    visualizationOffset: 0,
    supportedPanels: ["overlay", "sub"],
    defaultParams: { atrPeriod: 10, multiplier: 3 },
    chartDefinitionId: "st",
    chartPanel: "overlay",
    notes: "Oleada 2.",
  }),
  entry({
    canonicalId: "IND-TDI",
    name: "Traders Dynamic Index",
    xtbCode: "TDI",
    category: "momentum",
    origin: { xtb: true },
    status: "planned",
    outputType: "multi_series",
    outputs: 4,
    chartPanel: "sub",
  }),
  entry({
    canonicalId: "IND-TRIX",
    name: "TRIX",
    xtbCode: "TRIX",
    prtAliases: ["TRIX"],
    category: "trend",
    origin: { xtb: true, prorealtime: true, taLib: true },
    status: "planned",
    outputType: "scalar",
    outputs: 1,
    defaultParams: { period: 15 },
    chartPanel: "sub",
  }),
  entry({
    canonicalId: "IND-VD",
    name: "Volume Distribution",
    xtbCode: "VD",
    prtAliases: ["Volume Profile"],
    category: "volume",
    origin: { xtb: true, prorealtime: true },
    status: "planned",
    inputTypes: ["ohlcv", "volume"],
    outputType: "histogram",
    outputs: 1,
  }),
  entry({
    canonicalId: "IND-VWAP",
    name: "Volume Weighted Average Price",
    xtbCode: "VWAP",
    prtAliases: ["VWAP"],
    category: "volume",
    origin: { xtb: true, prorealtime: true, pandasTa: true, vectorbt: true },
    status: "implemented",
    inputTypes: ["ohlcv", "volume"],
    outputType: "scalar",
    outputs: 1,
    outputShape: "single_line",
    scaleType: "price",
    displayPrecision: 4,
    complexity: "medium",
    causal: true,
    confirmationLag: 0,
    visualizationOffset: 0,
    supportedPanels: ["overlay", "sub"],
    chartDefinitionId: "vwap",
    chartPanel: "overlay",
    notes: "Oleada 2 — VWAP acumulado desde el inicio de la serie.",
  }),
  entry({
    canonicalId: "IND-ZZ",
    name: "ZigZag",
    xtbCode: "ZZ",
    prtAliases: ["ZigZag"],
    category: "trend",
    origin: { xtb: true, prorealtime: true },
    status: "planned",
    outputType: "signal",
    outputs: 1,
    outputShape: "polyline",
    scaleType: "price",
    complexity: "medium",
    chartPanel: "overlay",
  }),

  // ── Oleada PRT / librerías (horizonte) ────────────────────────────────
  entry({
    canonicalId: "IND-ROC",
    name: "Rate of Change",
    prtAliases: ["ROC"],
    category: "momentum",
    origin: { prorealtime: true, taLib: true, pandasTa: true },
    status: "implemented",
    causal: true,
    confirmationLag: 0,
    visualizationOffset: 0,
    outputType: "scalar",
    outputs: 1,
    complexity: "low",
    defaultParams: { period: 12 },
    chartDefinitionId: "roc",
    chartPanel: "sub",
    notes: "Oleada 3 prioritaria (cuant / screener).",
  }),
  entry({
    canonicalId: "IND-OBV",
    name: "On Balance Volume",
    prtAliases: ["OBV"],
    category: "volume",
    origin: { prorealtime: true, taLib: true, pandasTa: true },
    status: "implemented",
    causal: true,
    confirmationLag: 0,
    visualizationOffset: 0,
    inputTypes: ["ohlcv", "volume"],
    outputType: "scalar",
    outputs: 1,
    complexity: "low",
    chartDefinitionId: "obv",
    chartPanel: "sub",
    notes: "Oleada 3 prioritaria (cuant / screener).",
  }),
  entry({
    canonicalId: "IND-CMF",
    name: "Chaikin Money Flow",
    prtAliases: ["Chaikin Money Flow"],
    category: "volume",
    origin: { prorealtime: true, pandasTa: true },
    status: "planned",
    inputTypes: ["ohlcv", "volume"],
    outputType: "scalar",
    outputs: 1,
    defaultParams: { period: 20 },
    chartPanel: "sub",
  }),
  entry({
    canonicalId: "IND-ADL",
    name: "Accumulation / Distribution",
    prtAliases: ["Accumulation / Distribution"],
    category: "volume",
    origin: { prorealtime: true, taLib: true },
    status: "planned",
    inputTypes: ["ohlcv", "volume"],
    outputType: "scalar",
    outputs: 1,
    chartPanel: "sub",
  }),
  entry({
    canonicalId: "IND-FI",
    name: "Force Index",
    prtAliases: ["Force Index", "Elder Force Index"],
    category: "volume",
    origin: { prorealtime: true },
    status: "planned",
    inputTypes: ["ohlcv", "volume"],
    outputType: "scalar",
    outputs: 1,
    defaultParams: { period: 13 },
    chartPanel: "sub",
  }),
  entry({
    canonicalId: "IND-EOM",
    name: "Ease of Movement",
    prtAliases: ["Ease of Movement"],
    category: "volume",
    origin: { prorealtime: true },
    status: "planned",
    inputTypes: ["ohlcv", "volume"],
    outputType: "scalar",
    outputs: 1,
    chartPanel: "sub",
  }),
  entry({
    canonicalId: "IND-MFI",
    name: "Money Flow Index",
    prtAliases: ["Money Flow Index"],
    category: "volume",
    origin: { prorealtime: true, taLib: true, pandasTa: true },
    status: "implemented",
    causal: true,
    confirmationLag: 0,
    visualizationOffset: 0,
    inputTypes: ["ohlcv", "volume"],
    outputType: "oscillator",
    outputs: 1,
    scaleType: "oscillator",
    defaultParams: { period: 14 },
    chartDefinitionId: "mfi",
    chartPanel: "sub",
    notes: "Oleada 3 prioritaria (cuant / screener).",
  }),
  entry({
    canonicalId: "IND-UO",
    name: "Ultimate Oscillator",
    prtAliases: ["Ultimate Oscillator"],
    category: "momentum",
    origin: { prorealtime: true, taLib: true },
    status: "planned",
    outputType: "scalar",
    outputs: 1,
    chartPanel: "sub",
  }),
  entry({
    canonicalId: "IND-TSI",
    name: "True Strength Index",
    prtAliases: ["TSI"],
    category: "momentum",
    origin: { prorealtime: true },
    status: "planned",
    outputType: "scalar",
    outputs: 1,
    chartPanel: "sub",
  }),
  entry({
    canonicalId: "IND-CMO",
    name: "Chande Momentum Oscillator",
    prtAliases: ["Chande Momentum Oscillator"],
    category: "momentum",
    origin: { prorealtime: true },
    status: "planned",
    outputType: "scalar",
    outputs: 1,
    chartPanel: "sub",
  }),
  entry({
    canonicalId: "IND-DEM",
    name: "DeMarker",
    prtAliases: ["DeMarker"],
    category: "momentum",
    origin: { prorealtime: true },
    status: "planned",
    outputType: "scalar",
    outputs: 1,
    chartPanel: "sub",
  }),
  entry({
    canonicalId: "IND-AROON",
    name: "Aroon",
    prtAliases: ["Aroon", "Aroon Oscillator"],
    category: "trend",
    origin: { prorealtime: true, taLib: true, pandasTa: true },
    status: "implemented",
    outputType: "multi_series",
    outputKeys: ["up", "down"],
    outputShape: "multi_line",
    scaleType: "oscillator",
    causal: true,
    confirmationLag: 0,
    visualizationOffset: 0,
    defaultParams: { period: 25 },
    chartDefinitionId: "aroon",
    chartPanel: "sub",
    notes: "Oleada 3 prioritaria (cuant / screener).",
  }),
  entry({
    canonicalId: "IND-VORTEX",
    name: "Vortex",
    prtAliases: ["Vortex"],
    category: "trend",
    origin: { prorealtime: true, pandasTa: true },
    status: "planned",
    outputType: "multi_series",
    outputs: 2,
    chartPanel: "sub",
  }),
  entry({
    canonicalId: "IND-KST",
    name: "Know Sure Thing",
    prtAliases: ["KST", "Know Sure Thing"],
    category: "trend",
    origin: { prorealtime: true },
    status: "planned",
    outputType: "multi_series",
    outputs: 2,
    chartPanel: "sub",
  }),
  entry({
    canonicalId: "IND-KAMA",
    name: "Kaufman Adaptive Moving Average",
    prtAliases: ["Adaptive Moving Average (KAMA)"],
    category: "moving_average",
    origin: { prorealtime: true, taLib: true, pandasTa: true },
    status: "planned",
    outputType: "scalar",
    outputs: 1,
    defaultParams: { period: 10 },
    chartPanel: "overlay",
  }),
  entry({
    canonicalId: "IND-DEMA",
    name: "Double Exponential Moving Average",
    prtAliases: ["DEMA"],
    category: "moving_average",
    origin: { prorealtime: true, taLib: true },
    status: "planned",
    outputType: "scalar",
    outputs: 1,
    defaultParams: { period: 20 },
    chartPanel: "overlay",
  }),
  entry({
    canonicalId: "IND-TEMA",
    name: "Triple Exponential Moving Average",
    prtAliases: ["TEMA"],
    category: "moving_average",
    origin: { prorealtime: true, taLib: true },
    status: "planned",
    outputType: "scalar",
    outputs: 1,
    defaultParams: { period: 20 },
    chartPanel: "overlay",
  }),
  entry({
    canonicalId: "IND-ZLEMA",
    name: "Zero Lag Exponential Moving Average",
    prtAliases: ["Zero Lag Moving Average"],
    category: "moving_average",
    origin: { prorealtime: true },
    status: "planned",
    outputType: "scalar",
    outputs: 1,
    chartPanel: "overlay",
  }),
  entry({
    canonicalId: "IND-TYPPRICE",
    name: "Typical Price",
    prtAliases: ["Typical Price"],
    category: "price",
    origin: { prorealtime: true, taLib: true },
    status: "planned",
    outputType: "scalar",
    outputs: 1,
    chartPanel: "overlay",
  }),
  entry({
    canonicalId: "IND-MEDPRICE",
    name: "Median Price",
    prtAliases: ["Median Price"],
    category: "price",
    origin: { prorealtime: true, taLib: true },
    status: "planned",
    outputType: "scalar",
    outputs: 1,
    chartPanel: "overlay",
  }),
  entry({
    canonicalId: "IND-WCLPRICE",
    name: "Weighted Close",
    prtAliases: ["Weighted Close"],
    category: "price",
    origin: { prorealtime: true, taLib: true },
    status: "planned",
    outputType: "scalar",
    outputs: 1,
    chartPanel: "overlay",
  }),
  entry({
    canonicalId: "IND-AVGPRICE",
    name: "Average Price",
    prtAliases: ["Average Price"],
    category: "price",
    origin: { prorealtime: true, taLib: true },
    status: "planned",
    outputType: "scalar",
    outputs: 1,
    chartPanel: "overlay",
  }),
  entry({
    canonicalId: "IND-LINREG",
    name: "Linear Regression",
    prtAliases: ["Linear Regression", "Regression Channel"],
    category: "statistical",
    origin: { prorealtime: true, taLib: true },
    status: "planned",
    outputType: "bands",
    outputs: 3,
    chartPanel: "overlay",
  }),
  entry({
    canonicalId: "IND-CORR",
    name: "Correlation",
    prtAliases: ["Correlation"],
    category: "statistical",
    origin: { prorealtime: true },
    status: "planned",
    inputTypes: ["ohlcv", "market_data"],
    outputType: "scalar",
    outputs: 1,
    chartPanel: "sub",
  }),
  entry({
    canonicalId: "IND-BETA",
    name: "Beta",
    prtAliases: ["Beta"],
    category: "statistical",
    origin: { prorealtime: true },
    status: "planned",
    inputTypes: ["ohlcv", "market_data"],
    outputType: "scalar",
    outputs: 1,
    chartPanel: "sub",
  }),
];

export function indicatorUniverseByCanonicalId(
  id: string,
): IndicatorUniverseEntry | undefined {
  return INDICATOR_UNIVERSE.find((e) => e.canonicalId === id);
}

export function indicatorUniverseByChartId(
  chartDefinitionId: string,
): IndicatorUniverseEntry | undefined {
  return INDICATOR_UNIVERSE.find(
    (e) => e.chartDefinitionId === chartDefinitionId,
  );
}

export function indicatorUniverseByXtbCode(
  code: string,
): IndicatorUniverseEntry | undefined {
  const normalized = code.trim().toUpperCase();
  return INDICATOR_UNIVERSE.find(
    (e) => e.xtbCode?.toUpperCase() === normalized,
  );
}

/** Familia matemática (MOVING_AVERAGE → SMA/EMA/WMA…). */
export function indicatorUniverseByFamily(
  familyId: string,
): IndicatorUniverseEntry[] {
  return INDICATOR_UNIVERSE.filter((e) => e.familyId === familyId);
}

/** Filtro por origen formal (xtb, prorealtime, taLib…). */
export function indicatorUniverseByOrigin(
  key: keyof IndicatorOrigin,
): IndicatorUniverseEntry[] {
  return INDICATOR_UNIVERSE.filter((e) => Boolean(e.origin[key]));
}

/** Resuelve id de gráfico para compute/UI a partir de IND-* o id legacy. */
export function resolveChartDefinitionId(ref: string): string | undefined {
  if (!ref.startsWith("IND-")) return ref;
  return indicatorUniverseByCanonicalId(ref)?.chartDefinitionId;
}

export function summarizeIndicatorUniverse(): {
  total: number;
  byStatus: Record<IndicatorLifecycle, number>;
  families: number;
  xtbCoded: number;
  xtbReady: number;
  withChart: number;
} {
  const byStatus = {
    draft: 0,
    planned: 0,
    implemented: 0,
    validated: 0,
    production: 0,
    deprecated: 0,
  } satisfies Record<IndicatorLifecycle, number>;
  const families = new Set<string>();
  for (const item of INDICATOR_UNIVERSE) {
    byStatus[item.status] += 1;
    families.add(item.familyId);
  }
  const xtb = INDICATOR_UNIVERSE.filter((e) => e.origin.xtb);
  const ready = new Set<IndicatorLifecycle>([
    "implemented",
    "validated",
    "production",
  ]);
  return {
    total: INDICATOR_UNIVERSE.length,
    byStatus,
    families: families.size,
    xtbCoded: xtb.length,
    xtbReady: xtb.filter((e) => ready.has(e.status)).length,
    withChart: INDICATOR_UNIVERSE.filter((e) => e.chartDefinitionId).length,
  };
}
