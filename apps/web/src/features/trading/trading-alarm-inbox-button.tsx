/**
 * Popover inbox alarmas Radar (B1) en la barra Trading.
 * Filtrado por cuenta activa DEMO · abrir valor · ack · Proponer F3.
 */

import { useMemo, useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { Bell, BrainCircuit, Loader2 } from 'lucide-react';
import { SIGNAL_KIND_LABELS } from '@bolsa/shared';
import { Button } from '@/components/ui/button';
import { IconButton } from '@/components/ui/icon-button';
import { useActiveAccount } from '@/features/accounts/use-active-account';
import { openHitInTrading } from '@/features/screeners/open-hit-in-trading';
import { api } from '@/lib/api';
import { cn } from '@/lib/utils';
import { useAlertsStore } from '@/stores/alerts-store';
import {
  openHelpAiPlatform,
  type SupervisedProposePayload,
  useSupervisedF3QueueStore,
} from '@/stores/supervised-f3-queue-store';
import {
  itemsForAccount,
  unreadCountForAccount,
  useTrackerAlarmInboxStore,
  type TrackerAlarmInboxItem,
} from '@/stores/tracker-alarm-inbox-store';
import { useWorkspaceStore } from '@/stores/workspace-store';
import { PAPER_PATH_SUPERVISED } from '@/features/settings/paper-paths-copy';

function kindLabel(kind: string): string {
  return (SIGNAL_KIND_LABELS as Record<string, string>)[kind] ?? kind;
}

function formatWhen(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleString(undefined, {
      day: '2-digit',
      month: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return iso;
  }
}

function AlarmRow({
  item,
  onOpen,
  onAck,
  onPropose,
  proposePending,
}: {
  item: TrackerAlarmInboxItem;
  onOpen: () => void;
  onAck: () => void;
  onPropose: () => void;
  proposePending: boolean;
}) {
  const unread = !item.ackedAt;
  return (
    <li
      className={cn(
        'flex flex-col gap-1 border-b border-border/60 px-2.5 py-2 last:border-0',
        unread ? 'bg-primary/5' : 'opacity-80',
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <button
          type="button"
          className="min-w-0 text-left hover:underline"
          onClick={onOpen}
          title="Abrir en Trading"
        >
          <p className="truncate text-[11px] font-medium text-foreground">
            {item.symbol}
            <span className="ml-1.5 font-normal text-muted-foreground">
              {kindLabel(item.signalKind)}
            </span>
          </p>
          <p className="text-[10px] tabular-nums text-muted-foreground">
            {item.price != null ? `@ ${item.price.toFixed(2)}` : '—'} · {formatWhen(item.createdAt)}
          </p>
        </button>
        <div className="flex shrink-0 flex-col items-end gap-0.5">
          <Button
            type="button"
            size="sm"
            variant="secondary"
            className="h-6 gap-0.5 px-1.5 text-[10px]"
            disabled={proposePending}
            title={PAPER_PATH_SUPERVISED.blurb}
            onClick={onPropose}
          >
            {proposePending ? (
              <Loader2 className="h-3 w-3 animate-spin" aria-hidden />
            ) : (
              <BrainCircuit className="h-3 w-3" aria-hidden />
            )}
            F3
          </Button>
          {unread ? (
            <Button
              type="button"
              size="sm"
              variant="ghost"
              className="h-5 px-1.5 text-[10px]"
              onClick={onAck}
            >
              OK
            </Button>
          ) : (
            <span className="text-[9px] uppercase text-muted-foreground">visto</span>
          )}
        </div>
      </div>
    </li>
  );
}

export function TradingAlarmInboxButton({ className }: { className?: string }) {
  const [open, setOpen] = useState(false);
  const [pendingId, setPendingId] = useState<string | null>(null);
  const navigate = useNavigate();
  const { effectiveAccountId } = useActiveAccount();
  const items = useTrackerAlarmInboxStore((s) => s.items);
  const ack = useTrackerAlarmInboxStore((s) => s.ack);
  const ackAllForAccount = useTrackerAlarmInboxStore((s) => s.ackAllForAccount);
  const clearForAccount = useTrackerAlarmInboxStore((s) => s.clearForAccount);
  const pushToast = useAlertsStore((s) => s.pushToast);
  const enqueue = useSupervisedF3QueueStore((s) => s.enqueue);
  const setActive = useSupervisedF3QueueStore((s) => s.setActive);
  const openChartTab = useWorkspaceStore((s) => s.openChartTab);
  const updateChartTimeframe = useWorkspaceStore((s) => s.updateChartTimeframe);
  const focusInstrumentFromList = useWorkspaceStore((s) => s.focusInstrumentFromList);

  const accountItems = useMemo(
    () => itemsForAccount(items, effectiveAccountId),
    [items, effectiveAccountId],
  );
  const unread = unreadCountForAccount(items, effectiveAccountId);

  const proposeMutation = useMutation({
    mutationFn: async (item: TrackerAlarmInboxItem) => {
      if (!effectiveAccountId) throw new Error('Sin cuenta DEMO activa');
      const res = await api.proposeRecommendation({
        instrumentId: item.instrumentId,
        symbol: item.symbol,
        accountId: effectiveAccountId,
        suggestedQuantity: 1,
        includeFundamentals: true,
        includeMacro: true,
        includeEvidence: true,
        includeNews: true,
        ...(item.strategyDefinitionId
          ? { strategyOrSignalRef: item.strategyDefinitionId }
          : {}),
      });
      return {
        item,
        payload: {
          ...(res.data as SupervisedProposePayload),
          source: 'alarm',
        } satisfies SupervisedProposePayload,
      };
    },
    onMutate: (item) => {
      setPendingId(item.id);
    },
    onSuccess: ({ item, payload }) => {
      const id = enqueue(payload, {
        symbol: payload.symbol ?? item.symbol,
        origin: 'alarm',
        scanId: item.scanId,
      });
      setActive(id);
      ack(item.id);
      pushToast(
        `${PAPER_PATH_SUPERVISED.cta} · ${item.symbol}: ${payload.action} → Supervisado F3`,
      );
      openHelpAiPlatform({ panel: 'supervised-f3' });
      setOpen(false);
    },
    onError: (err: Error, item) => {
      pushToast(`F3 · ${item.symbol}: ${err.message}`);
    },
    onSettled: () => {
      setPendingId(null);
    },
  });

  function handleOpen(item: TrackerAlarmInboxItem) {
    openHitInTrading(
      navigate,
      { openChartTab, updateChartTimeframe, focusInstrumentFromList },
      { instrumentId: item.instrumentId, symbol: item.symbol },
      {
        timeframe: item.timeframe ?? undefined,
        listId: item.listId ?? undefined,
      },
    );
    ack(item.id);
    setOpen(false);
  }

  return (
    <div className={cn('relative shrink-0', className)}>
      <IconButton
        icon={Bell}
        title={
          unread > 0
            ? `Alarmas Radar · ${unread} sin leer (cuenta activa DEMO)`
            : 'Alarmas Radar (entrada/salida · cuenta activa)'
        }
        onClick={() => setOpen((v) => !v)}
        className={cn(unread > 0 && 'text-amber-700 dark:text-amber-300')}
      />
      {unread > 0 ? (
        <span
          className="pointer-events-none absolute -right-0.5 -top-0.5 flex h-3.5 min-w-3.5 items-center justify-center rounded-full bg-amber-500 px-0.5 text-[8px] font-semibold text-white"
          aria-hidden
        >
          {unread > 9 ? '9+' : unread}
        </span>
      ) : null}

      {open ? (
        <>
          <button
            type="button"
            className="fixed inset-0 z-[90] cursor-default"
            aria-label="Cerrar alarmas"
            onClick={() => setOpen(false)}
          />
          <div
            role="dialog"
            aria-label="Inbox alarmas Radar"
            className="absolute bottom-8 right-0 z-[91] w-[min(20rem,calc(100vw-1.5rem))] overflow-hidden rounded-md border border-border bg-card shadow-lg"
          >
            <div className="flex items-center justify-between gap-2 border-b border-border px-2.5 py-2">
              <div>
                <p className="text-[11px] font-semibold text-foreground">Alarmas Radar</p>
                <p className="text-[9px] text-muted-foreground">
                  DEMO activa · scan / on_bar_close · F3 = Supervisado
                </p>
              </div>
              <div className="flex gap-1">
                {unread > 0 && effectiveAccountId ? (
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    className="h-6 px-1.5 text-[10px]"
                    onClick={() => ackAllForAccount(effectiveAccountId)}
                  >
                    Marcar leídas
                  </Button>
                ) : null}
                {accountItems.length > 0 && effectiveAccountId ? (
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    className="h-6 px-1.5 text-[10px] text-muted-foreground"
                    onClick={() => clearForAccount(effectiveAccountId)}
                  >
                    Vaciar
                  </Button>
                ) : null}
              </div>
            </div>
            {!effectiveAccountId ? (
              <p className="px-2.5 py-3 text-[11px] text-muted-foreground">
                Selecciona una cuenta DEMO activa.
              </p>
            ) : accountItems.length === 0 ? (
              <p className="px-2.5 py-3 text-[11px] text-muted-foreground">
                Sin alarmas. Scan manual o programado (on_bar_close) con política inform/alert.
              </p>
            ) : (
              <ul className="max-h-64 overflow-y-auto">
                {accountItems.slice(0, 30).map((item) => (
                  <AlarmRow
                    key={item.id}
                    item={item}
                    onOpen={() => handleOpen(item)}
                    onAck={() => ack(item.id)}
                    onPropose={() => proposeMutation.mutate(item)}
                    proposePending={pendingId === item.id}
                  />
                ))}
              </ul>
            )}
          </div>
        </>
      ) : null}
    </div>
  );
}
