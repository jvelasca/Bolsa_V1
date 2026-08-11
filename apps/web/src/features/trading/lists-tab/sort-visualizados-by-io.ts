/**
 * Ordena Visualizados por Índice Operativo (IO) — el mismo factor que Operativa
 * usa para «El N de M en Estudio» (#1 = mejor IO).
 *
 * Mejor IO → índice menor (pestaña más a la izquierda).
 */

import { computeIndiceOperativo } from "@/features/trading/operativa-index";

export type IoSortRow = {
  instrumentId: string;
  io: number | null;
  symbol: string;
};

export function compareIoQuality(a: IoSortRow, b: IoSortRow): number {
  const ai = a.io;
  const bi = b.io;
  if (ai == null && bi == null) return a.symbol.localeCompare(b.symbol, "es");
  if (ai == null) return 1;
  if (bi == null) return -1;
  if (bi !== ai) return bi - ai;
  return a.symbol.localeCompare(b.symbol, "es");
}

export function buildIoSortRows(
  instrumentIds: ReadonlyArray<string>,
  ioByInstrument: ReadonlyMap<string, number | null>,
  symbolById: ReadonlyMap<string, string> | Record<string, string>,
): IoSortRow[] {
  const symbolOf = (id: string) => {
    if (symbolById instanceof Map) return symbolById.get(id) ?? id;
    return (symbolById as Record<string, string>)[id] ?? id;
  };
  return instrumentIds.map((instrumentId) => ({
    instrumentId,
    io: ioByInstrument.get(instrumentId) ?? null,
    symbol: symbolOf(instrumentId),
  }));
}

/** instrumentIds ordenados: mayor IO primero (izq = #1 relativo). */
export function orderInstrumentIdsByIo(
  instrumentIds: ReadonlyArray<string>,
  ioByInstrument: ReadonlyMap<string, number | null>,
  symbolById: ReadonlyMap<string, string> | Record<string, string>,
): string[] {
  return [...buildIoSortRows(instrumentIds, ioByInstrument, symbolById)]
    .sort(compareIoQuality)
    .map((r) => r.instrumentId);
}

export function ioFromCompositeAndFa(input: {
  compositeDisplay100: number | null | undefined;
  distress?: boolean;
}): number | null {
  return computeIndiceOperativo(input);
}
