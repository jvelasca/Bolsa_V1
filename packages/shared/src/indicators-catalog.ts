import type { ChartDisplayConfig } from './chart-defaults.js';
import { AI_INDICATOR_DEFINITIONS } from './ai-indicators-catalog.js';
import {
  findInstanceBySpec,
  instanceSpecKey,
  parametersKey,
} from './indicators-runtime.js';

export type IndicatorCategory = 'trend' | 'momentum' | 'volume' | 'volatility' | 'custom';
export type IndicatorPanel = 'overlay' | 'sub';
export type IndicatorSource = 'builtin' | 'custom' | 'ai';

export interface IndicatorParamSchema {
  id: string;
  label: string;
  type: 'number' | 'boolean' | 'color' | 'select';
  default: number | boolean | string;
  min?: number;
  max?: number;
  step?: number;
  /** Agrupa parámetros en formularios complejos (fase backtest). */
  group?: string;
  description?: string;
  /** Opciones para type === 'select'. */
  options?: { value: string | number; label: string }[];
  /** Marca parámetros iterables en optimización/backtest (fase 2). */
  backtestIterable?: boolean;
}

export interface IndicatorDefinition {
  id: string;
  name: string;
  shortLabel: string;
  description: string;
  category: IndicatorCategory;
  panel: IndicatorPanel;
  source: IndicatorSource;
  parameters: IndicatorParamSchema[];
}

export interface ChartIndicatorInstance {
  instanceId: string;
  /** Preset de catálogo del que deriva (si aplica). */
  presetId?: string;
  definitionId: string;
  parameters: Record<string, number | boolean | string>;
  visible: boolean;
  /** Zoom vertical del panel secundario (1 = 100%). */
  scaleZoom?: number;
  /** Reparto vertical entre paneles inferiores visibles (% relativo, suma ≈ 100). */
  subPanelWeight?: number;
  /** Muestra el último valor en la escala de precios (derecha). */
  showLastValue?: boolean;
  /** Grosor de línea (1–4) en gráfico principal o sub-panel. */
  lineWidth?: number;
}

