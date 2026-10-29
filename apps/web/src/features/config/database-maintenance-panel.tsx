"use client";

/**
 * Configuración → BD · diagnóstico y copia bajo demanda.
 *
 * Responde a las preguntas que el conteo de filas no responde: ¿el esquema es el que el
 * código espera?, ¿cuánto ocupa?, ¿está trabajando autovacuum?, ¿hay transacciones
 * colgadas?, ¿existe una copia reciente y con checksum?, ¿el estado durable es coherente?
 *
 * Doctrina:
 * - **El diagnóstico no escribe en la BD**: ni VACUUM, ni ANALYZE, ni migraciones desde la
 *   UI. La única acción es crear un fichero de copia (``pg_dump`` lee la BD), y por eso
 *   exige confirmación escrita.
 * - Un dato que la API no pudo medir se muestra como «No disponible» con su motivo; nunca
 *   como cero ni como verde. ``unknown`` no se pinta de rojo: no es un fallo, es ausencia.
 * - El rojo se reserva para un fallo medido (esquema fuera de head, sin copias, huérfanos).
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  HardDriveDownload,
  Loader2,
  RefreshCw,
  ShieldCheck,
} from "lucide-react";
import { useState } from "react";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { api } from "@/lib/api";
import type {
  DatabaseBackupsDto,
  DatabaseCapacityDto,
  DatabaseIntegrityDto,
  DatabaseMaintenanceDto,
  DatabaseMaintenanceStatusDto,
  DatabaseSchemaStatusDto,
  MaintenanceCheckDto,
  MaintenanceCheckStatus,
} from "@bolsa/shared";

const STATUS_LABEL: Record<MaintenanceCheckStatus, string> = {
  ok: "Correcto",
  warning: "Atención",
  error: "Fallo",
  unknown: "Sin verificar",
};

const STATUS_CLASS: Record<MaintenanceCheckStatus, string> = {
  ok: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400",
  warning: "bg-amber-500/15 text-amber-700 dark:text-amber-400",
  error: "bg-destructive/15 text-destructive",
  unknown: "bg-muted text-muted-foreground",
};

function StatusBadge({ status }: { status: MaintenanceCheckStatus }) {
  return (
    <span
      data-testid={`maintenance-status-${status}`}
      className={`inline-flex shrink-0 items-center rounded px-1.5 py-0.5 text-[11px] font-medium ${STATUS_CLASS[status]}`}
    >
      {STATUS_LABEL[status]}
    </span>
  );
}

function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "—";
  return parsed.toLocaleString("es-ES", {
    dateStyle: "short",
    timeStyle: "short",
  });
}

function formatRelativeHours(hours: number | null): string {
  if (hours === null) return "sin fecha";
  if (hours < 1) return `hace ${Math.max(1, Math.round(hours * 60))} min`;
  if (hours < 48) return `hace ${hours.toFixed(1)} h`;
  return `hace ${(hours / 24).toFixed(1)} días`;
}

function Unavailable({ detail }: { detail: string }) {
  return (
    <p
      data-testid="maintenance-unavailable"
      className="rounded border border-dashed border-border px-2 py-1.5 text-xs text-muted-foreground"
    >
      No disponible. {detail}
    </p>
  );
}

function SchemaCard({ schema }: { schema: DatabaseSchemaStatusDto }) {
  const aligned =
    schema.currentRevision !== null &&
    schema.currentRevision === schema.expectedHead;
  return (
    <Card data-testid="db-maintenance-schema">
      <CardHeader className="flex flex-row items-start justify-between gap-2 space-y-0 pb-2">
        <div>
          <CardTitle className="text-base">Esquema y migraciones</CardTitle>
          <CardDescription>
            Revisión aplicada frente al head que espera el código, tablas y
            columnas del contrato.
          </CardDescription>
        </div>
        <StatusBadge status={schema.status} />
      </CardHeader>
      <CardContent className="space-y-2 text-sm">
        <p className="flex flex-wrap items-center gap-1">
          <span className="text-muted-foreground">Revisión:</span>
          <code className="rounded bg-muted px-1 text-xs">
            {schema.currentRevision ?? "sin migrar"}
          </code>
          <span className="text-muted-foreground">· esperada:</span>
          <code className="rounded bg-muted px-1 text-xs">
            {schema.expectedHead ?? "desconocida"}
          </code>
          {schema.currentRevision && schema.expectedHead && !aligned && (
            <span className="text-xs text-destructive">
              (desalineada: aplica las migraciones pendientes)
            </span>
          )}
        </p>
        <p className="text-xs text-muted-foreground">
          {schema.databaseTables} tabla(s) en la BD · {schema.expectedTables} en
          el contrato del código
        </p>
        {schema.missingTables.length > 0 && (
          <p className="text-xs text-destructive">
            Faltan tablas: {schema.missingTables.join(", ")}
          </p>
        )}
        {schema.missingColumns.length > 0 && (
          <p className="text-xs text-destructive">
            Faltan columnas: {schema.missingColumns.join(", ")}
          </p>
        )}
        {schema.missingConstraints.length > 0 && (
          <p className="text-xs text-amber-700 dark:text-amber-400">
            Faltan constraints: {schema.missingConstraints.join(", ")}
          </p>
        )}
        {schema.unexpectedTables.length > 0 && (
          <p className="text-xs text-amber-700 dark:text-amber-400">
            Tablas fuera del contrato: {schema.unexpectedTables.join(", ")}
          </p>
        )}
        {schema.allowlisted.length > 0 && (
          <details className="text-xs text-muted-foreground">
            <summary className="cursor-pointer">
              {schema.allowlisted.length} divergencia(s) históricas declaradas
              (deuda, no borrado silencioso)
            </summary>
            <ul className="mt-1 list-disc space-y-0.5 pl-4">
              {schema.allowlisted.map((item) => (
                <li key={item}>
                  <code className="text-[11px]">{item}</code>
                </li>
              ))}
            </ul>
          </details>
        )}
        <p className="text-xs text-muted-foreground">{schema.detail}</p>
      </CardContent>
    </Card>
  );
}

function CapacityCard({ capacity }: { capacity: DatabaseCapacityDto }) {
  return (
    <Card data-testid="db-maintenance-capacity">
      <CardHeader className="flex flex-row items-start justify-between gap-2 space-y-0 pb-2">
        <div>
          <CardTitle className="text-base">Capacidad</CardTitle>
          <CardDescription>
            Tamaño de la base y tablas que más ocupan (incluye índices y TOAST).
          </CardDescription>
        </div>
        <StatusBadge status={capacity.status} />
      </CardHeader>
      <CardContent className="space-y-2 text-sm">
        {capacity.status === "unknown" ? (
          <Unavailable detail={capacity.detail} />
        ) : (
          <>
            <p>
              <span className="font-medium">{capacity.databasePretty}</span>
              <span className="text-muted-foreground"> en total</span>
            </p>
            <div className="rounded border border-border">
              <table className="w-full text-left text-xs">
                <thead className="bg-muted/60">
                  <tr>
                    <th className="px-2 py-1 font-medium">Tabla</th>
                    <th className="px-2 py-1 text-right font-medium">Filas</th>
                    <th className="px-2 py-1 text-right font-medium">Tamaño</th>
                  </tr>
                </thead>
                <tbody>
                  {capacity.tables.map((row) => (
                    <tr key={row.table} className="border-t border-border/60">
                      <td className="px-2 py-1">
                        {row.label}
                        <span className="ml-1 text-muted-foreground">
                          ({row.table})
                        </span>
                      </td>
                      <td className="px-2 py-1 text-right tabular-nums">
                        {row.rows.toLocaleString("es-ES")}
                      </td>
                      <td className="px-2 py-1 text-right tabular-nums">
                        {row.sizePretty}
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
  );
}

function MaintenanceCard({
  maintenance,
  connections,
}: {
  maintenance: DatabaseMaintenanceStatusDto;
  connections: DatabaseMaintenanceDto["connections"];
}) {
  return (
    <Card data-testid="db-maintenance-vacuum">
      <CardHeader className="flex flex-row items-start justify-between gap-2 space-y-0 pb-2">
        <div>
          <CardTitle className="text-base">Mantenimiento</CardTitle>
          <CardDescription>
            autovacuum, tuplas muertas y transacciones abiertas. Solo lectura:
            aquí no se lanza VACUUM ni ANALYZE.
          </CardDescription>
        </div>
        <StatusBadge status={maintenance.status} />
      </CardHeader>
      <CardContent className="space-y-2 text-sm">
        {maintenance.status === "unknown" ? (
          <Unavailable detail={maintenance.detail} />
        ) : (
          <>
            <p className="text-xs text-muted-foreground">
              autovacuum:{" "}
              <span className="text-foreground">
                {maintenance.autovacuumEnabled === null
                  ? "sin dato"
                  : maintenance.autovacuumEnabled
                    ? "activo"
                    : "desactivado"}
              </span>
              {maintenance.naptimeSeconds !== null && (
                <> · naptime {maintenance.naptimeSeconds} s</>
              )}{" "}
              · {maintenance.deadTuplesTotal.toLocaleString("es-ES")} tuplas
              muertas
            </p>
            {maintenance.tablesWithDeadTuples.length > 0 && (
              <ul className="space-y-0.5 text-xs">
                {maintenance.tablesWithDeadTuples.map((row) => (
                  <li key={row.table} className="flex justify-between gap-2">
                    <span className="truncate">{row.table}</span>
                    <span className="shrink-0 tabular-nums text-muted-foreground">
                      {row.deadTuples.toLocaleString("es-ES")} muertas /{" "}
                      {row.liveTuples.toLocaleString("es-ES")} vivas
                      {row.lastAutovacuum
                        ? ` · ${formatDateTime(row.lastAutovacuum)}`
                        : " · sin autovacuum"}
                    </span>
                  </li>
                ))}
              </ul>
            )}
            <div className="border-t border-border/60 pt-2">
              <p className="flex items-center justify-between gap-2 text-xs">
                <span className="text-muted-foreground">
                  Conexiones ({connections.total}
                  {connections.maxConnections
                    ? `/${connections.maxConnections}`
                    : ""}{" "}
                  · {connections.active} activas · {connections.idle} idle
                  {connections.idleInTransaction > 0
                    ? ` · ${connections.idleInTransaction} idle in transaction`
                    : ""}
                  )
                </span>
                <StatusBadge status={connections.status} />
              </p>
              <p className="mt-1 text-xs text-muted-foreground">
                {connections.detail}
                {connections.longestTransactionSeconds !== null && (
                  <>
                    {" "}
                    · transacción más larga:{" "}
                    {Math.round(connections.longestTransactionSeconds)} s
                  </>
                )}
              </p>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}

function BackupsCard({
  backups,
  onRefresh,
}: {
  backups: DatabaseBackupsDto;
  onRefresh: () => void;
}) {
  return (
    <Card data-testid="db-maintenance-backups">
      <CardHeader className="flex flex-row items-start justify-between gap-2 space-y-0 pb-2">
        <div>
          <CardTitle className="text-base">Copias de seguridad</CardTitle>
          <CardDescription>
            Última copia del árbol local y su checksum. La copia bajo demanda
            crea un fichero con los mismos scripts y retención que `pnpm
            db:dump`.
          </CardDescription>
        </div>
        <StatusBadge status={backups.status} />
      </CardHeader>
      <CardContent className="space-y-2 text-sm">
        {!backups.accessible ? (
          <Unavailable detail={backups.detail} />
        ) : (
          <>
            <p>
              <span className="font-medium">
                {backups.latestName ?? "sin copias"}
              </span>
              {backups.latestName && (
                <span className="text-muted-foreground">
                  {" "}
                  · {formatRelativeHours(backups.ageHours)}
                  {backups.latestBytes !== null
                    ? ` · ${(backups.latestBytes / (1024 * 1024)).toFixed(1)} MB`
                    : ""}
                </span>
              )}
            </p>
            <p className="text-xs text-muted-foreground">
              {backups.count} copia(s) · retención {backups.retention} ·
              checksum:{" "}
              <span
                className={
                  backups.checksumPresent
                    ? "text-emerald-700 dark:text-emerald-400"
                    : "text-amber-700 dark:text-amber-400"
                }
              >
                {backups.checksumPresent ? "presente" : "ausente"}
              </span>{" "}
              · espejo:{" "}
              <span
                className={
                  backups.mirrorConfigured
                    ? "text-emerald-700 dark:text-emerald-400"
                    : "text-muted-foreground"
                }
              >
                {backups.mirrorConfigured ? "configurado" : "no configurado"}
              </span>
            </p>
            {backups.latestSchema && (
              <p className="text-xs text-muted-foreground">
                Revisión de la copia:{" "}
                <code className="rounded bg-muted px-1">
                  {backups.latestSchema}
                </code>
              </p>
            )}
            <p className="text-xs text-muted-foreground">{backups.detail}</p>
          </>
        )}
        <BackupAction disabled={!backups.accessible} onDone={onRefresh} />
      </CardContent>
    </Card>
  );
}

const BACKUP_CONFIRMATION = "COPIAR";

/**
 * Acción de escritura de la ventana BD: crear una copia.
 *
 * No hay botón «de un clic»: se despliega un campo y hay que escribir `COPIAR`. Si la API
 * devuelve 409 (otra copia en curso), 403 (producción o sin rol) o 500/503 (el volcado no
 * se pudo ejecutar), se muestra el motivo y **no** se pinta ningún éxito.
 */
