/**
 * Mandato operativo — tenure de estrategia por instrumento×cuenta (ADR-020).
 *
 * Fuente de verdad del historial; la adopción (`strategy-adoption`) es proyección
 * del tenure abierto + estados de puente (candidata / propuesta / obsoleta).
 *
 * Persistencia: localStorage (cache) + PostgreSQL multi-dispositivo (M1b ·
 * `operating-mandate-sync.ts`).
 *
 * @see docs/adr/020-operating-mandate-tenure.md
 */
import type { MandateActorDto, MandateReasonDto } from "@bolsa/shared";

export const MANDATE_TENURES_KEY = "bolsa-mandate-tenures-v1";
export const MANDATE_TENURES_ENGINE = "mandate-tenures-v1" as const;

export const MANDATE_TRADE_LINKS_KEY = "bolsa-mandate-trade-links-v1";
export const MANDATE_TRADE_LINKS_ENGINE = "mandate-trade-links-v1" as const;

export type MandateActor = MandateActorDto;
export type MandateReason = MandateReasonDto;

export const MANDATE_ACTOR_LABELS: Record<MandateActor, string> = {
  user: "Usuario",
  coach: "Coach",
  core_r: "CORE-R",
  system: "Sistema",
};

export const MANDATE_REASON_LABELS: Record<MandateReason, string> = {
  adopt: "Adoptar",
  switch: "Cambio",
  propose_accepted: "Propuesta aceptada",
  obsolete: "Obsoleto",
  manual: "Manual",
};

export type MandateTenure = {
  id: string;
  accountId: string;
  instrumentId: string;
  timeframe?: string | null;
  strategyDefinitionId?: string | null;
  strategyLabelSnapshot?: string | null;
  effectiveFrom: string;
  /** null = vigente */
  effectiveTo: string | null;
  actor: MandateActor;
  reason: MandateReason;
  sourceTopId?: string | null;
  sourceTopVersion?: number | null;
  evidenceLevel?: "in_sample_only" | "lab_validated" | null;
};

export type MandateTenureStore = {
  engine: typeof MANDATE_TENURES_ENGINE;
  /** Clave `instrumentId::accountId` → tenures (más reciente al final). */
  byKey: Record<string, MandateTenure[]>;
};

export type MandateTradeLink = {
  engine: typeof MANDATE_TRADE_LINKS_ENGINE;
  transactionId: string;
  mandateTenureId: string;
  instrumentId: string;
  accountId: string;
  linkedAt: string;
};

export type MandateTradeLinkStore = {
  engine: typeof MANDATE_TRADE_LINKS_ENGINE;
  links: MandateTradeLink[];
};

export type MandateChurnSummary = {
  totalChanges: number;
  byActor: Record<MandateActor, number>;
  openCount: number;
  closedCount: number;
};

/** Suscriptores UI (rail / timeline) ante escrituras localStorage. */
let mandateRevision = 0;
const mandateListeners = new Set<() => void>();

function bumpMandateRevision(): void {
  mandateRevision += 1;
  for (const l of mandateListeners) l();
}

export function subscribeMandateStore(onStoreChange: () => void): () => void {
  mandateListeners.add(onStoreChange);
  return () => {
    mandateListeners.delete(onStoreChange);
  };
}

export function getMandateStoreSnapshot(): number {
  return mandateRevision;
}

/** Para que adopción (candidata/propuesta) también refresque el rail. */
export function notifyMandateStoreListeners(): void {
  bumpMandateRevision();
}

export function mandateKey(instrumentId: string, accountId: string): string {
  return `${instrumentId}::${accountId}`;
}

function schedulePush(accountId: string): void {
  void import("@/features/platform/operating-mandate-sync").then((m) => {
    m.scheduleMandatePush(accountId);
  });
}

