import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, RefreshCw, Trash2 } from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { api, ApiError } from "@/lib/api";
import { useState } from "react";

export function DatabaseConfigPanel() {
  const queryClient = useQueryClient();
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const summaryQuery = useQuery({
    queryKey: ["database-summary"],
    queryFn: () => api.getDatabaseSummary(),
  });

  const orphansQuery = useQuery({
    queryKey: ["database-orphans"],
    queryFn: () => api.getOrphanInstruments(100),
  });

  const closedAccountsQuery = useQuery({
    queryKey: ["database-closed-accounts"],
    queryFn: () => api.getClosedSimulatedAccounts(100),
  });

  async function invalidateDbQueries() {
    await queryClient.invalidateQueries({ queryKey: ["database-summary"] });
    await queryClient.invalidateQueries({ queryKey: ["database-orphans"] });
    await queryClient.invalidateQueries({
      queryKey: ["database-closed-accounts"],
    });
    await queryClient.invalidateQueries({ queryKey: ["accounts"] });
  }

  const purgeMutation = useMutation({
    mutationFn: () => api.purgeOrphanInstruments(50),
    onSuccess: async (res) => {
      setError(null);
      setMessage(
        `Purga valores: ${res.data.purgedIds.length} eliminados, ${res.data.skipped.length} omitidos (de ${res.data.scanned} revisados).`,
      );
      await invalidateDbQueries();
      await queryClient.invalidateQueries({ queryKey: ["lists"] });
      await queryClient.invalidateQueries({ queryKey: ["instruments"] });
    },
    onError: (err) => {
      setMessage(null);
      setError(err instanceof ApiError ? err.message : "No se pudo purgar");
    },
  });

  const purgeOneMutation = useMutation({
    mutationFn: (id: string) => api.deleteInstrument(id, false),
    onSuccess: async () => {
      setError(null);
      setMessage("Instrumento eliminado de BD.");
      await invalidateDbQueries();
    },
    onError: (err) => {
      setMessage(null);
      setError(err instanceof ApiError ? err.message : "No se pudo eliminar");
    },
  });

  const purgeClosedMutation = useMutation({
    mutationFn: () => api.purgeClosedSimulatedAccounts(50),
    onSuccess: async (res) => {
      setError(null);
      setMessage(
        `Purga demos: ${res.data.purgedIds.length} eliminadas, ${res.data.skipped.length} omitidas (de ${res.data.scanned} revisadas).`,
      );
      await invalidateDbQueries();
    },
    onError: (err) => {
      setMessage(null);
      setError(
        err instanceof ApiError
          ? err.message
          : "No se pudieron purgar las demos",
      );
    },
  });

  const purgeOneClosedMutation = useMutation({
    mutationFn: (id: string) => api.deleteAccount(id),
    onSuccess: async () => {
      setError(null);
      setMessage("Cuenta demo eliminada de BD.");
      await invalidateDbQueries();
    },
    onError: (err) => {
      setMessage(null);
      setError(
        err instanceof ApiError ? err.message : "No se pudo eliminar la cuenta",
      );
    },
  });

  const summary = summaryQuery.data?.data;
  const orphans = orphansQuery.data?.data;
  const closed = closedAccountsQuery.data?.data;

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="flex flex-row items-start justify-between gap-2 space-y-0">
          <div>
            <CardTitle>Estado de PostgreSQL</CardTitle>
            <CardDescription>
              Conteos por tabla, valores huérfanos y demos cerradas pendientes
              de purga.
            </CardDescription>
          </div>
          <button
            type="button"
            className="inline-flex items-center gap-1 rounded border border-border px-2 py-1 text-xs hover:bg-accent"
            onClick={() => {
              void summaryQuery.refetch();
              void orphansQuery.refetch();
              void closedAccountsQuery.refetch();
            }}
          >
            <RefreshCw className="h-3 w-3" />
            Actualizar
          </button>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          {summaryQuery.isLoading && (
            <p className="flex items-center gap-1 text-muted-foreground">
              <Loader2 className="h-3 w-3 animate-spin" />
              Conectando…
            </p>
          )}
          {summary && (
            <>
              <p>
                <span
                  className={
                    summary.connected
                      ? "font-medium text-emerald-600"
                      : "font-medium text-destructive"
                  }
                >
                  {summary.connected ? "Conectado" : "Sin conexión"}
                </span>
                <span className="text-muted-foreground">
                  {" "}
                  · {summary.message}
                </span>
              </p>
              <div className="scroll-area max-h-56 overflow-auto rounded border border-border">
                <table className="w-full text-left text-xs">
                  <thead className="sticky top-0 bg-muted/80">
                    <tr>
                      <th className="px-2 py-1.5 font-medium">Tabla</th>
                      <th className="px-2 py-1.5 text-right font-medium">
                        Filas
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {summary.tables.map((row) => (
                      <tr key={row.table} className="border-t border-border/60">
                        <td className="px-2 py-1">
                          <span className="text-foreground">{row.label}</span>
                          <span className="ml-1 text-muted-foreground">
                            ({row.table})
                          </span>
                        </td>
                        <td className="px-2 py-1 text-right tabular-nums">
                          {row.count.toLocaleString()}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Valores huérfanos</CardTitle>
          <CardDescription>
            Instrumentos que no están a ninguna lista persistente. Con{" "}
            <span className="text-foreground">scope=listas</span> la cola ya no
            los actualiza, pero OHLCV y ficha siguen ocupando espacio hasta
            purgarlos. No se borran si tienen posición u orden pendiente.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          {orphansQuery.isLoading && (
            <p className="flex items-center gap-1 text-muted-foreground">
              <Loader2 className="h-3 w-3 animate-spin" />
              Buscando…
            </p>
          )}
          {orphans && (
            <>
              <p className="text-xs text-muted-foreground">
                {orphans.orphans.length} candidato(s) ·{" "}
                {orphans.totalOhlcvBars.toLocaleString()} velas asociadas
              </p>
              {orphans.orphans.length === 0 ? (
                <p className="text-xs text-muted-foreground">
                  No hay huérfanos ahora mismo.
                </p>
              ) : (
                <ul className="scroll-area max-h-48 space-y-1 overflow-auto rounded border border-border p-2">
                  {orphans.orphans.map((o) => (
                    <li
                      key={o.id}
                      className="flex items-center justify-between gap-2 rounded px-1 py-1 text-xs hover:bg-accent/40"
                    >
                      <span className="min-w-0 truncate">
                        <span className="font-medium">{o.symbol}</span>
                        <span className="text-muted-foreground">
                          {" "}
                          · {o.name}
                        </span>
                        <span className="ml-1 text-muted-foreground">
                          ({o.ohlcvBarCount.toLocaleString()} velas)
                        </span>
                      </span>
                      <button
                        type="button"
                        className="shrink-0 rounded border border-border px-1.5 py-0.5 hover:bg-destructive/10 hover:text-destructive disabled:opacity-50"
                        disabled={purgeOneMutation.isPending}
                        title="Eliminar de BD"
                        onClick={() => {
                          if (
                            window.confirm(
                              `¿Borrar ${o.symbol} de la base de datos? Se eliminarán velas y alertas asociadas.`,
                            )
                          ) {
                            purgeOneMutation.mutate(o.id);
                          }
                        }}
                      >
                        <Trash2 className="h-3 w-3" />
                      </button>
                    </li>
                  ))}
                </ul>
              )}
              <button
                type="button"
                className="rounded bg-destructive px-3 py-1.5 text-sm font-medium text-destructive-foreground hover:bg-destructive/90 disabled:opacity-50"
                disabled={purgeMutation.isPending || !orphans.orphans.length}
                onClick={() => {
                  if (
                    window.confirm(
                      `¿Purgar hasta 50 huérfanos? Se omitirán los que tengan posición u orden pendiente.`,
                    )
                  ) {
                    purgeMutation.mutate();
                  }
                }}
              >
                {purgeMutation.isPending
                  ? "Purgando…"
                  : "Purgar huérfanos (lote)"}
              </button>
            </>
          )}
          <p className="text-xs text-muted-foreground">
            Quitar un valor de la última lista personalizada también ofrece esta
            purga. Las listas de catálogo no se editan. Detalle: Ayuda → Datos
            de mercado / Watchlist.
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Demos cerradas</CardTitle>
          <CardDescription>
            Cerrar una cuenta demo la deja en BD (ledger e historial). Eliminar
            (aquí o en la ficha de cuenta) borra la fila y sus carteras,
            posiciones, transacciones, ledger y órdenes. Los perfiles inversor
            del catálogo se conservan; las referencias cognitivas sueltas se
            desvinculan (no se borran).
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          {closedAccountsQuery.isLoading && (
            <p className="flex items-center gap-1 text-muted-foreground">
              <Loader2 className="h-3 w-3 animate-spin" />
              Buscando…
            </p>
          )}
          {closed && (
            <>
              <p className="text-xs text-muted-foreground">
                {closed.accounts.length} demo(s) cerrada(s) ·{" "}
                {closed.totalLedgerEntries.toLocaleString()} asientos de ledger
              </p>
              {closed.accounts.length === 0 ? (
                <p className="text-xs text-muted-foreground">
                  No hay demos cerradas pendientes de purga.
                </p>
              ) : (
                <ul className="scroll-area max-h-48 space-y-1 overflow-auto rounded border border-border p-2">
                  {closed.accounts.map((a) => (
                    <li
                      key={a.id}
                      className="flex items-center justify-between gap-2 rounded px-1 py-1 text-xs hover:bg-accent/40"
                    >
                      <span className="min-w-0 truncate">
                        <span className="font-medium">{a.name}</span>
                        <span className="text-muted-foreground">
                          {" "}
                          · {a.currency} · {a.ledgerEntryCount} ledger ·{" "}
                          {a.positionCount} pos.
                        </span>
                      </span>
                      <button
                        type="button"
                        className="shrink-0 rounded border border-border px-1.5 py-0.5 hover:bg-destructive/10 hover:text-destructive disabled:opacity-50"
                        disabled={purgeOneClosedMutation.isPending}
                        title="Eliminar de BD"
                        onClick={() => {
                          if (
                            window.confirm(
                              `¿Borrar la demo «${a.name}» de la base de datos? Se eliminarán ledger, posiciones y carteras asociadas.`,
                            )
                          ) {
                            purgeOneClosedMutation.mutate(a.id);
                          }
                        }}
                      >
                        <Trash2 className="h-3 w-3" />
                      </button>
                    </li>
                  ))}
                </ul>
              )}
              <button
                type="button"
                className="rounded bg-destructive px-3 py-1.5 text-sm font-medium text-destructive-foreground hover:bg-destructive/90 disabled:opacity-50"
                disabled={
                  purgeClosedMutation.isPending || !closed.accounts.length
                }
                onClick={() => {
                  if (
                    window.confirm(
                      `¿Purgar hasta 50 demos cerradas? Esta acción no se puede deshacer.`,
                    )
                  ) {
                    purgeClosedMutation.mutate();
                  }
                }}
              >
                {purgeClosedMutation.isPending
                  ? "Purgando…"
                  : "Purgar demos cerradas (lote)"}
              </button>
            </>
          )}
          {message && (
            <p className="text-xs text-emerald-700 dark:text-emerald-400">
              {message}
            </p>
          )}
          {error && <p className="text-xs text-destructive">{error}</p>}
          <p className="text-xs text-muted-foreground">
            Solo cuentas <span className="text-foreground">simuladas</span> ya
            cerradas. Paper/live no se purgan aquí. Flujo: Cuentas → cerrar →
            purgar en BD (o Eliminar en la ficha).
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
