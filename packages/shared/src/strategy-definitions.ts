/** DTOs API — estrategias guardadas (BT-2). */

import type {
  StrategyDefinitionV1,
  StrategyOrigin,
} from './research-platform.js';
import type { BacktestStrategyType } from './types.js';

export interface StrategyDefinitionSummaryDto {
  id: string;
  name: string;
  presetKey?: BacktestStrategyType;
  origin: StrategyOrigin;
  timeframe: string;
  kind: StrategyDefinitionV1['kind'];
  /**
   * Alcance S3: `[]` = reutilizable (plantilla);
   * no vacío = ajuste a ese/esos valores (`universe.instrumentIds`).
   */
  instrumentIds: string[];
  updatedAt: string;
  createdAt: string;
}

export interface StrategyDefinitionDetailDto extends StrategyDefinitionSummaryDto {
  definition: StrategyDefinitionV1;
}

/** Crear desde preset builtin. */
export interface CreateStrategyFromPresetDto {
  name: string;
  presetKey: BacktestStrategyType;
  timeframe?: StrategyDefinitionV1['timeframe'];
  commissionBps?: number;
  slippageBps?: number;
}

/** Crear/actualizar definición completa. */
export interface UpsertStrategyDefinitionDto {
  name: string;
  definition: StrategyDefinitionV1;
}

export interface UpdateStrategyDefinitionDto {
  name?: string;
  definition?: StrategyDefinitionV1;
}
