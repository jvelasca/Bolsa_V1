/**
 * V1.28 B-α (G2) — badges y toasts operativos DISPARADA / T1.
 * T1 = informativo (H2: tocado ≠ gestionado). Sin drag · sin bypass Confirm.
 *
 * @see docs/engineering/estudio-operativa-auto-y-grafico-2026-08-28.md §4.2 G2
 */

import type { MercadoCockpitPhase } from "@/features/trading/operativa-cockpit-phase";

export const OPERATIVA_TOAST_SEEN_KEY = "bolsa-operativa-toast-seen-v1";

export type ListOperativaBadgeKind = "disparada" | "propuesta" | "t1";

export type ListOperativaBadge = {
  kind: ListOperativaBadgeKind;
  label: string;
};

export type OperativaToastKind = "disparada" | "t1";

export type OperativaToastEvent = {
  key: string;
  kind: OperativaToastKind;
  instrumentId: string;
  symbol: string;
};

export function resolveListOperativaBadge(input: {
  phase: MercadoCockpitPhase;
  target1Touched: boolean;
  target1Managed: boolean;
}): ListOperativaBadge | null {
  if (input.phase === "disparada") {
    return { kind: "disparada", label: "Disparada" };
  }
  if (input.phase === "propuesta") {
    return { kind: "propuesta", label: "Propuesta" };
  }
  if (
    input.phase === "posicion" &&
    input.target1Touched &&
    !input.target1Managed
  ) {
    return { kind: "t1", label: "T1 ●" };
  }
  return null;
}

export function operativaDisparadaToastKey(
  instrumentId: string,
  decisionId: string | null | undefined,
): string {
  return `disparada|${instrumentId}|${decisionId?.trim() || "—"}`;
}

export function operativaT1ToastKey(
  instrumentId: string,
  positionId: string | null | undefined,
): string {
  return `t1|${instrumentId}|${positionId?.trim() || "—"}`;
}

export function collectOperativaToastEvents(
  rows: ReadonlyArray<{
    instrumentId: string;
    symbol: string;
    phase: MercadoCockpitPhase;
    target1Touched: boolean;
    target1Managed: boolean;
    decisionId?: string | null;
    positionId?: string | null;
  }>,
): OperativaToastEvent[] {
  const events: OperativaToastEvent[] = [];
  for (const row of rows) {
    if (row.phase === "disparada") {
      events.push({
        key: operativaDisparadaToastKey(row.instrumentId, row.decisionId),
        kind: "disparada",
        instrumentId: row.instrumentId,
        symbol: row.symbol,
      });
    }
    if (row.phase === "posicion" && row.target1Touched && !row.target1Managed) {
      events.push({
        key: operativaT1ToastKey(row.instrumentId, row.positionId),
        kind: "t1",
        instrumentId: row.instrumentId,
        symbol: row.symbol,
      });
    }
  }
  return events;
}

export function partitionFreshOperativaEvents(
  events: ReadonlyArray<OperativaToastEvent>,
  seen: ReadonlySet<string>,
): { fresh: OperativaToastEvent[]; nextSeen: Set<string> } {
  const nextSeen = new Set(seen);
  const fresh: OperativaToastEvent[] = [];
  for (const event of events) {
    if (nextSeen.has(event.key)) continue;
    fresh.push(event);
    nextSeen.add(event.key);
  }
  return { fresh, nextSeen };
}

export function formatOperativaToastMessage(
  event: OperativaToastEvent,
): string {
  if (event.kind === "disparada") {
    return `Mercado · ${event.symbol} disparada — revisa y confirma (Ranking ≠ BUY)`;
  }
  return `Mercado · ${event.symbol} T1 alcanzado · pendiente de gestión (tocado ≠ reducido)`;
}

export function loadOperativaToastSeen(): Set<string> {
  try {
    const raw = sessionStorage.getItem(OPERATIVA_TOAST_SEEN_KEY);
    if (!raw) return new Set();
    const arr = JSON.parse(raw) as unknown;
    if (!Array.isArray(arr)) return new Set();
    return new Set(arr.filter((x): x is string => typeof x === "string"));
  } catch {
    return new Set();
  }
}

export function saveOperativaToastSeen(seen: Set<string>): void {
  try {
    sessionStorage.setItem(
      OPERATIVA_TOAST_SEEN_KEY,
      JSON.stringify([...seen].slice(-300)),
    );
  } catch {
    /* ignore */
  }
}
