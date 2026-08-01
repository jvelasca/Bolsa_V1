import type { StrategyDefinitionV1 } from './research-platform.js';
import type { StrategyDraftFundamentalPreviewDto } from './fundamentals-gate.js';

export type StrategyDraftKind = 'classic' | 'hybrid';

export interface DraftStrategyFromPromptRequestDto {
  prompt: string;
  instrumentIds?: string[];
}

export interface DraftStrategyFromPromptResultDto {
  draftKind: StrategyDraftKind;
  presetKey: string;
  timeframe: string;
  suggestedName: string;
  confidence: number;
  explanation: string;
  definition: StrategyDefinitionV1 | Record<string, unknown>;
  engine: string;
  validated: boolean;
  gatePresetKey?: string;
  minScore?: number;
  /** Interpretación detallada para el usuario (P11+). */
  feedback?: StrategyDraftFeedbackDto;
}

export interface StrategyDraftDetectedSignalDto {
  id: string;
  label: string;
  detail?: string;
}

export interface StrategyDraftAlternativeDto {
  presetKey: string;
  label: string;
  score: number;
  selected: boolean;
}

export interface StrategyDraftFeedbackDto {
  /** Resumen conversacional de lo interpretado. */
  summary: string;
  detectedSignals: StrategyDraftDetectedSignalDto[];
  alternatives: StrategyDraftAlternativeDto[];
  warnings: string[];
  scanSteps: string[];
  engineLabel: string;
  ambiguous: boolean;
  matchedPresetKey?: string;
  /** Vista previa del gate fundamental (P12) cuando el prompt lo incluye. */
  fundamentalPreview?: StrategyDraftFundamentalPreviewDto;
}

export type {
  StrategyDraftFundamentalConditionPreviewDto,
  StrategyDraftFundamentalPreviewDto,
} from './fundamentals-gate.js';

export interface DraftStrategyFromPromptResponseDto {
  data: DraftStrategyFromPromptResultDto;
}

export const PROMPT_DRAFT_EXAMPLES = [
  'Cruce SMA 20/50 en diario',
  'RSI reversión a la media en sobreventa',
  'Híbrido: tendencia alcista SMA200 con rating ≥ 65',
  'PER máximo 20 y cap. mínima 1000M con rating técnico',
  'Pullback en uptrend con ranking técnico',
  'MACD cruza señal semanal',
] as const;
