import type { ChartDrawing } from './chart-drawings.js';
import type { OhlcvBarDto } from './types.js';

/** Evento `backtest_marker` (ADR-006) — cruce precio vs nivel del dibujo. */
export interface DrawingReplayMarkerDto {
  id: string;
  drawingId: string;
  timestamp: string;
  /** Cierre de la barra en el cruce. */
  price: number;
  /** Nivel del dibujo en esa barra. */
  level: number;
  /** Precio cruzó hacia arriba o hacia abajo del nivel. */
  direction: 'up' | 'down';
  drawingType: ChartDrawing['type'];
  label?: string;
}

export interface DrawingReplayRequestDto {
  bars: OhlcvBarDto[];
  drawings: ChartDrawing[];
  /** Si true, solo dibujos con `alertOnCross`. Default true. */
  alertDrawingsOnly?: boolean;
}

export interface DrawingReplayResponseDto {
  data: DrawingReplayMarkerDto[];
}
