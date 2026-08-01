import type { IndicatorSpec } from './research-platform.js';
import type { OhlcvBarDto } from './types.js';

export interface IndicatorLinePointDto {
  timestamp: string;
  value: number;
}

export interface IndicatorLineSeriesDto {
  key: string;
  points: IndicatorLinePointDto[];
}

/** Resultado de compute para un IndicatorSpec concreto. */
export interface IndicatorSpecSeriesDto {
  definitionId: string;
  parameters: Record<string, number | boolean | string>;
  specKey: string;
  lines: IndicatorLineSeriesDto[];
}

export interface ComputeIndicatorsRequestDto {
  bars: OhlcvBarDto[];
  specs: IndicatorSpec[];
}

export interface ComputeIndicatorsResponseDto {
  data: IndicatorSpecSeriesDto[];
}
