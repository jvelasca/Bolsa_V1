/**
 * Tercios de rentabilidad sobre la curva de patrimonio (coach ★ / matriz).
 * Módulo sin dependencias de UI para evitar ciclos matrix ↔ explore.
 */

export type EquityPeriodReturns = {
  early: number;
  mid: number;
  late: number;
};

/** Tercios de rentabilidad sobre la curva de patrimonio (misma lógica que el coach). */
export function periodReturnsFromEquity(
  equity: Array<{ equity: number }> | undefined | null,
): EquityPeriodReturns | null {
  if (!equity || equity.length < 4) return null;
  if (equity.length < 12) {
    const mid = Math.floor(equity.length / 2);
    const start = equity[0]!.equity;
    const midEq = equity[mid]!.equity;
    const end = equity[equity.length - 1]!.equity;
    if (!(start > 0) || !(midEq > 0)) return null;
    const early = ((midEq - start) / start) * 100;
    const late = ((end - midEq) / midEq) * 100;
    return { early, mid: early, late };
  }
  const a = Math.floor(equity.length / 3);
  const b = Math.floor((2 * equity.length) / 3);
  const e0 = equity[0]!.equity;
  const e1 = equity[a]!.equity;
  const e2 = equity[b]!.equity;
  const e3 = equity[equity.length - 1]!.equity;
  if (!(e0 > 0) || !(e1 > 0) || !(e2 > 0)) return null;
  return {
    early: ((e1 - e0) / e0) * 100,
    mid: ((e2 - e1) / e1) * 100,
    late: ((e3 - e2) / e2) * 100,
  };
}
