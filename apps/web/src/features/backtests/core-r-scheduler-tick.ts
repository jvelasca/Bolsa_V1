/**
 * Ejecuta un tick CORE-R: informe Lista AUTO + PnL DEMO → cola.
 *
 * Usado por Monitor (`scope=monitor`) y PlatformShell (`scope=shell` vía
 * `CoreRSchedulerHost`). Respeta `intervalMinutes` / `listId` / enabled.
 * No lanza Lista AUTO · no pisa TOP · no auto-paper D.
 *
 * @see core-r-scheduler.ts · docs/engineering/operativa-test-plan-2026-07-31.md
 */

import {
  buildCoreRPaperPnlReviewRow,
  coreRAccountReturnPct,
  readCoreRReport,
  type CoreRPaperPnlSnap,
  type CoreRReportRow,
} from '@/features/backtests/core-r-judgment';
import {
  coreRSchedulerDue,
  emitCoreRSchedulerTick,
  loadCoreRSchedulerPrefs,
  markCoreRSchedulerTick,
} from '@/features/backtests/core-r-scheduler';
import {
  buildStrategyMonitorRow,
  sliceMonitorInstruments,
} from '@/features/backtests/strategy-monitor';
import { api } from '@/lib/api';
import { useCoreRReviewQueueStore } from '@/stores/core-r-review-queue-store';

export type CoreRTickResult = {
  listId: string;
  added: number;
  skipped: boolean;
  reason?: string;
};

async function fetchPnlExtraRows(listId: string): Promise<CoreRReportRow[]> {
  const extras: CoreRReportRow[] = [];
  try {
    const [listRes, instrumentsRes, accountsRes] = await Promise.all([
      api.getList(listId),
      api.getInstruments(),
      api.getAccounts(),
    ]);
    const ids = listRes.data?.instrumentIds ?? [];
    const byId = new Map((instrumentsRes.data ?? []).map((i) => [i.id, i] as const));
    const accounts = Array.isArray(accountsRes.data) ? accountsRes.data : [];
    const instruments = sliceMonitorInstruments(
      ids.map((id) => {
        const inst = byId.get(id);
        return { id, symbol: inst?.symbol ?? id.slice(0, 8), name: inst?.name };
      }),
    );

    const tops = await Promise.all(
      instruments.map((inst) =>
        api.getInstrumentStrategyTop(inst.id, '1d').catch(() => null),
      ),
    );

    const rows = instruments.map((inst, i) =>
      buildStrategyMonitorRow({
        instrument: inst,
        timeframe: '1d',
        top: tops[i]?.data ?? null,
        accounts,
        queue: [],
      }),
    );

    const withPaper = rows.filter((r) => r.paperAccount?.id && r.top?.slots?.length);
    const summaries = await Promise.all(
      withPaper.map((r) =>
        api.getAccountSummary(r.paperAccount!.id).catch(() => null),
      ),
    );

    withPaper.forEach((row, i) => {
      const summary = summaries[i]?.data;
      if (!summary || !row.paperAccount) return;
      const returnPct = coreRAccountReturnPct(
        summary.account.initialDeposit,
        summary.totalEquity,
      );
      if (returnPct == null) return;
      const pnl: CoreRPaperPnlSnap = {
        accountId: row.paperAccount.id,
        returnPct,
        totalUnrealizedPnl: summary.totalUnrealizedPnl,
        totalEquity: summary.totalEquity,
        initialDeposit: summary.account.initialDeposit,
      };
      const extra = buildCoreRPaperPnlReviewRow({
        instrumentId: row.instrumentId,
        symbol: row.symbol,
        timeframe: row.timeframe,
        pnl,
        slot1RunId: row.slot1RunId,
      });
      if (extra) extras.push(extra);
    });
  } catch {
    // best-effort PnL
  }
  return extras;
}

/**
 * @param force — ignora due/interval (tests / botón manual).
 * @param scopeFilter — solo corre si prefs.scope coincide (shell host vs monitor).
 */
export async function runCoreRSchedulerTick(opts?: {
  force?: boolean;
  scopeFilter?: 'monitor' | 'shell';
  includePnl?: boolean;
}): Promise<CoreRTickResult | null> {
  const prefs = loadCoreRSchedulerPrefs();
  if (!prefs.enabled && !opts?.force) {
    return { listId: '', added: 0, skipped: true, reason: 'disabled' };
  }
  if (opts?.scopeFilter && prefs.scope !== opts.scopeFilter && !opts.force) {
    return { listId: prefs.listId ?? '', added: 0, skipped: true, reason: 'scope' };
  }
  if (!prefs.listId) {
    return { listId: '', added: 0, skipped: true, reason: 'no_list' };
  }
  if (!opts?.force && !coreRSchedulerDue(prefs)) {
    return { listId: prefs.listId, added: 0, skipped: true, reason: 'not_due' };
  }

  const report = readCoreRReport(prefs.listId);
  const extras =
    opts?.includePnl === false ? [] : await fetchPnlExtraRows(prefs.listId);
  const added = useCoreRReviewQueueStore
    .getState()
    .syncFromReport(prefs.listId, report, extras);
  markCoreRSchedulerTick(prefs);
  emitCoreRSchedulerTick({
    listId: prefs.listId,
    added,
    at: new Date().toISOString(),
  });
  return { listId: prefs.listId, added, skipped: false };
}
