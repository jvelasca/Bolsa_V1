import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type {
  InstrumentDataStatusDto,
  InstrumentDbInventoryDto,
  InstrumentXtbValidationDto,
} from "@bolsa/shared";
import { formatPrice } from "@/features/charts/chart-utils";
import {
  DATA_STATUS_COLORS,
  DATA_STATUS_LABELS,
} from "@/features/charts/chart-database-panel";
import {
  formatSyncError,
  useInstrumentSync,
} from "@/features/instruments/use-instrument-sync";
import { api } from "@/lib/api";
import { formatDateTimeCompact, formatNumber } from "@/lib/format";
import { cn } from "@/lib/utils";

const XTB_RECOMMENDATION_LABELS: Record<string, string> = {
  aligned: "Alineado con BD",
  review: "Desviación notable — revisar",
  unavailable: "XTB no disponible",
  no_db_reference: "Sin cierre de referencia en BD",
};

const XTB_CARD_STYLES: Record<string, string> = {
  aligned: "border-emerald-500/40 bg-emerald-500/10",
  review: "border-amber-500/40 bg-amber-500/10",
  unavailable: "border-border bg-muted/30",
  no_db_reference: "border-sky-500/40 bg-sky-500/10",
};

function formatDateTime(iso: string | null) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return formatDateTimeCompact(d);
}

function SectionTitle({ children }: { children: string }) {
  return (
    <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
      {children}
    </p>
  );
}

function InventoryRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start justify-between gap-3 py-0.5 text-xs">
      <span className="text-muted-foreground">{label}</span>
      <span className="text-right tabular-nums">{value}</span>
    </div>
  );
}

