import type { ChartTimeframe } from './chart-timeframes.js';
import type { IndicatorPreset } from './indicator-presets.js';

export interface DraftIndicatorFromPromptRequestDto {
  prompt: string;
  chartTimeframe?: ChartTimeframe;
}

export interface IndicatorDraftDetectedSignalDto {
  id: string;
  label: string;
  detail?: string;
}

export interface IndicatorDraftAlternativeDto {
  definitionId: string;
  label: string;
  score: number;
  selected: boolean;
}

export interface IndicatorDraftFeedbackDto {
  summary: string;
  detectedSignals: IndicatorDraftDetectedSignalDto[];
  alternatives: IndicatorDraftAlternativeDto[];
  warnings: string[];
  engineLabel: string;
  ambiguous: boolean;
  matchedDefinitionId?: string;
}

export interface DraftIndicatorFromPromptResultDto {
  definitionId: string;
  suggestedPresetName: string;
  confidence: number;
  explanation: string;
  preset: IndicatorPreset;
  engine: string;
  validated: boolean;
  feedback?: IndicatorDraftFeedbackDto;
}

export interface DraftIndicatorFromPromptResponseDto {
  data: DraftIndicatorFromPromptResultDto;
}

export const INDICATOR_PROMPT_DRAFT_EXAMPLES = [
  'RSI 14 en panel inferior',
  'SMA 20 sobre el precio',
  'MACD en panel inferior',
  'Rating técnico con componentes visibles',
  'Calidad de datos OHLCV',
  'Score global 70% setup 30% datos',
  'Bollinger periodo 20',
] as const;
