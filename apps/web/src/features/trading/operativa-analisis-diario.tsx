/**
 * Banda compacta de ANÁLISIS DIARIO del valor seleccionado en MERCADO.
 *
 * Cuatro lecturas, de arriba abajo: tendencia del parte diario, seguimiento Lab
 * (estrategia #1 + indicadores optimizados), momento de entrada y momento de
 * salida. Proyecta `InstrumentDailyAnalysisV1`: no calcula nada ni inventa datos;
 * lo que falta se declara («Sin dato todavía»).
 *
 * Se coloca encima de la tarjeta de decisión y no la sustituye.
 *
 * @see packages/shared/src/cognitive/instrument-daily-analysis.ts
 * @see docs/engineering/analisis-diario-operativa-mercado-2026-11-10.md
 */

import { Link } from "react-router-dom";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import { absentDataLabel } from "@/components/absent-data";
import {
  formatPctOrAbsent,
  formatPriceOrAbsent,
} from "@/features/charts/chart-utils";
import {
  formatJournalStudyAge,
  JOURNAL_STUDY_VIGENCIA_LABELS,
  type DailyTrendToneV1,
  type InstrumentDailyAnalysisV1,
} from "@bolsa/shared";
import { formatNumberWith } from "@/lib/format";

/** Ratio con 2 decimales y coma es-ES (R:R, múltiplos R). */
function formatRatio2(value: number): string {
  return formatNumberWith(value, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

const TONE_CLASS: Record<DailyTrendToneV1, string> = {
  bullish:
    "border-emerald-600/45 bg-emerald-500/10 text-emerald-900 dark:text-emerald-100",
  bearish: "border-rose-600/45 bg-rose-500/10 text-rose-900 dark:text-rose-100",
  range:
    "border-amber-600/45 bg-amber-500/10 text-amber-950 dark:text-amber-100",
  mixed:
    "border-slate-500/45 bg-slate-500/10 text-slate-900 dark:text-slate-100",
  unknown: "border-border/70 bg-muted/20 text-muted-foreground",
};

const EVIDENCE_LABELS: Record<"in_sample_only" | "lab_validated", string> = {
  lab_validated: "Validada en LAB",
  in_sample_only: "Solo in-sample",
};

function RowLabel({ children }: { children: string }) {
  return (
    <span className="w-[62px] shrink-0 text-[9px] font-semibold uppercase tracking-wide text-muted-foreground">
      {children}
    </span>
  );
}

function Row({
  label,
  testId,
  children,
}: {
  label: string;
  testId: string;
  children: ReactNode;
}) {
  return (
    <div className="flex min-w-0 items-start gap-1.5" data-testid={testId}>
      <RowLabel>{label}</RowLabel>
      <div className="min-w-0 flex-1">{children}</div>
    </div>
  );
}

function Metric({
  label,
  value,
  tone,
  title,
}: {
  label: string;
  value: string;
  tone?: "up" | "down" | "neutral";
  title?: string;
}) {
  return (
    <span
      className="inline-flex items-baseline gap-1 rounded border border-border/60 bg-background/60 px-1.5 py-0.5"
      title={title}
    >
      <span className="text-[9px] text-muted-foreground">{label}</span>
      <span
        className={cn(
          "font-semibold tabular-nums",
          tone === "up" && "text-emerald-700 dark:text-emerald-300",
          tone === "down" && "text-rose-700 dark:text-rose-300",
        )}
      >
        {value}
      </span>
    </span>
  );
}

function StatusChip({
  label,
  value,
  title,
}: {
  label: string;
  value: string;
  title?: string;
}) {
  return (
    <span
      className="inline-flex items-baseline gap-1 rounded border border-border/60 bg-background/60 px-1.5 py-0.5"
      title={title}
    >
      <span className="text-[9px] text-muted-foreground">{label}</span>
      <span className="font-medium text-foreground">{value}</span>
    </span>
  );
}

export function OperativaAnalisisDiario({
  analysis,
  symbol,
  timeframe,
  labHref,
  loading,
  refreshPending,
  onRefreshStudy,
  className,
}: {
  analysis: InstrumentDailyAnalysisV1;
  symbol: string;
  timeframe: string;
  labHref: string;
  loading?: boolean;
  refreshPending?: boolean;
  onRefreshStudy?: () => void;
  className?: string;
}) {
  const { studyMeta, trends, tracking, entry, exit } = analysis;
  const ageLabel = formatJournalStudyAge(studyMeta?.ageMs ?? null);
  const vigenciaLabel = studyMeta?.vigencia
    ? JOURNAL_STUDY_VIGENCIA_LABELS[studyMeta.vigencia]
    : null;

  if (!analysis.inEstudio) {
    return (
      <section
        className={cn(
          "space-y-1 rounded-md border border-violet-600/30 bg-violet-500/5 px-2 py-1.5",
          className,
        )}
        data-testid="operativa-analisis-diario"
        data-instrument-id={analysis.instrumentId}
        data-estudio="false"
        data-measured={String(analysis.measured)}
        data-phase={entry?.state ?? "descubierto"}
        aria-label={`Análisis diario · ${symbol}`}
      >
        <div className="flex items-center justify-between gap-2">
          <p className="text-[10px] font-semibold uppercase tracking-wide text-foreground">
            Análisis diario
          </p>
          <Link
            to={labHref}
            className="shrink-0 rounded border border-sky-600/30 bg-sky-500/10 px-1.5 py-0.5 text-[9px] font-medium text-sky-950 hover:bg-sky-500/20 dark:text-sky-50"
          >
            Abrir estudio (LAB)
          </Link>
        </div>
        <p
          className="text-[10px] leading-snug text-muted-foreground"
          data-testid="operativa-analisis-diario-fuera"
        >
          Sin seguimiento diario: fuera de Estudio. Añádelo para supervisar
          tendencia, indicadores del Lab y niveles.
        </p>
      </section>
    );
  }

  return (
    <section
      className={cn(
        "space-y-1.5 rounded-md border border-border/70 bg-gradient-to-b from-muted/25 to-transparent px-2 py-1.5",
        className,
      )}
      data-testid="operativa-analisis-diario"
      data-instrument-id={analysis.instrumentId}
      data-estudio="true"
      data-measured={String(analysis.measured)}
      data-phase={entry?.state ?? (exit ? "posicion" : "desconocido")}
      aria-label={`Análisis diario · ${symbol}`}
    >
      <div className="flex flex-wrap items-center justify-between gap-1">
        <p className="text-[10px] font-semibold uppercase tracking-wide text-foreground">
          Análisis diario
          <span className="ml-1 font-normal normal-case text-muted-foreground">
            · {symbol} · {timeframe}
          </span>
        </p>
        <div className="flex shrink-0 items-center gap-1">
          {ageLabel ? (
            <span className="text-[9px] tabular-nums text-muted-foreground">
              hace {ageLabel}
            </span>
          ) : null}
          {vigenciaLabel ? (
            <span
              className={cn(
                "rounded border px-1.5 py-0.5 text-[9px] font-semibold",
                studyMeta?.vigencia === "expired"
                  ? "border-rose-600/45 bg-rose-500/10 text-rose-900 dark:text-rose-100"
                  : studyMeta?.vigencia === "expiring_soon"
                    ? "border-amber-600/45 bg-amber-500/10 text-amber-950 dark:text-amber-100"
                    : "border-border/70 bg-background/60 text-muted-foreground",
              )}
              data-testid="operativa-analisis-vigencia"
              data-vigencia={studyMeta?.vigencia}
            >
              {vigenciaLabel}
            </span>
          ) : null}
          <Link
            to={labHref}
            className="rounded border border-sky-600/30 bg-sky-500/10 px-1.5 py-0.5 text-[9px] font-medium text-sky-950 hover:bg-sky-500/20 dark:text-sky-50"
          >
            Abrir estudio (LAB)
          </Link>
        </div>
      </div>

      {/* Tendencia — copia literal del parte diario */}
      <Row label="Tendencia" testId="operativa-analisis-tendencia">
        {loading ? (
          <span className="text-[10px] text-muted-foreground">
            Leyendo parte diario…
          </span>
        ) : trends.length > 0 ? (
          <div className="flex flex-wrap items-center gap-1">
            {trends.map((trend) => (
              <span
                key={trend.key}
                className={cn(
                  "inline-flex items-baseline gap-1 rounded border px-1.5 py-0.5",
                  TONE_CLASS[trend.tone],
                )}
                data-trend={trend.key}
                data-tone={trend.tone}
                title={
                  trend.basis
                    ? `${trend.label}: ${trend.display} · base ${trend.basis}`
                    : `${trend.label}: ${trend.display}`
                }
              >
                <span className="text-[9px] font-normal opacity-80">
                  {trend.label}
                </span>
                <span className="text-[10px] font-semibold">
                  {trend.display}
                </span>
                {trend.basis ? (
                  <span className="text-[9px] font-normal opacity-70">
                    {trend.basis}
                  </span>
                ) : null}
              </span>
            ))}
          </div>
        ) : (
          <div className="flex flex-wrap items-center gap-1">
            <span className="text-[10px] text-muted-foreground">
              Sin análisis diario todavía.
            </span>
            {onRefreshStudy ? (
              <button
                type="button"
                className="rounded border border-border px-1.5 py-0.5 text-[9px] font-medium text-foreground hover:bg-accent disabled:opacity-50"
                onClick={onRefreshStudy}
                disabled={refreshPending}
                data-testid="operativa-analisis-actualizar"
              >
                {refreshPending ? "Actualizando…" : "Actualizar análisis"}
              </button>
            ) : null}
          </div>
        )}
      </Row>

      {/* Seguimiento Lab — estrategia #1 e indicadores optimizados */}
      <Row label="Seguimiento" testId="operativa-analisis-seguimiento">
        {tracking.strategyLabel ? (
          <div className="space-y-0.5">
            <p className="min-w-0 truncate text-[10px] font-medium text-foreground">
              <span className="text-muted-foreground">
                #{tracking.strategyRank ?? 1}
              </span>{" "}
              {tracking.strategyLabel}
              {tracking.evidenceLevel ? (
                <span className="ml-1 font-normal text-muted-foreground">
                  · {EVIDENCE_LABELS[tracking.evidenceLevel]}
                </span>
              ) : null}
            </p>
            <p
              className="min-w-0 text-[10px] leading-snug text-muted-foreground"
              data-testid="operativa-analisis-indicadores"
            >
              Indicadores:{" "}
              {tracking.indicators.length > 0
                ? tracking.indicators.map((item) => item.display).join(" · ")
                : absentDataLabel()}
              {tracking.stabilityLabel ? (
                <span className="opacity-80"> · {tracking.stabilityLabel}</span>
              ) : null}
            </p>
            <p
              className="min-w-0 truncate text-[9px] leading-snug text-muted-foreground/90"
              title={tracking.reason ?? undefined}
            >
              {tracking.reason
                ? `Razón: ${tracking.reason}`
                : `Razón: ${absentDataLabel()}`}
            </p>
          </div>
        ) : (
          <p className="text-[10px] leading-snug text-muted-foreground">
            {tracking.gap ?? "Sin estrategia de seguimiento todavía."}
          </p>
        )}
      </Row>

      {/* Entrada — fase sin posición */}
      {entry ? (
        <Row label="Entrada" testId="operativa-analisis-entrada">
          <div className="space-y-0.5">
            <div className="flex flex-wrap items-center gap-1">
              <span
                className="rounded border border-border/70 bg-background/60 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide text-foreground"
                data-testid="operativa-analisis-entrada-estado"
              >
                {entry.stateLabel}
              </span>
              {entry.entry != null ? (
                <>
                  <Metric
                    label="Entrada"
                    value={formatPriceOrAbsent(entry.entry)}
                  />
                  <Metric
                    label="Stop"
                    value={formatPriceOrAbsent(entry.stop)}
                  />
                  <Metric
                    label="T1"
                    value={formatPriceOrAbsent(entry.target1)}
                  />
                  <Metric
                    label="T2"
                    value={formatPriceOrAbsent(entry.target2)}
                  />
                  <Metric
                    label="Dist."
                    value={formatPctOrAbsent(entry.distancePct)}
                    tone={
                      entry.distancePct == null
                        ? "neutral"
                        : entry.distancePct > 0
                          ? "up"
                          : entry.distancePct < 0
                            ? "down"
                            : "neutral"
                    }
                    title="Distancia del precio a la entrada (mark − entrada)"
                  />
                  <Metric
                    label="R:R"
                    value={
                      entry.expectedRR != null
                        ? formatRatio2(entry.expectedRR)
                        : absentDataLabel()
                    }
                  />
                </>
              ) : null}
            </div>
            {entry.missing ? (
              <p className="text-[9px] leading-snug text-muted-foreground">
                {entry.missing}
              </p>
            ) : null}
          </div>
        </Row>
      ) : null}

      {/* Salida — posición abierta */}
      {exit ? (
        <Row label="Salida" testId="operativa-analisis-salida">
          <div className="space-y-0.5">
            <div className="flex flex-wrap items-center gap-1">
              <Metric
                label="Stop vigente"
                value={formatPriceOrAbsent(exit.stop)}
                title="Stop operativo con autoridad; el trailing solo sugiere"
              />
              <StatusChip
                label="T1"
                value={exit.target1Hint}
                title="Estado de T1 (tocado / gestionado)"
              />
              <StatusChip
                label="T2"
                value={exit.target2Hint}
                title="Estado de T2 (tocado / gestionado)"
              />
              <Metric
                label="R"
                value={
                  exit.unrealizedR != null
                    ? `${formatRatio2(exit.unrealizedR)}R`
                    : absentDataLabel()
                }
                tone={
                  exit.unrealizedR == null
                    ? "neutral"
                    : exit.unrealizedR > 0
                      ? "up"
                      : exit.unrealizedR < 0
                        ? "down"
                        : "neutral"
                }
                title="Resultado no realizado en múltiplos de riesgo"
              />
            </div>
            {exit.trailingLabel ? (
              <p
                className="text-[9px] leading-snug text-amber-900 dark:text-amber-100"
                data-testid="operativa-analisis-trailing"
              >
                ↗ Trailing: {exit.trailingLabel}
              </p>
            ) : null}
            {exit.invalidation ? (
              <p
                className="min-w-0 truncate text-[9px] leading-snug text-muted-foreground"
                title={exit.invalidation}
              >
                Invalida: {exit.invalidation}
              </p>
            ) : null}
          </div>
        </Row>
      ) : null}

      {analysis.gaps.length > 0 ? (
        <p
          className="text-[9px] leading-snug text-muted-foreground"
          data-testid="operativa-analisis-gaps"
        >
          Falta: {analysis.gaps.join(" · ")}
        </p>
      ) : null}
    </section>
  );
}
