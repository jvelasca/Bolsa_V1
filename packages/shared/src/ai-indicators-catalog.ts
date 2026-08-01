import type { IndicatorDefinition } from './indicators-catalog.js';

/** Motores IA deterministas (scores compuestos explicables). */
export const AI_INDICATOR_DEFINITIONS: IndicatorDefinition[] = [
  {
    id: 'technical_rating_v1',
    name: 'Rating técnico IA v1',
    shortLabel: 'Rating IA',
    description:
      'Score 0–100 del setup técnico (tendencia, momentum, volatilidad, reversión, patrón). Mismo motor que rastreadores híbridos.',
    category: 'custom',
    panel: 'sub',
    source: 'ai',
    parameters: [
      {
        id: 'showComponents',
        label: 'Mostrar componentes',
        type: 'boolean',
        default: false,
        description: 'Tendencia y momentum como líneas auxiliares.',
      },
      {
        id: 'warmupBars',
        label: 'Barras mínimas',
        type: 'number',
        default: 50,
        min: 30,
        max: 200,
        step: 1,
      },
    ],
  },
  {
    id: 'bar_data_quality_v1',
    name: 'Calidad datos (OHLCV)',
    shortLabel: 'Datos',
    description:
      'Calidad de la serie visible según profundidad e integridad de barras (sin datos de sync externo).',
    category: 'custom',
    panel: 'sub',
    source: 'ai',
    parameters: [
      {
        id: 'gapLookback',
        label: 'Ventana gaps',
        type: 'number',
        default: 90,
        min: 20,
        max: 250,
        step: 5,
      },
    ],
  },
  {
    id: 'ai_global_score_v1',
    name: 'Score global IA',
    shortLabel: 'Global IA',
    description: 'Combinación ponderada de rating técnico y calidad de barras.',
    category: 'custom',
    panel: 'sub',
    source: 'ai',
    parameters: [
      {
        id: 'setupWeight',
        label: 'Peso setup (%)',
        type: 'number',
        default: 70,
        min: 0,
        max: 100,
        step: 5,
      },
      {
        id: 'dataWeight',
        label: 'Peso datos (%)',
        type: 'number',
        default: 30,
        min: 0,
        max: 100,
        step: 5,
      },
      {
        id: 'warmupBars',
        label: 'Barras mínimas',
        type: 'number',
        default: 50,
        min: 30,
        max: 200,
        step: 1,
      },
    ],
  },
  {
    id: 'strategy_hybrid_score_v1',
    name: 'Score de estrategia',
    shortLabel: 'Score estrategia',
    description:
      'Rating técnico vinculado a una estrategia guardada, con umbral mínimo y gate bar-a-bar opcional.',
    category: 'custom',
    panel: 'sub',
    source: 'ai',
    parameters: [
      {
        id: 'linkedStrategyId',
        label: 'Estrategia',
        type: 'select',
        default: '',
        options: [],
      },
      {
        id: 'strategyName',
        label: 'Nombre estrategia',
        type: 'select',
        default: '',
        options: [],
      },
      {
        id: 'minScore',
        label: 'Umbral mínimo',
        type: 'number',
        default: 60,
        min: 0,
        max: 100,
        step: 1,
      },
      {
        id: 'showMinScoreLine',
        label: 'Línea umbral',
        type: 'boolean',
        default: true,
      },
      {
        id: 'gatePresetKey',
        label: 'Preset gate',
        type: 'select',
        default: '',
        options: [],
      },
      {
        id: 'showGateLine',
        label: 'Línea gate',
        type: 'boolean',
        default: true,
      },
      {
        id: 'showComponents',
        label: 'Mostrar componentes',
        type: 'boolean',
        default: true,
      },
      {
        id: 'warmupBars',
        label: 'Barras mínimas',
        type: 'number',
        default: 50,
        min: 30,
        max: 200,
        step: 1,
      },
    ],
  },
];

export const AI_SCORE_DEFINITION_IDS = new Set(
  AI_INDICATOR_DEFINITIONS.map((definition) => definition.id),
);

export function isAiScoreIndicator(definitionId: string): boolean {
  return AI_SCORE_DEFINITION_IDS.has(definitionId);
}

export function findAiIndicatorDefinition(id: string): IndicatorDefinition | undefined {
  return AI_INDICATOR_DEFINITIONS.find((definition) => definition.id === id);
}
