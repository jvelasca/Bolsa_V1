import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { RotateCcw, Trash2, Zap } from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  ALERT_CHANNEL_LABELS,
  BACKTEST_STRATEGIES,
  DEFAULT_ALERT_CHANNELS,
  SIGNAL_KIND_LABELS,
  type AlertChannelType,
  type BacktestStrategyType,
  type SignalAlertSubscriptionDto,
  type SignalKind,
} from "@bolsa/shared";
import { api } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import { formatPrice } from "@/features/charts/chart-utils";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

type StrategySource = "preset" | "saved";

const kindOptions: SignalKind[] = [
  "entry_long",
  "exit",
  "entry_short",
  "watch",
];
const channelOptions: AlertChannelType[] = ["toast", "webhook", "email"];

export function SignalAlertsSection() {
  const queryClient = useQueryClient();
  const [instrumentId, setInstrumentId] = useState("");
  const [strategySource, setStrategySource] =
    useState<StrategySource>("preset");
  const [presetKey, setPresetKey] =
    useState<BacktestStrategyType>("sma_crossover");
  const [savedStrategyId, setSavedStrategyId] = useState("");
  const [note, setNote] = useState("");
  const [kinds, setKinds] = useState<SignalKind[]>(["entry_long", "exit"]);
  const [channels, setChannels] = useState<AlertChannelType[]>([
    ...DEFAULT_ALERT_CHANNELS,
  ]);
  const [webhookUrl, setWebhookUrl] = useState("");
  const [emailTo, setEmailTo] = useState("");

  const instrumentsQuery = useQuery({
    queryKey: ["instruments"],
    queryFn: api.getInstruments,
  });

  const strategiesQuery = useQuery({
    queryKey: ["strategies"],
    queryFn: api.getStrategies,
  });

  const signalAlertsQuery = useQuery({
    queryKey: ["signal-alerts"],
    queryFn: () => api.getSignalAlerts(),
    refetchInterval: 30_000,
  });

  const createMutation = useMutation({
    mutationFn: api.createSignalAlert,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["signal-alerts"] });
      setNote("");
    },
  });

  const deleteMutation = useMutation({
    mutationFn: api.deleteSignalAlert,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["signal-alerts"] });
    },
  });

  const resetMutation = useMutation({
    mutationFn: api.resetSignalAlertDedupe,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["signal-alerts"] });
    },
  });

  const instruments = useMemo(
    () => instrumentsQuery.data?.data ?? [],
    [instrumentsQuery.data?.data],
  );
  const strategies = strategiesQuery.data?.data ?? [];
  const subscriptions = signalAlertsQuery.data?.data ?? [];

  const instrumentOptions = useMemo(
    () =>
      [...instruments]
        .sort((a, b) => a.symbol.localeCompare(b.symbol))
        .map((item) => ({
          id: item.id,
          label: `${item.symbol} — ${item.name}`,
        })),
    [instruments],
  );

  function toggleKind(kind: SignalKind) {
    setKinds((current) =>
      current.includes(kind)
        ? current.filter((item) => item !== kind)
        : [...current, kind],
    );
  }

  function toggleChannel(channel: AlertChannelType) {
    setChannels((current) => {
      if (current.includes(channel)) {
        const next = current.filter((item) => item !== channel);
        return next.length > 0 ? next : [...DEFAULT_ALERT_CHANNELS];
      }
      return [...current, channel];
    });
  }

  function handleCreate(event: React.FormEvent) {
    event.preventDefault();
    if (!instrumentId || kinds.length === 0) return;
    if (strategySource === "saved" && !savedStrategyId) return;
    if (channels.includes("webhook") && !webhookUrl.trim()) return;
    if (channels.includes("email") && !emailTo.trim()) return;

    createMutation.mutate({
      instrumentId,
      signalKinds: kinds,
      channels,
      webhookUrl: channels.includes("webhook") ? webhookUrl.trim() : undefined,
      emailTo: channels.includes("email") ? emailTo.trim() : undefined,
      note: note.trim() || undefined,
      ...(strategySource === "saved"
        ? { strategyDefinitionId: savedStrategyId }
        : { presetKey }),
    });
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Zap className="h-4 w-4 text-primary" />
          Alertas de estrategia
        </CardTitle>
        <CardDescription>
          Señales en cierre de barra — toast en app, webhook JSON o email
          (SC-6).
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <form onSubmit={handleCreate} className="grid gap-3 md:grid-cols-2">
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

          <fieldset className="space-y-2 md:col-span-2">
            <legend className="text-xs font-medium text-muted-foreground">
              Estrategia
            </legend>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="radio"
                checked={strategySource === "preset"}
                onChange={() => setStrategySource("preset")}
              />
              Preset
            </label>
            {strategySource === "preset" && (
              <select
                value={presetKey}
                onChange={(e) =>
                  setPresetKey(e.target.value as BacktestStrategyType)
                }
                className="ml-6 w-[calc(100%-1.5rem)] rounded-md border border-border bg-background px-2 py-1.5 text-sm"
              >
                {Object.entries(BACKTEST_STRATEGIES).map(([key, meta]) => (
                  <option key={key} value={key}>
                    {meta.label}
                  </option>
                ))}
              </select>
            )}
            <label className="flex items-center gap-2 text-sm">
              <input
                type="radio"
                checked={strategySource === "saved"}
                onChange={() => setStrategySource("saved")}
              />
              Guardada
            </label>
            {strategySource === "saved" && (
              <select
                value={savedStrategyId}
                onChange={(e) => setSavedStrategyId(e.target.value)}
                className="ml-6 w-[calc(100%-1.5rem)] rounded-md border border-border bg-background px-2 py-1.5 text-sm"
              >
                <option value="">Seleccionar…</option>
                {strategies.map((strategy) => (
                  <option key={strategy.id} value={strategy.id}>
                    {strategy.name}
                  </option>
                ))}
              </select>
            )}
          </fieldset>

          <fieldset className="md:col-span-2">
            <legend className="mb-2 text-xs font-medium text-muted-foreground">
              Tipos de señal
            </legend>
            <div className="flex flex-wrap gap-2">
              {kindOptions.map((kind) => (
                <label key={kind} className="flex items-center gap-1 text-xs">
                  <input
                    type="checkbox"
                    checked={kinds.includes(kind)}
                    onChange={() => toggleKind(kind)}
                  />
                  {SIGNAL_KIND_LABELS[kind]}
                </label>
              ))}
            </div>
          </fieldset>

          <fieldset className="md:col-span-2">
            <legend className="mb-2 text-xs font-medium text-muted-foreground">
              Canales de entrega
            </legend>
            <div className="flex flex-wrap gap-2">
              {channelOptions.map((channel) => (
                <label
                  key={channel}
                  className="flex items-center gap-1 text-xs"
                >
                  <input
                    type="checkbox"
                    checked={channels.includes(channel)}
                    onChange={() => toggleChannel(channel)}
                  />
                  {ALERT_CHANNEL_LABELS[channel]}
                </label>
              ))}
            </div>
          </fieldset>

          {channels.includes("webhook") && (
            <label className="flex flex-col gap-1 text-xs md:col-span-2">
              Webhook URL
              <input
                type="url"
                value={webhookUrl}
                onChange={(e) => setWebhookUrl(e.target.value)}
                placeholder="https://hooks.example.com/signal"
                className="rounded border border-border bg-background px-2 py-1.5 text-sm"
                required
              />
            </label>
          )}

          {channels.includes("email") && (
            <label className="flex flex-col gap-1 text-xs md:col-span-2">
              Email destino
              <input
                type="email"
                value={emailTo}
                onChange={(e) => setEmailTo(e.target.value)}
                placeholder="tu@email.com"
                className="rounded border border-border bg-background px-2 py-1.5 text-sm"
                required
              />
            </label>
          )}

          <label className="flex flex-col gap-1 text-xs md:col-span-2">
            Nota (opcional)
            <input
              type="text"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              className="rounded border border-border bg-background px-2 py-1.5 text-sm"
            />
          </label>

          <div className="md:col-span-2">
            <button
              type="submit"
              disabled={createMutation.isPending || kinds.length === 0}
              className="rounded bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-50"
            >
              {createMutation.isPending ? "Creando…" : "Suscribir alerta"}
            </button>
            {createMutation.isError && (
              <span className="ml-3 text-xs text-red-400">
                {(createMutation.error as Error).message}
              </span>
            )}
          </div>
        </form>

        {signalAlertsQuery.isLoading && (
          <p className="text-sm text-muted-foreground">
            Cargando suscripciones…
          </p>
        )}

        {!signalAlertsQuery.isLoading && subscriptions.length === 0 && (
          <p className="text-sm text-muted-foreground">
            No hay suscripciones activas.
          </p>
        )}

        {subscriptions.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs text-muted-foreground">
                  <th className="pb-2 pr-3">Símbolo</th>
                  <th className="pb-2 pr-3">Estrategia</th>
                  <th className="pb-2 pr-3">Señales</th>
                  <th className="pb-2 pr-3">Canales</th>
                  <th className="pb-2 pr-3">Última</th>
                  <th className="pb-2" />
                </tr>
              </thead>
              <tbody>
                {subscriptions.map((sub) => (
                  <SignalAlertRow
                    key={sub.id}
                    subscription={sub}
                    onDelete={() => deleteMutation.mutate(sub.id)}
                    onReset={() => resetMutation.mutate(sub.id)}
                    deleting={deleteMutation.isPending}
                    resetting={resetMutation.isPending}
                  />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function SignalAlertRow({
  subscription,
  onDelete,
  onReset,
  deleting,
  resetting,
}: {
  subscription: SignalAlertSubscriptionDto;
  onDelete: () => void;
  onReset: () => void;
  deleting: boolean;
  resetting: boolean;
}) {
  const strategyLabel =
    subscription.presetKey != null
      ? BACKTEST_STRATEGIES[subscription.presetKey].label
      : (subscription.strategyDefinitionId?.slice(0, 8) ?? "—");

  return (
    <tr className="border-b border-border/60">
      <td className="py-2 pr-3">
        <Link
          to={`/instruments/${subscription.instrumentId}`}
          className="font-medium hover:text-primary"
        >
          {subscription.symbol}
        </Link>
        {subscription.note && (
          <p className="text-xs text-muted-foreground">{subscription.note}</p>
        )}
      </td>
      <td className="py-2 pr-3 text-xs">{strategyLabel}</td>
      <td className="py-2 pr-3 text-xs">
        {subscription.signalKinds
          .map((kind) => SIGNAL_KIND_LABELS[kind])
          .join(", ")}
      </td>
      <td className="py-2 pr-3 text-xs">
        {subscription.channels
          .map((channel) => ALERT_CHANNEL_LABELS[channel])
          .join(", ")}
        {subscription.webhookUrl && (
          <p
            className="truncate text-[10px] text-muted-foreground"
            title={subscription.webhookUrl}
          >
            {subscription.webhookUrl}
          </p>
        )}
        {subscription.emailTo && (
          <p className="text-[10px] text-muted-foreground">
            {subscription.emailTo}
          </p>
        )}
      </td>
      <td className="py-2 pr-3 text-xs text-muted-foreground">
        {subscription.lastTriggeredAt && subscription.lastSignalKind ? (
          <>
            {SIGNAL_KIND_LABELS[subscription.lastSignalKind]} ·{" "}
            {formatPrice(subscription.lastSignalPrice ?? 0)}
            <br />
            {formatDateTime(subscription.lastTriggeredAt)}
          </>
        ) : (
          "—"
        )}
      </td>
      <td className="py-2 text-right">
        <div className="flex justify-end gap-1">
          <button
            type="button"
            onClick={onReset}
            disabled={resetting}
            className="rounded p-1 text-muted-foreground hover:bg-accent hover:text-primary"
            title="Permitir re-disparo en la barra actual"
          >
            <RotateCcw className="h-4 w-4" />
          </button>
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