export const BUILTIN_INDICATORS: IndicatorDefinition[] = [
  {
    id: 'volume',
    name: 'Volumen',
    shortLabel: 'Vol',
    description: 'Histograma de volumen bajo las velas.',
    category: 'volume',
    panel: 'overlay',
    source: 'builtin',
    parameters: [],
  },
  {
    id: 'sma',
    name: 'Media móvil simple (SMA)',
    shortLabel: 'SMA',
    description: 'Media aritmética del cierre en N periodos.',
    category: 'trend',
    panel: 'overlay',
    source: 'builtin',
    parameters: [
      { id: 'period', label: 'Periodo', type: 'number', default: 20, min: 2, max: 200 },
    ],
  },
  {
    id: 'ema',
    name: 'Media móvil exponencial (EMA)',
    shortLabel: 'EMA',
    description: 'Media ponderada exponencial del cierre.',
    category: 'trend',
    panel: 'overlay',
    source: 'builtin',
    parameters: [
      { id: 'period', label: 'Periodo', type: 'number', default: 20, min: 2, max: 200 },
    ],
  },
  {
    id: 'rsi',
    name: 'Índice de fuerza relativa (RSI)',
    shortLabel: 'RSI',
    description: 'Oscilador de momentum en panel inferior.',
    category: 'momentum',
    panel: 'sub',
    source: 'builtin',
    parameters: [
      { id: 'period', label: 'Periodo', type: 'number', default: 14, min: 2, max: 100 },
    ],
  },
  {
    id: 'wma',
    name: 'Media móvil ponderada (WMA)',
    shortLabel: 'WMA',
    description: 'Media ponderada por volumen reciente del cierre.',
    category: 'trend',
    panel: 'overlay',
    source: 'builtin',
    parameters: [
      { id: 'period', label: 'Periodo', type: 'number', default: 20, min: 2, max: 200 },
    ],
  },
  {
    id: 'bb',
    name: 'Bandas de Bollinger',
    shortLabel: 'BB',
    description: 'Bandas de volatilidad alrededor de una SMA.',
    category: 'volatility',
    panel: 'overlay',
    source: 'builtin',
    parameters: [
      { id: 'period', label: 'Periodo', type: 'number', default: 20, min: 2, max: 200 },
      { id: 'stdDev', label: 'Desv. típica', type: 'number', default: 2, min: 0.5, max: 4, step: 0.5 },
    ],
  },
  {
    id: 'macd',
    name: 'MACD',
    shortLabel: 'MACD',
    description: 'Convergencia/divergencia de medias — línea MACD en panel inferior.',
    category: 'momentum',
    panel: 'sub',
    source: 'builtin',
    parameters: [
      { id: 'fastPeriod', label: 'Rápida', type: 'number', default: 12, min: 2, max: 50 },
      { id: 'slowPeriod', label: 'Lenta', type: 'number', default: 26, min: 2, max: 100 },
      { id: 'signalPeriod', label: 'Señal', type: 'number', default: 9, min: 2, max: 50 },
    ],
  },
  {
    id: 'stoch',
    name: 'Estocástico',
    shortLabel: 'Stoch',
    description: 'Oscilador %K en panel inferior.',
    category: 'momentum',
    panel: 'sub',
    source: 'builtin',
    parameters: [
      { id: 'kPeriod', label: 'Periodo %K', type: 'number', default: 14, min: 2, max: 100 },
      { id: 'dPeriod', label: 'Suavizado %D', type: 'number', default: 3, min: 1, max: 20 },
    ],
  },
  {
    id: 'atr',
    name: 'Average True Range (ATR)',
    shortLabel: 'ATR',
    description: 'Rango verdadero medio — volatilidad.',
    category: 'volatility',
    panel: 'sub',
    source: 'builtin',
    parameters: [
      { id: 'period', label: 'Periodo', type: 'number', default: 14, min: 2, max: 100 },
    ],
  },
    {
      id: 'cci',
      name: 'Commodity Channel Index (CCI)',
      shortLabel: 'CCI',
      description: 'Oscilador de desviación respecto a la media.',
      category: 'momentum',
      panel: 'sub',
      source: 'builtin',
      parameters: [
        { id: 'period', label: 'Periodo', type: 'number', default: 20, min: 2, max: 100 },
      ],
    },
  {
    id: 'willr',
    name: 'Williams %R',
    shortLabel: '%R',
    description: 'Oscilador de momentum (−100…0). Típico −20 / −80.',
    category: 'momentum',
    panel: 'sub',
    source: 'builtin',
    parameters: [
      { id: 'period', label: 'Periodo', type: 'number', default: 14, min: 2, max: 100 },
    ],
  },
  {
    id: 'mom',
    name: 'Momentum',
    shortLabel: 'MOM',
    description: 'Close(t) − Close(t − N).',
    category: 'momentum',
    panel: 'sub',
    source: 'builtin',
    parameters: [
      { id: 'period', label: 'Periodo', type: 'number', default: 10, min: 1, max: 100 },
    ],
  },
  {
    id: 'sd',
    name: 'Desviación típica',
    shortLabel: 'SD',
    description: 'Desviación estándar rodante del cierre.',
    category: 'volatility',
    panel: 'sub',
    source: 'builtin',
    parameters: [
      { id: 'period', label: 'Periodo', type: 'number', default: 20, min: 2, max: 200 },
    ],
  },
  {
    id: 'dc',
    name: 'Canal de Donchian',
    shortLabel: 'DC',
    description: 'Canal high/low de N barras (breakouts).',
    category: 'volatility',
    panel: 'overlay',
    source: 'builtin',
    parameters: [
      { id: 'period', label: 'Periodo', type: 'number', default: 20, min: 2, max: 200 },
    ],
  },
  {
    id: 'adx',
    name: 'ADX / DMI',
    shortLabel: 'ADX',
    description: 'Fuerza de tendencia (ADX) con +DI / −DI.',
    category: 'trend',
    panel: 'sub',
    source: 'builtin',
    parameters: [
      { id: 'period', label: 'Periodo', type: 'number', default: 14, min: 2, max: 100 },
    ],
  },
  {
    id: 'srsi',
    name: 'Stochastic RSI',
    shortLabel: 'StochRSI',
    description: 'Estocástico aplicado sobre RSI (0–100).',
    category: 'momentum',
    panel: 'sub',
    source: 'builtin',
    parameters: [
      { id: 'rsiPeriod', label: 'RSI', type: 'number', default: 14, min: 2, max: 100 },
      { id: 'stochPeriod', label: 'Stoch', type: 'number', default: 14, min: 2, max: 100 },
      { id: 'kPeriod', label: '%K', type: 'number', default: 3, min: 1, max: 20 },
      { id: 'dPeriod', label: '%D', type: 'number', default: 3, min: 1, max: 20 },
    ],
  },
  {
    id: 'st',
    name: 'SuperTrend',
    shortLabel: 'ST',
    description: 'Seguimiento de tendencia basado en ATR.',
    category: 'trend',
    panel: 'overlay',
    source: 'builtin',
    parameters: [
      { id: 'atrPeriod', label: 'ATR', type: 'number', default: 10, min: 2, max: 100 },
      { id: 'multiplier', label: 'Mult.', type: 'number', default: 3, min: 0.5, max: 10, step: 0.1 },
    ],
  },
  {
    id: 'vwap',
    name: 'VWAP',
    shortLabel: 'VWAP',
    description: 'Precio medio ponderado por volumen (acumulado).',
    category: 'volume',
    panel: 'overlay',
    source: 'builtin',
    parameters: [],
  },
  {
    id: 'obv',
    name: 'On Balance Volume',
    shortLabel: 'OBV',
    description: 'Volumen acumulado según dirección del cierre.',
    category: 'volume',
    panel: 'sub',
    source: 'builtin',
    parameters: [],
  },
  {
    id: 'roc',
    name: 'Rate of Change',
    shortLabel: 'ROC',
    description: 'Variación porcentual del cierre en N barras.',
    category: 'momentum',
    panel: 'sub',
    source: 'builtin',
    parameters: [
      { id: 'period', label: 'Periodo', type: 'number', default: 12, min: 1, max: 200 },
    ],
  },
  {
    id: 'mfi',
    name: 'Money Flow Index',
    shortLabel: 'MFI',
    description: 'RSI ponderado por volumen (0–100).',
    category: 'volume',
    panel: 'sub',
    source: 'builtin',
    parameters: [
      { id: 'period', label: 'Periodo', type: 'number', default: 14, min: 2, max: 100 },
    ],
  },
  {
    id: 'aroon',
    name: 'Aroon',
    shortLabel: 'Aroon',
    description: 'Aroon Up / Down (0–100).',
    category: 'trend',
    panel: 'sub',
    source: 'builtin',
    parameters: [
      { id: 'period', label: 'Periodo', type: 'number', default: 25, min: 2, max: 100 },
    ],
  },
  {
    id: 'sar',
    name: 'Parabolic SAR',
    shortLabel: 'SAR',
    description: 'Stop and Reverse parabólico.',
    category: 'trend',
    panel: 'overlay',
    source: 'builtin',
    parameters: [
      { id: 'step', label: 'AF step', type: 'number', default: 0.02, min: 0.001, max: 0.2, step: 0.001 },
      { id: 'maxAf', label: 'AF máx.', type: 'number', default: 0.2, min: 0.01, max: 1, step: 0.01 },
    ],
  },
  {
    id: 'bears',
    name: 'Bears Power',
    shortLabel: 'Bears',
    description: 'Elder Ray: Low − EMA.',
    category: 'momentum',
    panel: 'sub',
    source: 'builtin',
    parameters: [
      { id: 'period', label: 'EMA', type: 'number', default: 13, min: 2, max: 100 },
    ],
  },
  {
    id: 'bulls',
    name: 'Bulls Power',
    shortLabel: 'Bulls',
    description: 'Elder Ray: High − EMA.',
    category: 'momentum',
    panel: 'sub',
    source: 'builtin',
    parameters: [
      { id: 'period', label: 'EMA', type: 'number', default: 13, min: 2, max: 100 },
    ],
  },
  {
    id: 'ali',
    name: 'Alligator',
    shortLabel: 'ALI',
    description: 'Mandíbula / dientes / labios (SMMA).',
    category: 'trend',
    panel: 'overlay',
    source: 'builtin',
    parameters: [],
  },
  {
    id: 'fr',
    name: 'Fractals',
    shortLabel: 'FR',
    description: 'Fractales Williams (5 barras).',
    category: 'trend',
    panel: 'overlay',
    source: 'builtin',
    parameters: [],
  },
  {
    id: 'ich',
    name: 'Ichimoku',
    shortLabel: 'ICH',
    description: 'Tenkan, Kijun, Senkou A/B y Chikou.',
    category: 'trend',
    panel: 'overlay',
    source: 'builtin',
    parameters: [
      { id: 'tenkanPeriod', label: 'Tenkan', type: 'number', default: 9, min: 2, max: 50 },
      { id: 'kijunPeriod', label: 'Kijun', type: 'number', default: 26, min: 2, max: 100 },
      { id: 'senkouBPeriod', label: 'Senkou B', type: 'number', default: 52, min: 2, max: 200 },
      { id: 'displacement', label: 'Desplaz.', type: 'number', default: 26, min: 1, max: 100 },
    ],
  },
];

