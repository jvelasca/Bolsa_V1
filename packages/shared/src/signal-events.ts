import type { BacktestStrategyType } from './types.js';

/** Tipos de señal discretos — alineado SC-0/SC-1 y ADR-006 backtest_marker. */
export type SignalKind = 'entry_long' | 'entry_short' | 'exit' | 'watch';

/** Subset H0 emitido por evaluate_preset (SC-0). */
export interface PresetSignalEventDto {
  kind: SignalKind;
  barIndex: number;
  timestamp: string;
  price: number;
  presetKey: BacktestStrategyType;
}

/** Contrato completo para screener/alertas (SC-1). */
export interface SignalEventV1 {
  id: string;
  instrumentId: string;
  timestamp: string;
  kind: SignalKind;
  strategyDefinitionId: string;
  strategyVersion: number;
  barIndex: number;
  price: number;
  dataVersion?: string;
  indicatorSnapshotHash?: string;
  presetKey?: BacktestStrategyType;
}
