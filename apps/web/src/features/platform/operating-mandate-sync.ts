/**
 * Sync mandato cliente ↔ PostgreSQL (ADR-020 M1b).
 * localStorage = cache offline; BD = SoT multi-dispositivo.
 */

import { api } from '@/lib/api';
import {
  MANDATE_TRADE_LINKS_ENGINE,
  MANDATE_TENURES_ENGINE,
  mandateKey,
  readMandateTenureStore,
  readMandateTradeLinkStore,
  writeMandateTenureStore,
  writeMandateTradeLinkStore,
  type MandateTenure,
  type MandateTradeLink,
} from '@/features/platform/operating-mandate';

let syncTimer: ReturnType<typeof setTimeout> | null = null;
const hydratedAccounts = new Set<string>();

function tenuresForAccount(accountId: string): MandateTenure[] {
  const store = readMandateTenureStore();
  const out: MandateTenure[] = [];
  for (const [key, rows] of Object.entries(store.byKey)) {
    if (key.endsWith(`::${accountId}`) || rows.some((r) => r.accountId === accountId)) {
      out.push(...rows.filter((r) => r.accountId === accountId));
    }
  }
  return out;
}

function linksForAccount(accountId: string): MandateTradeLink[] {
  return readMandateTradeLinkStore().links.filter((l) => l.accountId === accountId);
}

/** Pull BD → localStorage (merge por id; BD gana en conflicto). */
export async function hydrateMandateFromServer(accountId: string): Promise<void> {
  if (!accountId) return;
  try {
    const res = await api.getAccountMandates(accountId);
    const data = res.data;
    const tenureStore = readMandateTenureStore();
    const byKey: Record<string, MandateTenure[]> = { ...tenureStore.byKey };

    // Drop existing rows for this account then replace from server.
    for (const key of Object.keys(byKey)) {
      byKey[key] = (byKey[key] ?? []).filter((r) => r.accountId !== accountId);
      if (byKey[key].length === 0) delete byKey[key];
    }
    for (const t of data.tenures) {
      const key = mandateKey(t.instrumentId, accountId);
      const row: MandateTenure = {
        id: t.id,
        accountId,
        instrumentId: t.instrumentId,
        timeframe: t.timeframe ?? null,
        strategyDefinitionId: t.strategyDefinitionId ?? null,
        strategyLabelSnapshot: t.strategyLabelSnapshot ?? null,
        effectiveFrom: t.effectiveFrom,
        effectiveTo: t.effectiveTo ?? null,
        actor: t.actor as MandateTenure['actor'],
        reason: t.reason as MandateTenure['reason'],
        sourceTopId: t.sourceTopId ?? null,
        sourceTopVersion: t.sourceTopVersion ?? null,
        evidenceLevel: (t.evidenceLevel as MandateTenure['evidenceLevel']) ?? null,
      };
      byKey[key] = [...(byKey[key] ?? []), row];
    }
    writeMandateTenureStore({ engine: MANDATE_TENURES_ENGINE, byKey });

    const linkStore = readMandateTradeLinkStore();
    const otherLinks = linkStore.links.filter((l) => l.accountId !== accountId);
    const serverLinks: MandateTradeLink[] = data.links.map((l) => ({
      engine: MANDATE_TRADE_LINKS_ENGINE,
      transactionId: l.transactionId,
      mandateTenureId: l.mandateTenureId,
      instrumentId: l.instrumentId,
      accountId: l.accountId,
      linkedAt: l.linkedAt,
    }));
    writeMandateTradeLinkStore({
      engine: MANDATE_TRADE_LINKS_ENGINE,
      links: [...otherLinks, ...serverLinks].slice(-500),
    });
    hydratedAccounts.add(accountId);
  } catch {
    // Offline / API down: keep local cache.
  }
}

export async function pushMandateToServer(accountId: string): Promise<void> {
  if (!accountId) return;
  try {
    await api.syncAccountMandates(accountId, {
      tenures: tenuresForAccount(accountId),
      links: linksForAccount(accountId),
    });
  } catch {
    // Retry on next write / hydrate.
  }
}

/** Debounce push tras mutaciones locales. */
export function scheduleMandatePush(accountId: string | null | undefined): void {
  if (!accountId) return;
  if (syncTimer) clearTimeout(syncTimer);
  syncTimer = setTimeout(() => {
    void pushMandateToServer(accountId);
  }, 400);
}

export async function ensureMandateHydrated(accountId: string): Promise<void> {
  if (!accountId || hydratedAccounts.has(accountId)) return;
  // Si hay datos locales y BD vacía, push primero; si BD tiene datos, pull gana.
  const localTenures = tenuresForAccount(accountId);
  try {
    const res = await api.getAccountMandates(accountId);
    if ((res.data.tenures?.length ?? 0) === 0 && localTenures.length > 0) {
      await pushMandateToServer(accountId);
      hydratedAccounts.add(accountId);
      return;
    }
  } catch {
    /* fall through to hydrate attempt */
  }
  await hydrateMandateFromServer(accountId);
}