function BackupAction({
  disabled,
  onDone,
}: {
  disabled: boolean;
  onDone: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [confirmation, setConfirmation] = useState("");

  const mutation = useMutation({
    mutationFn: () =>
      api.createDatabaseBackup(confirmation.trim().toUpperCase()),
    onSuccess: () => {
      setConfirmation("");
      setOpen(false);
      onDone();
    },
  });

  const result = mutation.data?.data.run;
  // Cualquier error con mensaje se muestra: perderlo obligaría al usuario a adivinar si
  // falló la red, el rol, el cerrojo o el propio ``pg_dump``.
  const error =
    mutation.error instanceof Error && mutation.error.message
      ? mutation.error.message
      : mutation.error
        ? "No se pudo crear la copia"
        : null;

  return (
    <div className="space-y-2 border-t border-border/60 pt-2">
      {!open && (
        <button
          type="button"
          data-testid="db-backup-start"
          className="inline-flex items-center gap-1 rounded border border-border px-2 py-1 text-xs hover:bg-accent disabled:opacity-50"
          disabled={disabled || mutation.isPending}
          onClick={() => {
            setOpen(true);
          }}
        >
          <HardDriveDownload className="h-3 w-3" />
          Crear copia ahora
        </button>
      )}

      {open && (
        <div className="space-y-2 rounded border border-border px-2 py-2">
          <label className="block text-xs" htmlFor="db-backup-confirm">
            Escribe{" "}
            <code className="rounded bg-muted px-1 font-semibold">
              {BACKUP_CONFIRMATION}
            </code>{" "}
            para confirmar. No se puede deshacer la poda por retención.
          </label>
          <div className="flex items-center gap-2">
            <input
              id="db-backup-confirm"
              type="text"
              autoComplete="off"
              value={confirmation}
              onChange={(event) => setConfirmation(event.target.value)}
              className="w-32 rounded border border-border bg-background px-2 py-1 text-xs"
              placeholder={BACKUP_CONFIRMATION}
            />
            <button
              type="button"
              data-testid="db-backup-confirm"
              className="inline-flex items-center gap-1 rounded bg-primary px-2 py-1 text-xs font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
              disabled={
                mutation.isPending ||
                confirmation.trim().toUpperCase() !== BACKUP_CONFIRMATION
              }
              onClick={() => mutation.mutate()}
            >
              {mutation.isPending ? (
                <>
                  <Loader2 className="h-3 w-3 animate-spin" />
                  Copiando…
                </>
              ) : (
                "Confirmar copia"
              )}
            </button>
            <button
              type="button"
              className="rounded border border-border px-2 py-1 text-xs hover:bg-accent disabled:opacity-50"
              disabled={mutation.isPending}
              onClick={() => {
                setOpen(false);
                setConfirmation("");
                mutation.reset();
              }}
            >
              Cancelar
            </button>
          </div>
        </div>
      )}

      {mutation.isPending && (
        <p className="flex items-center gap-1 text-xs text-muted-foreground">
          <Loader2 className="h-3 w-3 animate-spin" />
          Ejecutando el volcado. Puede tardar; no cierres la pestaña.
        </p>
      )}

      {result && (
        <p
          data-testid="db-backup-result"
          className="text-xs text-emerald-700 dark:text-emerald-400"
        >
          Copia creada:{" "}
          <span className="font-medium">
            {result.file?.split(/[\\/]/).pop() ?? "sin nombre"}
          </span>
          {result.bytes !== null
            ? ` · ${(result.bytes / (1024 * 1024)).toFixed(1)} MB`
            : ""}
          {result.sha256 ? ` · sha256 ${result.sha256.slice(0, 12)}…` : ""}
          {result.pruned > 0 ? ` · ${result.pruned} podada(s)` : ""}
          {` · ${(result.durationMs / 1000).toFixed(1)} s`}
        </p>
      )}

      {error && (
        <p data-testid="db-backup-error" className="text-xs text-destructive">
          {error}
        </p>
      )}
      <p className="text-xs text-muted-foreground">
        Solo se crea un fichero local: no restaura, no hace VACUUM y no aplica
        migraciones.
      </p>
    </div>
  );
}

function IntegrityCard({ integrity }: { integrity: DatabaseIntegrityDto }) {
  return (
    <Card data-testid="db-maintenance-integrity">
      <CardHeader className="flex flex-row items-start justify-between gap-2 space-y-0 pb-2">
        <div>
          <CardTitle className="text-base">Integridad</CardTitle>
          <CardDescription>
            Coherencia del estado durable: fila única de configuración,
            huérfanos y duplicados.
          </CardDescription>
        </div>
        <StatusBadge status={integrity.status} />
      </CardHeader>
      <CardContent className="space-y-1.5 text-sm">
        {integrity.checks.length === 0 ? (
          <Unavailable detail={integrity.detail} />
        ) : (
          <ul className="space-y-1">
            {integrity.checks.map((check: MaintenanceCheckDto) => (
              <li
                key={check.id}
                className="flex items-start justify-between gap-2 text-xs"
              >
                <span className="min-w-0">
                  <span className="text-foreground">{check.label}</span>
                  <span className="block text-muted-foreground">
                    {check.detail}
                  </span>
                </span>
                <StatusBadge status={check.status} />
              </li>
            ))}
          </ul>
        )}
        <p className="text-xs text-muted-foreground">{integrity.detail}</p>
      </CardContent>
    </Card>
  );
}

export function DatabaseMaintenancePanel() {
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: ["database-maintenance"],
    queryFn: () => api.getDatabaseMaintenance(),
    refetchInterval: 60_000,
  });
  const report = query.data?.data;

  return (
    <Card data-testid="db-maintenance-panel">
      <CardHeader className="flex flex-row items-start justify-between gap-2 space-y-0">
        <div>
          <CardTitle className="flex items-center gap-2">
            <ShieldCheck className="h-4 w-4" />
            Diagnóstico de la base de datos
          </CardTitle>
          <CardDescription>
            Esquema, capacidad, mantenimiento, conexiones, copias e integridad.
            El diagnóstico no escribe en la BD; la única acción crea un fichero
            de copia.
          </CardDescription>
        </div>
        <div className="flex items-center gap-2">
          {report && <StatusBadge status={report.status} />}
          <button
            type="button"
            className="inline-flex items-center gap-1 rounded border border-border px-2 py-1 text-xs hover:bg-accent"
            onClick={() => {
              void query.refetch();
            }}
          >
            <RefreshCw className="h-3 w-3" />
            Actualizar
          </button>
        </div>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        {query.isLoading && (
          <p className="flex items-center gap-1 text-muted-foreground">
            <Loader2 className="h-3 w-3 animate-spin" />
            Leyendo estado de PostgreSQL…
          </p>
        )}
        {query.isError && (
          <p className="text-xs text-destructive">
            No se pudo leer el diagnóstico. El endpoint responde 200 con
            `connected=false` si la BD está caída; este error es de red o de la
            API.
          </p>
        )}
        {report && (
          <>
            <p className="text-xs text-muted-foreground">
              {report.connected
                ? `Conectado · ${report.message} · generado ${formatDateTime(report.generatedAt)}`
                : `Sin conexión · ${report.message}`}
            </p>
            {!report.connected && (
              <Unavailable detail="PostgreSQL no responde; no se puede afirmar nada del esquema ni de las copias." />
            )}
          </>
        )}
      </CardContent>

      {report && (
        <CardContent className="grid gap-3 lg:grid-cols-2">
          <SchemaCard schema={report.schema} />
          <CapacityCard capacity={report.capacity} />
          <MaintenanceCard
            maintenance={report.maintenance}
            connections={report.connections}
          />
          <BackupsCard
            backups={report.backups}
            onRefresh={() => {
              // La copia cambia el manifest y el tamaño: se refresca el diagnóstico (el
              // propio POST ya devuelve el inventario nuevo, pero no el resto de bloques).
              void query.refetch();
              void queryClient.invalidateQueries({
                queryKey: ["database-summary"],
              });
            }}
          />
          <div className="lg:col-span-2">
            <IntegrityCard integrity={report.integrity} />
          </div>
        </CardContent>
      )}
    </Card>
  );
}