/** Reservado fase 3 — indicadores personales del usuario. */
export const CUSTOM_INDICATORS: IndicatorDefinition[] = [];

/** Indicadores IA deterministas (scores compuestos). */
export const AI_INDICATORS: IndicatorDefinition[] = AI_INDICATOR_DEFINITIONS;

export const ALL_INDICATOR_DEFINITIONS: IndicatorDefinition[] = [
  ...BUILTIN_INDICATORS,
  ...CUSTOM_INDICATORS,
  ...AI_INDICATORS,
];

export function findIndicatorDefinition(id: string): IndicatorDefinition | undefined {
  return ALL_INDICATOR_DEFINITIONS.find((definition) => definition.id === id);
}

function instanceKey(definitionId: string, parameters: ChartIndicatorInstance['parameters']) {
  return instanceSpecKey(definitionId, parameters);
}

/** Mapea instancia builtin a flags de display actuales (compatibilidad API). */
export function displayPatchForInstance(
  definitionId: string,
  parameters: ChartIndicatorInstance['parameters'],
  visible: boolean,
): Partial<ChartDisplayConfig> {
  if (definitionId === 'volume') return { showVolume: visible };
  if (definitionId === 'sma') {
    const period = Number(parameters.period ?? 20);
    if (period === 20) return { showSma20: visible };
    if (period === 50) return { showSma50: visible };
  }
  if (definitionId === 'ema') {
    const period = Number(parameters.period ?? 20);
    if (period === 20) return { showEma20: visible };
  }
  if (definitionId === 'rsi') {
    const period = Number(parameters.period ?? 14);
    if (period === 14) return { showRsi14: visible };
  }
  return {};
}