function OhlcvLayersTable({
  layers,
}: {
  layers: InstrumentDbInventoryDto["ohlcvLayers"];
}) {
  if (layers.length === 0) {
    return (
      <p className="text-xs text-muted-foreground">
        Sin velas OHLCV persistidas.
      </p>
    );
  }

  return (
    <div className="overflow-x-auto rounded border border-border">
      <table className="w-full min-w-[420px] text-[11px]">
        <thead className="bg-muted/30 text-muted-foreground">
          <tr>
            <th className="px-2 py-1 text-left font-medium">TF</th>
            <th className="px-2 py-1 text-left font-medium">Fuente</th>
            <th className="px-2 py-1 text-right font-medium">Barras</th>
            <th className="px-2 py-1 text-right font-medium">Desde</th>
            <th className="px-2 py-1 text-right font-medium">Hasta</th>
          </tr>
        </thead>
        <tbody>
          {layers.map((layer) => (
            <tr
              key={`${layer.timeframe}-${layer.source}`}
              className="border-t border-border/60"
            >
              <td className="px-2 py-1">{layer.timeframe.toUpperCase()}</td>
              <td className="px-2 py-1">{layer.source}</td>
              <td className="px-2 py-1 text-right tabular-nums">
                {formatNumber(layer.barCount)}
              </td>
              <td className="px-2 py-1 text-right tabular-nums">
                {layer.firstDate ?? "—"}
              </td>
              <td className="px-2 py-1 text-right tabular-nums">
                {layer.lastDate ?? "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function XtbValidationCard({
  result,
  highlight,
}: {
  result: InstrumentXtbValidationDto;
  highlight?: boolean;
}) {
  const cardClass =
    XTB_CARD_STYLES[result.recommendation] ?? XTB_CARD_STYLES.unavailable;

  return (
    <section
      className={cn(
        "space-y-3 rounded-md border p-3",
        cardClass,
        highlight && "ring-2 ring-primary/40",
      )}
    >
      <div className="space-y-1">
        <p className="text-xs font-semibold text-foreground">
          {XTB_RECOMMENDATION_LABELS[result.recommendation] ??
            result.recommendation}
        </p>
        <p className="text-[11px] leading-relaxed text-muted-foreground">
          {result.message}
        </p>
      </div>

      <div className="rounded-md border border-border/60 bg-background/60 p-2">
        <p className="mb-2 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
          Comparación (solo lectura)
        </p>
        <div className="grid grid-cols-2 gap-2 text-center text-xs">
          <div className="rounded bg-muted/40 p-2">
            <p className="text-[10px] text-muted-foreground">
              Último cierre BD
            </p>
            <p className="text-sm font-semibold tabular-nums">
              {result.dbLastClose != null
                ? formatPrice(result.dbLastClose)
                : "—"}
            </p>
            <p className="text-[10px] text-muted-foreground">
              {result.dbLastDate ?? "sin fecha"}
            </p>
          </div>
          <div className="rounded bg-muted/40 p-2">
            <p className="text-[10px] text-muted-foreground">XTB en vivo</p>
            <p className="text-sm font-semibold tabular-nums">
              {result.xtbLast != null ? formatPrice(result.xtbLast) : "—"}
            </p>
            <p className="text-[10px] text-muted-foreground">
              {result.xtbTimestamp
                ? formatDateTime(result.xtbTimestamp)
                : "sin timestamp"}
            </p>
          </div>
        </div>
        {result.deviationPct != null && (
          <p className="mt-2 text-center text-xs tabular-nums">
            Desviación:{" "}
            <span
              className={cn(
                "font-semibold",
                Math.abs(result.deviationPct) < 2
                  ? "text-emerald-500"
                  : "text-amber-500",
              )}
            >
              {result.deviationPct >= 0 ? "+" : ""}
              {result.deviationPct.toFixed(2)}%
            </span>
          </p>
        )}
        {(result.xtbBid != null || result.xtbAsk != null) && (
          <p className="mt-1 text-center text-[10px] text-muted-foreground tabular-nums">
            Bid {result.xtbBid != null ? formatPrice(result.xtbBid) : "—"} · Ask{" "}
            {result.xtbAsk != null ? formatPrice(result.xtbAsk) : "—"}
          </p>
        )}
      </div>

      <div className="space-y-1 text-[10px] text-muted-foreground">
        <p>
          <span className="font-medium text-foreground">Qué NO cambia:</span>{" "}
          velas OHLCV, perfil Yahoo, posiciones ni listas.
        </p>
        <p>
          <span className="font-medium text-foreground">Qué SÍ se guarda:</span>{" "}
          este informe en{" "}
          <code className="text-[9px]">last_xtb_validation</code> y una línea en
          el historial sync (provider=xtb).
        </p>
        <p>Validado: {formatDateTime(result.validatedAt)}</p>
      </div>
    </section>
  );
}

export function InstrumentDbTab({
  instrumentId,
  dataStatus,
}: {
  instrumentId: string;
  dataStatus?: InstrumentDataStatusDto;
}) {
  const queryClient = useQueryClient();
  const syncMutation = useInstrumentSync(instrumentId);
  const xtbResultRef = useRef<HTMLDivElement | null>(null);
  const [lastSyncSummary, setLastSyncSummary] = useState<string | null>(null);

  const inventoryQuery = useQuery({
    queryKey: ["instrument-db-inventory", instrumentId],
    queryFn: () => api.getInstrumentDbInventory(instrumentId),
  });

  const marketProvidersQuery = useQuery({
    queryKey: ["market-providers"],
    queryFn: () => api.getMarketProviders(),
    staleTime: 30_000,
  });

  const xtbProvider = marketProvidersQuery.data?.data.find(
    (provider) => provider.id === "xtb",
  );

  const xtbMutation = useMutation({
    mutationFn: () => api.validateInstrumentXtb(instrumentId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ["instrument-db-inventory", instrumentId],
      });
    },
  });

  const inventory = inventoryQuery.data?.data;
  const xtbResult: InstrumentXtbValidationDto | undefined =
    xtbMutation.data?.data ??
    inventory?.instrument.lastXtbValidation ??
    undefined;
  const xtbJustValidated = Boolean(xtbMutation.data?.data);

  useEffect(() => {
    if (xtbJustValidated && xtbResultRef.current) {
      xtbResultRef.current.scrollIntoView({
        behavior: "smooth",
        block: "nearest",
      });
    }
  }, [xtbJustValidated]);

  async function handleYahooSync() {
    setLastSyncSummary(null);
    try {
      const response = await syncMutation.mutateAsync();
      const sync = response.data;
      const parts = [
        `${sync.barsAdded} velas escritas`,
        sync.barsInserted ? `${sync.barsInserted} nuevas` : null,
        sync.barsUpdated ? `${sync.barsUpdated} revisadas` : null,
        sync.barsSkipped ? `${sync.barsSkipped} conservadas (sin pisar)` : null,
      ].filter(Boolean);
      setLastSyncSummary(parts.join(" · "));
      await queryClient.invalidateQueries({
        queryKey: ["instrument-db-inventory", instrumentId],
      });
      await queryClient.invalidateQueries({
        queryKey: ["instrument-detail", instrumentId],
      });
      await queryClient.invalidateQueries({
        queryKey: ["data-status", instrumentId],
      });
      await queryClient.invalidateQueries({
        queryKey: ["instrument-profile", instrumentId],
      });
      await queryClient.invalidateQueries({ queryKey: ["instruments"] });
      await queryClient.invalidateQueries({
        queryKey: ["visualization-quotes"],
      });
    } catch {
      // error shown below
    }
  }

  if (inventoryQuery.isLoading) {
    return (
      <p className="text-xs text-muted-foreground">
        Cargando inventario de BD…
      </p>
    );
  }

  if (inventoryQuery.isError || !inventory) {
    return (
      <p className="text-xs text-destructive">
        No se pudo cargar el inventario de BD.
      </p>
    );
  }

  const statusColor = dataStatus
    ? (DATA_STATUS_COLORS[dataStatus.freshnessStatus] ?? "text-foreground")
    : undefined;

  return (
    <div className="max-h-[52vh] space-y-4 overflow-y-auto pr-1">
      {xtbProvider?.mode === "mock" && (
        <p className="rounded-md border border-sky-500/30 bg-sky-500/10 px-3 py-2 text-xs text-muted-foreground">
          Bridge XTB en modo <strong>mock</strong>: la cotización se simula
          cerca del último cierre en BD (±0,4 %). Con un bridge real verás la
          cotización en vivo del broker.
        </p>
      )}

      {xtbProvider && !xtbProvider.healthy && (
        <p className="rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs text-muted-foreground">
          Bridge XTB no disponible: {xtbProvider.message}. En desarrollo usa{" "}
          <code className="text-[10px]">pnpm dev</code> o ejecuta{" "}
          <code className="text-[10px]">node scripts/xtb-bridge-mock.mjs</code>.
        </p>
      )}

      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          disabled={syncMutation.isPending}
          onClick={() => void handleYahooSync()}
          className="rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground disabled:opacity-50"
        >
          {syncMutation.isPending ? "Sincronizando Yahoo…" : "Actualizar Yahoo"}
        </button>
        <button
          type="button"
          disabled={xtbMutation.isPending}
          onClick={() => xtbMutation.mutate()}
          className="rounded-md border border-border bg-muted/40 px-3 py-1.5 text-xs font-medium disabled:opacity-50"
        >
          {xtbMutation.isPending ? "Consultando XTB…" : "Validar con XTB"}
        </button>
      </div>

      {lastSyncSummary && (
        <p className="rounded-md border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-xs">
          Sync Yahoo completada: {lastSyncSummary}
        </p>
      )}

      {syncMutation.isError && (
        <p className="text-xs text-destructive">
          {formatSyncError(syncMutation.error)}
        </p>
      )}

      {xtbResult && (
        <div ref={xtbResultRef}>
          <XtbValidationCard result={xtbResult} highlight={xtbJustValidated} />
        </div>
      )}

      {!xtbResult && (
        <p className="rounded-md border border-dashed border-border px-3 py-2 text-xs text-muted-foreground">
          Pulsa <strong>Validar con XTB</strong> para comparar el precio en vivo
          del broker con el último cierre guardado en BD. Verás el resultado
          aquí arriba; las velas no cambian.
        </p>
      )}

      {dataStatus && (
        <section className="space-y-1 rounded-md border border-border bg-muted/20 p-3">
          <SectionTitle>Calidad en BD</SectionTitle>
          <InventoryRow
            label="Estado"
            value={
              DATA_STATUS_LABELS[dataStatus.freshnessStatus] ??
              dataStatus.freshnessStatus
            }
          />
          <InventoryRow
            label="Última vela"
            value={dataStatus.lastBarDate ?? "—"}
          />
          <InventoryRow
            label="Esperada"
            value={dataStatus.expectedLastBarDate}
          />
          {dataStatus.lastSyncAt && (
            <InventoryRow
              label="Último sync Yahoo"
              value={`${formatDateTime(dataStatus.lastSyncAt)} (${dataStatus.lastSyncStatus ?? "—"})`}
            />
          )}
          {statusColor && (
            <p className={cn("pt-1 text-[10px]", statusColor)}>
              Sync Yahoo conservadora: si Yahoo difiere &gt;2% de una vela ya en
              BD, se conserva la existente.
            </p>
          )}
        </section>
      )}

      <section className="space-y-2">
        <SectionTitle>Datos crudos — instrumento</SectionTitle>
        <InventoryRow
          label="Alta en BD"
          value={formatDateTime(inventory.instrument.createdAt)}
        />
        <InventoryRow
          label="Actualizado"
          value={formatDateTime(inventory.instrument.updatedAt)}
        />
        <InventoryRow
          label="Perfil Yahoo en BD"
          value={formatDateTime(inventory.instrument.profileFetchedAt ?? null)}
        />
      </section>

      <section className="space-y-2">
        <SectionTitle>Datos crudos — OHLCV</SectionTitle>
        <OhlcvLayersTable layers={inventory.ohlcvLayers} />
      </section>

      <section className="space-y-2">
        <SectionTitle>Historial sync (data_sync_log)</SectionTitle>
        {inventory.recentSyncLogs.length === 0 ? (
          <p className="text-xs text-muted-foreground">
            Sin registros de sincronización.
          </p>
        ) : (
          <ul className="space-y-1 text-xs">
            {inventory.recentSyncLogs.map((log) => (
              <li
                key={`${log.syncedAt}-${log.provider}`}
                className="rounded border border-border/60 px-2 py-1"
              >
                <span className="font-medium">
                  {log.provider.toUpperCase()}
                </span>
                {" · "}
                {log.status}
                {" · "}+{log.barsAdded} barras
                {" · "}
                {formatDateTime(log.syncedAt)}
                {log.error && (
                  <span className="block text-muted-foreground">
                    {log.error}
                  </span>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="space-y-2">
        <SectionTitle>Datos de la app (por instrumento)</SectionTitle>
        <InventoryRow
          label="Posiciones"
          value={String(inventory.appData.positions)}
        />
        <InventoryRow
          label="Transacciones"
          value={String(inventory.appData.transactions)}
        />
        <InventoryRow
          label="Backtests"
          value={String(inventory.appData.backtestRuns)}
        />
        <InventoryRow
          label="Listas"
          value={String(inventory.appData.listMemberships)}
        />
        <InventoryRow
          label="Alertas"
          value={String(inventory.appData.priceAlerts)}
        />
        <InventoryRow
          label="Órdenes pendientes"
          value={String(inventory.appData.pendingOrders)}
        />
        <InventoryRow
          label="Apuntes ledger"
          value={String(inventory.appData.ledgerEntries)}
        />
      </section>

      <section className="space-y-2">
        <SectionTitle>Datos derivados (no persistidos)</SectionTitle>
        <ul className="list-inside list-disc space-y-1 text-[11px] text-muted-foreground">
          {inventory.derivedDataNotes.map((note) => (
            <li key={note}>{note}</li>
          ))}
        </ul>
      </section>
    </div>
  );
}
