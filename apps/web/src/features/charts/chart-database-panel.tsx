import type { ReactNode } from "react";
import type {
  ChartTimeframe,
  DatabaseSummaryDto,
  InstrumentDataStatusDto,
} from "@bolsa/shared";

function formatBarDate(iso: string | null, timeframe: ChartTimeframe) {
  if (!iso) return "—";
  const isDaily = timeframe === "1d" || iso.length === 10;
  const d = isDaily ? new Date(`${iso.slice(0, 10)}T12:00:00`) : new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  if (isDaily) {
    return d.toLocaleDateString("es-ES", {
      day: "2-digit",
      month: "short",
      year: "numeric",
    });
  }
  return d.toLocaleString("es-ES", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatDateTime(iso: string | null) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("es-ES", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function formatNumber(value: number) {
  return value.toLocaleString("es-ES");
}

export const DATA_STATUS_LABELS: Record<string, string> = {
  current: "Actualizados en BD",
  stale: "Desactualizados",
  empty: "Sin datos en BD",
  error: "Error de sincronización",
  gap_detected: "Con huecos recientes",
  syncing: "Sincronizando…",
};

export const DATA_STATUS_COLORS: Record<string, string> = {
  current: "text-emerald-400",
  stale: "text-amber-400",
  empty: "text-red-400",
  error: "text-red-400",
  gap_detected: "text-amber-400",
  syncing: "text-sky-400",
};

function DetailRow({
  label,
  value,
  valueClassName,
}: {
  label: string;
  value: ReactNode;
  valueClassName?: string;
}) {
  return (
    <div className="flex items-start justify-between gap-4 py-1.5 text-sm">
      <dt className="shrink-0 text-muted-foreground">{label}</dt>
      <dd
        className={
          valueClassName ??
          "text-right font-medium tabular-nums text-foreground"
        }
      >
        {value}
      </dd>
    </div>
  );
}

function PanelSection({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <section className="space-y-1">
      <h4 className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
        {title}
      </h4>
      <dl>{children}</dl>
    </section>
  );
}

export function ChartDatabaseInstrumentTab({
  status,
  timeframe,
  symbol,
  dbSummary,
}: {
  status: InstrumentDataStatusDto;
  timeframe: ChartTimeframe;
  symbol?: string;
  dbSummary?: DatabaseSummaryDto;
}) {
  const statusColor =
    DATA_STATUS_COLORS[status.freshnessStatus] ?? "text-foreground";

  return (
    <div className="space-y-5">
      <PanelSection
        title={symbol ? `Instrumento · ${symbol}` : "Instrumento activo"}
      >
        <DetailRow
          label="Timeframe en gráfico"
          value={timeframe.toUpperCase()}
        />
        <DetailRow
          label="Estado de frescura"
          value={
            DATA_STATUS_LABELS[status.freshnessStatus] ?? status.freshnessStatus
          }
          valueClassName={`text-right font-medium ${statusColor}`}
        />
        <DetailRow
          label="Barras en BD (activo)"
          value={formatNumber(status.barCount)}
        />
        <DetailRow
          label="Última vela"
          value={formatBarDate(status.lastBarDate, timeframe)}
        />
        {timeframe === "1d" && (
          <DetailRow
            label="Última sesión esperada"
            value={formatBarDate(status.expectedLastBarDate, "1d")}
          />
        )}
      </PanelSection>

      {dbSummary && dbSummary.instrumentOhlcv.length > 0 && (
        <PanelSection title="Histórico por resolución">
          {dbSummary.instrumentOhlcv.map((row) => (
            <DetailRow
              key={row.timeframe}
              label={row.timeframe.toUpperCase()}
              value={`${formatNumber(row.barCount)} velas`}
            />
          ))}
        </PanelSection>
      )}

      <PanelSection title="Sincronización 1D">
        <DetailRow
          label="Último sync"
          value={formatDateTime(status.lastSyncAt)}
        />
        <DetailRow
          label="Resultado"
          value={status.lastSyncStatus ?? "—"}
          valueClassName="text-right font-medium capitalize text-foreground"
        />
      </PanelSection>
    </div>
  );
}

export function ChartDatabaseServerTab({
  dbSummary,
  loadingDb,
}: {
  dbSummary?: DatabaseSummaryDto;
  loadingDb?: boolean;
}) {
  if (loadingDb) {
    return (
      <p className="text-sm text-muted-foreground">
        Conectando con PostgreSQL…
      </p>
    );
  }

  if (!dbSummary) {
    return (
      <p className="text-sm text-muted-foreground">
        No se pudo cargar el resumen del servidor. Comprueba que la API esté en
        marcha.
      </p>
    );
  }

  return (
    <div className="space-y-5">
      <PanelSection title="Conexión">
        <DetailRow
          label="Estado"
          value={dbSummary.connected ? "Conectado" : "Sin conexión"}
          valueClassName={`text-right font-medium ${dbSummary.connected ? "text-emerald-400" : "text-red-400"}`}
        />
        <DetailRow
          label="Mensaje"
          value={dbSummary.message}
          valueClassName="max-w-[14rem] text-right text-sm font-normal text-foreground"
        />
      </PanelSection>

      <PanelSection title="Tablas principales">
        {dbSummary.tables.map((row) => (
          <DetailRow
            key={row.table}
            label={row.label}
            value={formatNumber(row.count)}
          />
        ))}
      </PanelSection>
    </div>
  );
}

export function ChartDatabaseQualityTab({
  status,
}: {
  status: InstrumentDataStatusDto;
}) {
  return (
    <div className="space-y-5">
      <PanelSection title="Integridad de datos">
        <DetailRow
          label="Huecos detectados"
          value={status.gapCount}
          valueClassName={`text-right font-medium tabular-nums ${status.gapCount > 0 ? "text-amber-400" : "text-foreground"}`}
        />
        <DetailRow
          label="Desviación cierre XTB"
          value={
            status.xtbVsCloseDeviationPct != null
              ? `${status.xtbVsCloseDeviationPct.toFixed(2)} %`
              : "—"
          }
        />
        <DetailRow
          label="Última cotización XTB"
          value={formatDateTime(status.lastXtbQuoteAt)}
        />
      </PanelSection>

      {status.sanityWarnings.length > 0 && (
        <section>
          <h4 className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
            Advertencias
          </h4>
          <ul className="space-y-1.5 rounded-md border border-amber-500/30 bg-amber-500/5 p-3 text-sm text-amber-200">
            {status.sanityWarnings.map((warning) => (
              <li key={warning}>• {warning}</li>
            ))}
          </ul>
        </section>
      )}

      {status.lastSyncError && (
        <section>
          <h4 className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
            Último error de sync
          </h4>
          <p className="rounded-md border border-red-500/30 bg-red-500/5 p-3 text-sm text-red-300">
            {status.lastSyncError}
          </p>
        </section>
      )}

      {status.sanityWarnings.length === 0 && !status.lastSyncError && (
        <p className="text-sm text-muted-foreground">
          No hay incidencias de calidad registradas para este instrumento y
          timeframe.
        </p>
      )}
    </div>
  );
}

export function ChartDatabaseActivityTab({
  status,
  timeframe,
  dbSummary,
}: {
  status: InstrumentDataStatusDto;
  timeframe: ChartTimeframe;
  dbSummary?: DatabaseSummaryDto;
}) {
  const intradayFrames =
    dbSummary?.instrumentOhlcv.filter((row) => row.timeframe !== "1d") ?? [];

  return (
    <div className="space-y-5">
      <PanelSection title="Última actividad de sync">
        <DetailRow
          label="Timeframe consultado"
          value={timeframe.toUpperCase()}
        />
        <DetailRow
          label="Estado actual"
          value={
            DATA_STATUS_LABELS[status.freshnessStatus] ?? status.freshnessStatus
          }
        />
        <DetailRow
          label="Último sync 1D"
          value={formatDateTime(status.lastSyncAt)}
        />
        <DetailRow
          label="Resultado sync"
          value={status.lastSyncStatus ?? "—"}
          valueClassName="text-right font-medium capitalize text-foreground"
        />
        <DetailRow
          label="Barras tras sync"
          value={formatNumber(status.barCount)}
        />
      </PanelSection>

      {intradayFrames.length > 0 && (
        <PanelSection title="Caché intradía (BD)">
          {intradayFrames.map((row) => (
            <DetailRow
              key={row.timeframe}
              label={row.timeframe.toUpperCase()}
              value={`${formatNumber(row.barCount)} velas cacheadas`}
            />
          ))}
          <p className="pt-1 text-xs text-muted-foreground">
            Los timeframes intradía se almacenan en BD para backtests y se
            reutilizan al cambiar la escala del gráfico.
          </p>
        </PanelSection>
      )}

      <section className="rounded-md border border-dashed border-border bg-muted/10 p-3">
        <p className="text-xs font-medium text-foreground">
          Historial detallado
        </p>
        <p className="mt-1 text-xs text-muted-foreground">
          El registro completo de sincronizaciones por instrumento estará
          disponible en una próxima versión (cola de sync, reintentos y
          reparación de huecos).
        </p>
      </section>
    </div>
  );
}