export function seedIndicatorInstancesFromDisplay(
  display: ChartDisplayConfig,
): ChartIndicatorInstance[] {
  const instances: ChartIndicatorInstance[] = [];
  if (display.showVolume) {
    instances.push({
      instanceId: 'volume-default',
      definitionId: 'volume',
      parameters: {},
      visible: true,
    });
  }
  if (display.showSma20) {
    instances.push({
      instanceId: 'sma-20',
      definitionId: 'sma',
      parameters: { period: 20 },
      visible: true,
    });
  }
  if (display.showSma50) {
    instances.push({
      instanceId: 'sma-50',
      definitionId: 'sma',
      parameters: { period: 50 },
      visible: true,
    });
  }
  if (display.showEma20) {
    instances.push({
      instanceId: 'ema-20',
      definitionId: 'ema',
      parameters: { period: 20 },
      visible: true,
    });
  }
  if (display.showRsi14) {
    instances.push({
      instanceId: 'rsi-14',
      definitionId: 'rsi',
      parameters: { period: 14 },
      visible: true,
    });
  }
  return instances;
}

export function mergeDisplayFromInstances(
  display: ChartDisplayConfig,
  instances: ChartIndicatorInstance[],
): ChartDisplayConfig {
  const next: ChartDisplayConfig = {
    ...display,
    showVolume: false,
    showSma20: false,
    showSma50: false,
    showEma20: false,
    showRsi14: false,
  };
  for (const instance of instances) {
    if (!instance.visible) continue;
    const patch = displayPatchForInstance(instance.definitionId, instance.parameters, true);
    Object.assign(next, patch);
  }
  return next;
}

export function newIndicatorInstanceId(definitionId: string, parameters: ChartIndicatorInstance['parameters']) {
  const key = parametersKey(parameters).replace(/[^a-z0-9]+/gi, '-');
  return `ind-${definitionId}-${key}-${Date.now().toString(36)}`;
}

export function defaultParameters(definition: IndicatorDefinition): ChartIndicatorInstance['parameters'] {
  const parameters: ChartIndicatorInstance['parameters'] = {};
  for (const param of definition.parameters) {
    parameters[param.id] = param.default;
  }
  return parameters;
}

export function instanceLabel(instance: ChartIndicatorInstance): string {
  const definition = findIndicatorDefinition(instance.definitionId);
  if (!definition) return instance.definitionId;
  if (definition.parameters.length === 0) return definition.shortLabel;
  const parts = definition.parameters
    .map((param) => {
      const value = instance.parameters[param.id];
      if (value == null) return null;
      if (param.id === 'period') return String(value);
      return `${param.label} ${value}`;
    })
    .filter(Boolean);
  if (parts.length === 0) return definition.shortLabel;
  return `${definition.shortLabel} ${parts.join(' / ')}`;
}

export { findInstanceBySpec };

export function hasDuplicateInstance(
  instances: ChartIndicatorInstance[],
  definitionId: string,
  parameters: ChartIndicatorInstance['parameters'],
) {
  const key = instanceKey(definitionId, parameters);
  return instances.some(
    (item) => instanceKey(item.definitionId, item.parameters) === key,
  );
}