function newTenureId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `mt-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

export function emptyMandateTenureStore(): MandateTenureStore {
  return { engine: MANDATE_TENURES_ENGINE, byKey: {} };
}

export function readMandateTenureStore(): MandateTenureStore {
  if (typeof localStorage === "undefined") return emptyMandateTenureStore();
  try {
    const raw = localStorage.getItem(MANDATE_TENURES_KEY);
    if (!raw) return emptyMandateTenureStore();
    const parsed = JSON.parse(raw) as MandateTenureStore;
    if (!parsed || typeof parsed !== "object" || !parsed.byKey) {
      return emptyMandateTenureStore();
    }
    return { engine: MANDATE_TENURES_ENGINE, byKey: parsed.byKey };
  } catch {
    return emptyMandateTenureStore();
  }
}

export function writeMandateTenureStore(store: MandateTenureStore): void {
  if (typeof localStorage === "undefined") return;
  localStorage.setItem(
    MANDATE_TENURES_KEY,
    JSON.stringify({ engine: MANDATE_TENURES_ENGINE, byKey: store.byKey }),
  );
  bumpMandateRevision();
}

export function listMandateTenures(
  instrumentId: string,
  accountId: string | null | undefined,
): MandateTenure[] {
  if (!accountId) return [];
  const rows =
    readMandateTenureStore().byKey[mandateKey(instrumentId, accountId)] ?? [];
  return [...rows].sort((a, b) =>
    a.effectiveFrom.localeCompare(b.effectiveFrom),
  );
}

export function getOpenMandateTenure(
  instrumentId: string,
  accountId: string | null | undefined,
): MandateTenure | null {
  const rows = listMandateTenures(instrumentId, accountId);
  for (let i = rows.length - 1; i >= 0; i -= 1) {
    const row = rows[i];
    if (row != null && row.effectiveTo == null) return row;
  }
  return null;
}

/**
 * Cierra el tenure abierto (si hay) y opcionalmente abre uno nuevo.
 * Garantiza un solo abierto por instrumento×cuenta.
 */
export function applyMandateChange(input: {
  instrumentId: string;
  accountId: string;
  /** Si falta, solo cierra el vigente (p. ej. obsoleta / clear). */
  open?: {
    strategyDefinitionId?: string | null;
    strategyLabelSnapshot?: string | null;
    timeframe?: string | null;
    actor?: MandateActor;
    reason?: MandateReason;
    sourceTopId?: string | null;
    sourceTopVersion?: number | null;
    evidenceLevel?: "in_sample_only" | "lab_validated" | null;
  } | null;
  at?: string;
}): { closed: MandateTenure | null; opened: MandateTenure | null } {
  const at = input.at ?? new Date().toISOString();
  const key = mandateKey(input.instrumentId, input.accountId);
  const store = readMandateTenureStore();
  const rows = [...(store.byKey[key] ?? [])];

  let closed: MandateTenure | null = null;
  const openIdx = rows.findIndex((r) => r.effectiveTo == null);
  if (openIdx >= 0) {
    const prev = rows[openIdx];
    if (prev) {
      const sameStrategy =
        input.open &&
        (prev.strategyDefinitionId ?? null) ===
          (input.open.strategyDefinitionId ?? null);
      if (sameStrategy && input.open) {
        return { closed: null, opened: prev };
      }
      closed = { ...prev, effectiveTo: at };
      rows[openIdx] = closed;
    }
  }

  let opened: MandateTenure | null = null;
  if (input.open) {
    const reason: MandateReason =
      input.open.reason ?? (closed ? "switch" : "adopt");
    opened = {
      id: newTenureId(),
      accountId: input.accountId,
      instrumentId: input.instrumentId,
      timeframe: input.open.timeframe ?? null,
      strategyDefinitionId: input.open.strategyDefinitionId ?? null,
      strategyLabelSnapshot: input.open.strategyLabelSnapshot ?? null,
      effectiveFrom: at,
      effectiveTo: null,
      actor: input.open.actor ?? "user",
      reason,
      sourceTopId: input.open.sourceTopId ?? null,
      sourceTopVersion: input.open.sourceTopVersion ?? null,
      evidenceLevel: input.open.evidenceLevel ?? null,
    };
    rows.push(opened);
  }

  store.byKey[key] = rows;
  writeMandateTenureStore(store);
  schedulePush(input.accountId);
  return { closed, opened };
}

/** Seed tenure desde adopción legacy (solo si no hay historial). */
export function seedMandateFromAdoption(input: {
  instrumentId: string;
  accountId: string;
  strategyDefinitionId?: string | null;
  strategyLabel?: string | null;
  timeframe?: string | null;
  updatedAt?: string;
}): MandateTenure | null {
  if (listMandateTenures(input.instrumentId, input.accountId).length > 0) {
    return getOpenMandateTenure(input.instrumentId, input.accountId);
  }
  const { opened } = applyMandateChange({
    instrumentId: input.instrumentId,
    accountId: input.accountId,
    at: input.updatedAt,
    open: {
      strategyDefinitionId: input.strategyDefinitionId,
      strategyLabelSnapshot: input.strategyLabel,
      timeframe: input.timeframe,
      actor: "system",
      reason: "adopt",
    },
  });
  return opened;
}

export function summarizeMandateChurn(opts?: {
  accountId?: string | null;
  instrumentId?: string | null;
}): MandateChurnSummary {
  const store = readMandateTenureStore();
  const byActor: Record<MandateActor, number> = {
    user: 0,
    coach: 0,
    core_r: 0,
    system: 0,
  };
  let openCount = 0;
  let closedCount = 0;
  let totalChanges = 0;

  for (const [key, rows] of Object.entries(store.byKey)) {
    const [instrumentId, accountId] = key.split("::");
    if (opts?.accountId && accountId !== opts.accountId) continue;
    if (opts?.instrumentId && instrumentId !== opts.instrumentId) continue;
    for (const row of rows) {
      totalChanges += 1;
      byActor[row.actor] = (byActor[row.actor] ?? 0) + 1;
      if (row.effectiveTo == null) openCount += 1;
      else closedCount += 1;
    }
  }

  return { totalChanges, byActor, openCount, closedCount };
}

/** Tenures abiertos de una cuenta (revisión 5b en Coach rail). */
export function listOpenMandateTenures(
  accountId: string | null | undefined,
): MandateTenure[] {
  if (!accountId) return [];
  const store = readMandateTenureStore();
  const out: MandateTenure[] = [];
  for (const [key, rows] of Object.entries(store.byKey)) {
    const [, acc] = key.split("::");
    if (acc !== accountId) continue;
    for (const row of rows) {
      if (row.effectiveTo == null) out.push(row);
    }
  }
  return out.sort((a, b) => b.effectiveFrom.localeCompare(a.effectiveFrom));
}

export function emptyMandateTradeLinkStore(): MandateTradeLinkStore {
  return { engine: MANDATE_TRADE_LINKS_ENGINE, links: [] };
}

export function readMandateTradeLinkStore(): MandateTradeLinkStore {
  if (typeof localStorage === "undefined") return emptyMandateTradeLinkStore();
  try {
    const raw = localStorage.getItem(MANDATE_TRADE_LINKS_KEY);
    if (!raw) return emptyMandateTradeLinkStore();
    const parsed = JSON.parse(raw) as MandateTradeLinkStore;
    if (!parsed || !Array.isArray(parsed.links))
      return emptyMandateTradeLinkStore();
    return { engine: MANDATE_TRADE_LINKS_ENGINE, links: parsed.links };
  } catch {
    return emptyMandateTradeLinkStore();
  }
}

export function writeMandateTradeLinkStore(store: MandateTradeLinkStore): void {
  if (typeof localStorage === "undefined") return;
  localStorage.setItem(
    MANDATE_TRADE_LINKS_KEY,
    JSON.stringify({ engine: MANDATE_TRADE_LINKS_ENGINE, links: store.links }),
  );
  bumpMandateRevision();
}

/** M2: enlaza un fill/transacción al mandato vigente (o al indicado). */
export function linkTradeToMandate(input: {
  transactionId: string;
  instrumentId: string;
  accountId: string;
  mandateTenureId?: string | null;
}): MandateTradeLink | null {
  const tenureId =
    input.mandateTenureId ??
    getOpenMandateTenure(input.instrumentId, input.accountId)?.id ??
    null;
  if (!tenureId) return null;

  const store = readMandateTradeLinkStore();
  const existing = store.links.find(
    (l) => l.transactionId === input.transactionId,
  );
  if (existing) return existing;

  const link: MandateTradeLink = {
    engine: MANDATE_TRADE_LINKS_ENGINE,
    transactionId: input.transactionId,
    mandateTenureId: tenureId,
    instrumentId: input.instrumentId,
    accountId: input.accountId,
    linkedAt: new Date().toISOString(),
  };
  store.links = [...store.links, link].slice(-500);
  writeMandateTradeLinkStore(store);
  schedulePush(input.accountId);
  return link;
}

export function listTradeLinksForMandate(
  mandateTenureId: string,
): MandateTradeLink[] {
  return readMandateTradeLinkStore().links.filter(
    (l) => l.mandateTenureId === mandateTenureId,
  );
}

export function countTradeLinksForInstrument(
  instrumentId: string,
  accountId: string,
): number {
  return readMandateTradeLinkStore().links.filter(
    (l) => l.instrumentId === instrumentId && l.accountId === accountId,
  ).length;
}

export function formatMandateTenureRange(t: MandateTenure): string {
  const from = t.effectiveFrom.slice(0, 10);
  if (!t.effectiveTo) return `${from} → vigente`;
  return `${from} → ${t.effectiveTo.slice(0, 10)}`;
}
