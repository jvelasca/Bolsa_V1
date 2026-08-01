import type { AlertCondition, AlertPriceSource, PriceAlertDto } from '@bolsa/shared';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Bell, RotateCcw, Trash2 } from 'lucide-react';
import { useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { api } from '@/lib/api';
import { formatPrice } from '@/features/charts/chart-utils';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { cn } from '@/lib/utils';
import { SignalAlertsSection } from '@/features/alerts/signal-alerts-section';

const conditionLabels: Record<AlertCondition, string> = {
  above: 'Por encima de',
  below: 'Por debajo de',
};

const priceSourceLabels: Record<AlertPriceSource, string> = {
  daily_close: 'Cierre diario (Yahoo)',
  xtb_last: 'XTB tiempo real',
};

type AlertFilter = 'active' | 'history' | 'all';

export function AlertsPage() {
  const queryClient = useQueryClient();
  const [searchParams] = useSearchParams();
  const preselectedInstrumentId = searchParams.get('instrumentId') ?? '';

  const [instrumentId, setInstrumentId] = useState(preselectedInstrumentId);
  const [condition, setCondition] = useState<AlertCondition>('above');
  const [priceSource, setPriceSource] = useState<AlertPriceSource>('daily_close');
  const [targetPrice, setTargetPrice] = useState('');
  const [note, setNote] = useState('');
  const [filter, setFilter] = useState<AlertFilter>('active');

  const instrumentsQuery = useQuery({
    queryKey: ['instruments'],
    queryFn: api.getInstruments,
  });

  const alertsQuery = useQuery({
    queryKey: ['alerts'],
    queryFn: () => api.getAlerts(),
    refetchInterval: 30_000,
  });

  const marketQuery = useQuery({
    queryKey: ['market-providers'],
    queryFn: api.getMarketProviders,
    staleTime: 60_000,
  });

  const xtbProvider = marketQuery.data?.data.find((provider) => provider.id === 'xtb');
  const xtbReady = Boolean(xtbProvider?.enabled && xtbProvider.healthy);

  const createMutation = useMutation({
    mutationFn: api.createAlert,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['alerts'] });
      setTargetPrice('');
      setNote('');
    },
  });

  const deleteMutation = useMutation({
    mutationFn: api.deleteAlert,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['alerts'] });
    },
  });

  const reactivateMutation = useMutation({
    mutationFn: api.reactivateAlert,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['alerts'] });
    },
  });

  const instruments = instrumentsQuery.data?.data ?? [];
  const alerts = alertsQuery.data?.data ?? [];

  const filteredAlerts = useMemo(() => {
    if (filter === 'active') {
      return alerts.filter((alert) => alert.isActive);
    }
    if (filter === 'history') {
      return alerts.filter((alert) => !alert.isActive);
    }
    return alerts;
  }, [alerts, filter]);

  const instrumentOptions = useMemo(
    () =>
      [...instruments]
        .sort((a, b) => a.symbol.localeCompare(b.symbol))
        .map((item) => ({ id: item.id, label: `${item.symbol} — ${item.name}` })),
    [instruments],
  );

  function handleCreate(event: React.FormEvent) {
    event.preventDefault();
    const price = Number.parseFloat(targetPrice.replace(',', '.'));
    if (!instrumentId || !Number.isFinite(price) || price <= 0) {
      return;
    }
    createMutation.mutate({
      instrumentId,
      condition,
      priceSource,
      targetPrice: price,
      note: note.trim() || undefined,
    });
  }

  return (
    <div className="space-y-6 p-4">
      <div>
        <h2 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
          <Bell className="h-6 w-6 text-primary" />
          Alertas de precio
        </h2>
        <p className="text-sm text-muted-foreground">
          Notificaciones por cierre diario (Yahoo) o cotización XTB en tiempo real.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Nueva alerta</CardTitle>
          <CardDescription>
            Elige la fuente de precio según el tipo de alerta que necesites.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleCreate} className="grid gap-3 md:grid-cols-2 lg:grid-cols-5">
            <label className="flex flex-col gap-1 text-xs md:col-span-2">
              Instrumento
              <select
                value={instrumentId}
                onChange={(e) => setInstrumentId(e.target.value)}
                className="rounded border border-border bg-background px-2 py-1.5 text-sm"
                required
              >
                <option value="">Seleccionar…</option>
                {instrumentOptions.map((option) => (
                  <option key={option.id} value={option.id}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-1 text-xs">
              Condición
              <select
                value={condition}
                onChange={(e) => setCondition(e.target.value as AlertCondition)}
                className="rounded border border-border bg-background px-2 py-1.5 text-sm"
              >
                <option value="above">{conditionLabels.above}</option>
                <option value="below">{conditionLabels.below}</option>
              </select>
            </label>
            <label className="flex flex-col gap-1 text-xs">
              Fuente de precio
              <select
                value={priceSource}
                onChange={(e) => setPriceSource(e.target.value as AlertPriceSource)}
                className="rounded border border-border bg-background px-2 py-1.5 text-sm"
              >
                <option value="daily_close">{priceSourceLabels.daily_close}</option>
                <option value="xtb_last">{priceSourceLabels.xtb_last}</option>
              </select>
            </label>
            <label className="flex flex-col gap-1 text-xs">
              Precio objetivo (€)
              <input
                type="text"
                inputMode="decimal"
                value={targetPrice}
                onChange={(e) => setTargetPrice(e.target.value)}
                placeholder="12,50"
                className="rounded border border-border bg-background px-2 py-1.5 text-sm"
                required
              />
            </label>
            <label className="flex flex-col gap-1 text-xs md:col-span-2 lg:col-span-1">
              Nota (opcional)
              <input
                type="text"
                value={note}
                onChange={(e) => setNote(e.target.value)}
                className="rounded border border-border bg-background px-2 py-1.5 text-sm"
              />
            </label>
            {priceSource === 'xtb_last' && !xtbReady && (
              <p className="text-xs text-amber-400 md:col-span-2 lg:col-span-5">
                XTB no disponible ({xtbProvider?.message ?? 'sin bridge'}). La alerta se creará pero
                no se evaluará hasta que el bridge esté activo.
              </p>
            )}
            <div className="flex items-end md:col-span-2 lg:col-span-5">
              <button
                type="submit"
                disabled={createMutation.isPending}
                className="rounded bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-50"
              >
                {createMutation.isPending ? 'Creando…' : 'Crear alerta'}
              </button>
              {createMutation.isError && (
                <span className="ml-3 text-xs text-red-400">
                  {(createMutation.error as Error).message}
                </span>
              )}
            </div>
          </form>
        </CardContent>
      </Card>

      <SignalAlertsSection />

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Alertas configuradas</CardTitle>
          <CardDescription>
            {alerts.filter((a) => a.isActive).length} activas ·{' '}
            {alerts.filter((a) => !a.isActive).length} en historial
          </CardDescription>
          <div className="flex gap-1 pt-2">
            {(
              [
                ['active', 'Activas'],
                ['history', 'Historial'],
                ['all', 'Todas'],
              ] as const
            ).map(([value, label]) => (
              <button
                key={value}
                type="button"
                onClick={() => setFilter(value)}
                className={cn(
                  'rounded px-2 py-1 text-xs',
                  filter === value ? 'bg-primary text-primary-foreground' : 'hover:bg-accent',
                )}
              >
                {label}
              </button>
            ))}
          </div>
        </CardHeader>
        <CardContent>
          {alertsQuery.isLoading && (
            <p className="text-sm text-muted-foreground">Cargando alertas…</p>
          )}
          {!alertsQuery.isLoading && filteredAlerts.length === 0 && (
            <p className="text-sm text-muted-foreground">
              {filter === 'history' ? 'No hay alertas disparadas.' : 'No hay alertas en esta vista.'}
            </p>
          )}
          {filteredAlerts.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-xs text-muted-foreground">
                    <th className="pb-2 pr-3">Símbolo</th>
                    <th className="pb-2 pr-3">Fuente</th>
                    <th className="pb-2 pr-3">Condición</th>
                    <th className="pb-2 pr-3">Objetivo</th>
                    <th className="pb-2 pr-3">Estado</th>
                    <th className="pb-2 pr-3">Disparada</th>
                    <th className="pb-2" />
                  </tr>
                </thead>
                <tbody>
                  {filteredAlerts.map((alert) => (
                    <AlertRow
                      key={alert.id}
                      alert={alert}
                      onDelete={() => deleteMutation.mutate(alert.id)}
                      onReactivate={() => reactivateMutation.mutate(alert.id)}
                      deleting={deleteMutation.isPending}
                      reactivating={reactivateMutation.isPending}
                    />
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function AlertRow({
  alert,
  onDelete,
  onReactivate,
  deleting,
  reactivating,
}: {
  alert: PriceAlertDto;
  onDelete: () => void;
  onReactivate: () => void;
  deleting: boolean;
  reactivating: boolean;
}) {
  return (
    <tr className="border-b border-border/60">
      <td className="py-2 pr-3">
        <Link to={`/instruments/${alert.instrumentId}`} className="font-medium hover:text-primary">
          {alert.symbol}
        </Link>
        {alert.note && <p className="text-xs text-muted-foreground">{alert.note}</p>}
      </td>
      <td className="py-2 pr-3 text-xs">{priceSourceLabels[alert.priceSource]}</td>
      <td className="py-2 pr-3">{conditionLabels[alert.condition]}</td>
      <td className="py-2 pr-3">{formatPrice(alert.targetPrice)}</td>
      <td className="py-2 pr-3">
        <span
          className={cn(
            'rounded px-1.5 py-0.5 text-xs',
            alert.isActive ? 'bg-emerald-500/15 text-emerald-400' : 'bg-muted text-muted-foreground',
          )}
        >
          {alert.isActive ? 'Activa' : 'Disparada'}
        </span>
      </td>
      <td className="py-2 pr-3 text-xs text-muted-foreground">
        {alert.triggeredAt ? (
          <>
            {formatPrice(alert.triggeredPrice ?? 0)}
            <br />
            {new Date(alert.triggeredAt).toLocaleString('es-ES')}
          </>
        ) : (
          '—'
        )}
      </td>
      <td className="py-2 text-right">
        <div className="flex justify-end gap-1">
          {!alert.isActive && (
            <button
              type="button"
              onClick={onReactivate}
              disabled={reactivating}
              className="rounded p-1 text-muted-foreground hover:bg-accent hover:text-primary"
              title="Reactivar"
            >
              <RotateCcw className="h-4 w-4" />
            </button>
          )}
          <button
            type="button"
            onClick={onDelete}
            disabled={deleting}
            className="rounded p-1 text-muted-foreground hover:bg-accent hover:text-red-400"
            title="Eliminar"
          >
            <Trash2 className="h-4 w-4" />
          </button>
        </div>
      </td>
    </tr>
  );
}
