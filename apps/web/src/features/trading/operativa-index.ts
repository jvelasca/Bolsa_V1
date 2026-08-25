/**
 * Índice Operativo (IO) v1 — ranking entre valores de la lista «Estudio».
 *
 * - Base: Composite display 0–100.
 * - Distress FA → suelo IO ≤ 40.
 * - Universo ranking = membresía explícita de Estudio (no solo pestañas abiertas).
 *
 * @see docs/engineering/trading-operativa-panel-2026-08-04.md
 */

export type OperativaScoreRow = {
  instrumentId: string;
  /** Composite / IO 0–100 */
  io: number | null;
  ta: number | null;
  fa: number | null;
  distress?: boolean;
};

export type OperativaRankResult = {
  rank: number;
  total: number;
  io: number | null;
  ta: number | null;
  fa: number | null;
};

/** IO v1: Composite, con suelo si distress FA. */
export function computeIndiceOperativo(input: {
  compositeDisplay100: number | null | undefined;
  distress?: boolean;
}): number | null {
  const base = input.compositeDisplay100;
  if (base == null || !Number.isFinite(base)) return null;
  let io = Math.round(Math.max(0, Math.min(100, base)));
  if (input.distress) {
    io = Math.min(io, 40);
  }
  return io;
}

/**
 * Prefiere IO server (chip Composite, Ciclo I2). Fallback: fórmula cliente.
 * Ranking Estudio sigue en cliente. IO ≠ permiso.
 */
export function resolveIndiceOperativo(input: {
  indiceOperativo?: number | null;
  compositeDisplay100: number | null | undefined;
  distress?: boolean;
}): number | null {
  const server = input.indiceOperativo;
  if (server != null && Number.isFinite(server)) {
    return Math.round(Math.max(0, Math.min(100, server)));
  }
  return computeIndiceOperativo({
    compositeDisplay100: input.compositeDisplay100,
    distress: input.distress,
  });
}

/**
 * Ordena por IO desc (null al final). Empate: instrumentId estable.
 * Rank 1 = mejor IO.
 */
export function rankIndiceOperativo(
  rows: OperativaScoreRow[],
  activeInstrumentId: string,
): OperativaRankResult | null {
  if (!activeInstrumentId || rows.length === 0) return null;
  const sorted = [...rows].sort((a, b) => {
    const ai = a.io;
    const bi = b.io;
    if (ai == null && bi == null)
      return a.instrumentId.localeCompare(b.instrumentId);
    if (ai == null) return 1;
    if (bi == null) return -1;
    if (bi !== ai) return bi - ai;
    return a.instrumentId.localeCompare(b.instrumentId);
  });
  const index = sorted.findIndex((r) => r.instrumentId === activeInstrumentId);
  if (index < 0) return null;
  const row = sorted[index]!;
  return {
    rank: index + 1,
    total: sorted.length,
    io: row.io,
    ta: row.ta,
    fa: row.fa,
  };
}

export function formatEstudioRankLabel(rank: number, total: number): string {
  return `El ${rank} de ${total} en Estudio`;
}

/** Progreso visual: #1 → barra llena; último → casi vacía. */
export function estudioRankProgressPct(rank: number, total: number): number {
  if (total <= 1) return 100;
  return Math.round(((total - rank) / (total - 1)) * 100);
}
