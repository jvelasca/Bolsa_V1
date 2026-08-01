import type { DrawingReplayMarkerDto } from './drawing-replay-api.js';
import type { StrategyDefinitionV1 } from './research-platform.js';
import type { OhlcvBarDto } from './types.js';
import type { SignalEventV1, SignalKind } from './signal-events.js';

export type SignalEvaluationMode = 'raw' | 'gated';

export interface EvaluateSignalsRequestDto {
  definition: StrategyDefinitionV1 | Record<string, unknown>;
  instrumentId?: string;
  bars: OhlcvBarDto[];
  mode?: SignalEvaluationMode;
  dataVersion?: string;
  indicatorSnapshotHash?: string;
}

export interface EvaluateSignalsResponseDto {
  data: SignalEventV1[];
}

/** Convierte cruce de dibujo (BT-6) → SignalEventV1 para tubería unificada. */
export function drawingMarkerToSignalEventV1(
  marker: DrawingReplayMarkerDto,
  options: {
    instrumentId: string;
    strategyDefinitionId: string;
    strategyVersion: number;
    barIndex: number;
  },
): SignalEventV1 {
  let kind: SignalKind;
  if (marker.direction === 'up') {
    kind = 'entry_long';
  } else if (marker.direction === 'down') {
    kind = 'exit';
  } else {
    kind = 'watch';
  }

  return {
    id: `sig:draw:${marker.id}`,
    instrumentId: options.instrumentId,
    timestamp: marker.timestamp,
    kind,
    strategyDefinitionId: options.strategyDefinitionId,
    strategyVersion: options.strategyVersion,
    barIndex: options.barIndex,
    price: marker.price,
  };
}
