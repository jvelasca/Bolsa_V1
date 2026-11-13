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
  OPERATIVA_TEXT,
  type OperativaDensity,
} from "@/features/trading/operativa-density";
import {
  formatPctOrAbsent,
  formatPriceOrAbsent,
} from "@/features/charts/chart-utils";
import {
  formatJournalStudyAge,
  JOURNAL_STUDY_VIGENCIA_LABELS,
  marketTrendDefinition,
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
  neutral:
    "border-sky-600/40 bg-sky-500/10 text-sky-900 dark:text-sky-100",
  unknown: "border-border/70 bg-muted/20 text-muted-foreground",
};

const EVIDENCE_LABELS: Record<"in_sample_only" | "lab_validated", string> = {
  lab_validated: "Validada en LAB",
  in_sample_only: "Solo in-sample",
};

function RowLabel({
  children,
  density = "compact",
}: {
  children: string;
  density?: OperativaDensity;
}) {
  const text = OPERATIVA_TEXT[density];
  return (
    <span
      className={cn(
        "shrink-0 font-semibold uppercase tracking-wide text-muted-foreground",
        density === "dock" ? "w-[78px]" : "w-[62px]",
        text.micro,
      )}
    >
      {children}
    </span>
  );
}

function Row({
  label,
  testId,
  children,
  density = "compact",
}: {
  label: string;
  testId: string;
  children: ReactNode;
  density?: OperativaDensity;
}) {
  return (
    <div className="flex min-w-0 items-start gap-1.5" data-testid={testId}>
      <RowLabel density={density}>{label}</RowLabel>
      <div className="min-w-0 flex-1">{children}</div>
    </div>
  );
}

function Metric({
  label,
  value,
  tone,
  title,
  density = "compact",
}: {
  label: string;
  value: string;
  tone?: "up" | "down" | "neutral";
  title?: string;
  density?: OperativaDensity;
}) {
  const text = OPERATIVA_TEXT[density];
  return (
    <span
      className="inline-flex items-baseline gap-1 rounded border border-border/60 bg-background/60 px-1.5 py-0.5"
      title={title}
    >
      <span className={cn(text.micro, "text-muted-foreground")}>{label}</span>
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
  density = "compact",
}: {
  label: string;
  value: string;
  title?: string;
  density?: OperativaDensity;
}) {
  const text = OPERATIVA_TEXT[density];
  return (
    <span
      className="inline-flex items-baseline gap-1 rounded border border-border/60 bg-background/60 px-1.5 py-0.5"
      title={title}
    >
      <span className={cn(text.micro, "text-muted-foreground")}>{label}</span>
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
  error,
  refreshPending,
  onRefreshStudy,
  className,
  part = "all",
  density = "compact",
}: {
  analysis: InstrumentDailyAnalysisV1;
  symbol: string;
  timeframe: string;
  labHref: string;
  loading?: boolean;
  /** La lectura de estudios falló: «sin análisis» sería una afirmación falsa. */
  error?: boolean;
  refreshPending?: boolean;
  onRefreshStudy?: () => void;
  className?: string;
  /**
   * `all` es la banda completa (maximizada/estrecha). `tecnico` y `seguimiento`
   * son las dos mitades que el dock reparte entre sus grupos homónimos.
   */
  part?: "all" | "tecnico" | "seguimiento";
  density?: OperativaDensity;
}) {
  const { studyMeta, trends, tracking, entry, exit } = analysis;
  const text = OPERATIVA_TEXT[density];
  const ageLabel = formatJournalStudyAge(studyMeta?.ageMs ?? null);
  const vigenciaLabel = studyMeta?.vigencia
    ? JOURNAL_STUDY_VIGENCIA_LABELS[studyMeta.vigencia]
    : null;
  const showTecnico = part === "all" || part === "tecnico";
  const showSeguimiento = part === "all" || part === "seguimiento";
  const testId =
    part === "all"
      ? "operativa-analisis-diario"
      : `operativa-analisis-diario-${part}`;

  if (!analysis.inEstudio) {
    return (
      <section
        className={cn(
          "space-y-1 rounded-md border border-violet-600/30 bg-violet-500/5 px-2 py-1.5",
          className,
        )}
        data-testid={testId}
        data-part={part}
        data-instrument-id={analysis.instrumentId}
        data-estudio="false"
        data-measured={String(analysis.measured)}
        data-phase={entry?.state ?? "descubierto"}
        aria-label={`Análisis diario · ${symbol}`}
      >
        {part === "all" ? (
          <div className="flex items-center justify-between gap-2">
            <p
              className={cn(
                "font-semibold uppercase tracking-wide text-foreground",
                text.caption,
              )}
            >
              Análisis diario
            </p>
            <Link
              to={labHref}
              className="shrink-0 rounded border border-sky-600/30 bg-sky-500/10 px-1.5 py-0.5 text-[9px] font-medium text-sky-950 hover:bg-sky-500/20 dark:text-sky-50"
            >
              Abrir estudio (LAB)
            </Link>
          </div>
        ) : null}
        <p
          className={cn("leading-snug text-muted-foreground", text.caption)}
          data-testid="operativa-analisis-diario-fuera"
        >
          {part === "tecnico"
            ? "Fuera de Estudio: sin tendencia ni niveles del parte diario."
            : part === "seguimiento"
              ? "Fuera de Estudio: sin seguimiento diario del valor."
              : "Sin seguimiento diario: fuera de Estudio. Añádelo para supervisar tendencia, indicadores del Lab y niveles."}
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
      data-testid={testId}
      data-part={part}
      data-instrument-id={analysis.instrumentId}
      data-estudio="true"
      data-measured={String(analysis.measured)}
      data-phase={entry?.state ?? (exit ? "posicion" : "desconocido")}
      aria-label={`Análisis diario · ${symbol}`}
    >
      {part !== "tecnico" ? (
        <div className="flex flex-wrap items-center justify-between gap-1">
          <p
            className={cn(
              "font-semibold uppercase tracking-wide text-foreground",
              text.caption,
            )}
          >
            {part === "seguimiento" ? "Seguimiento del día" : "Análisis diario"}
            <span className="ml-1 font-normal normal-case text-muted-foreground">
              · {symbol} · {timeframe}
            </span>
          </p>
          <div className="flex shrink-0 items-center gap-1">
            {ageLabel ? (
              <span
                className={cn(
                  "tabular-nums text-muted-foreground",
                  text.micro,
                )}
              >
                hace {ageLabel}
              </span>
            ) : null}
            {vigenciaLabel ? (
              <span
                className={cn(
                  "rounded border px-1.5 py-0.5 font-semibold",
                  text.micro,
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
          </div>
        </div>
      ) : null}

      {/* Tendencia — copia literal del parte diario */}
      {showTecnico ? (
        <Row label="Tendencia" testId="operativa-analisis-tendencia" density={density}>
          {loading ? (
            <span className={cn("text-muted-foreground", text.caption)}>
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
                  title={[
                    `${trend.label}: ${trend.display}`,
                    marketTrendDefinition(trend.value)?.basis,
                    trend.basis ? `Base: ${trend.basis}` : null,
                  ]
                    .filter(Boolean)
                    .join(" · ")}
                >
                  <span className={cn("font-normal opacity-80", text.micro)}>
                    {trend.label}
                  </span>
                  <span className={cn("font-semibold", text.caption)}>
                    {trend.display}
                  </span>
                  {trend.basis ? (
                    <span className={cn("font-normal opacity-70", text.micro)}>
                      {trend.basis}
                    </span>
                  ) : null}
                </span>
              ))}
            </div>
          ) : (
            <div className="flex flex-wrap items-center gap-1">
              <span className={cn("text-muted-foreground", text.caption)}>
                {error
                  ? "No se pudo leer el parte diario."
                  : "Sin análisis diario todavía."}
              </span>
              {onRefreshStudy ? (
                <button
                  type="button"
                  className={cn(
                    "rounded border border-border px-1.5 py-0.5 font-medium text-foreground hover:bg-accent disabled:opacity-50",
                    text.micro,
                  )}
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
      ) : null}

      {/* Seguimiento Lab — estrategia #1 e indicadores optimizados */}
      {showSeguimiento ? (
        <Row
          label="Seguimiento"
          testId="operativa-analisis-seguimiento"
          density={density}
        >
          {tracking.strategyLabel ? (
            <div className="space-y-0.5">
              <p
                className={cn(
                  "min-w-0 truncate font-medium text-foreground",
                  text.caption,
                )}
              >
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
                className={cn(
                  "min-w-0 leading-snug text-muted-foreground",
                  text.caption,
                )}
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
                className={cn(
                  "min-w-0 truncate leading-snug text-muted-foreground/90",
                  text.micro,
                )}
                title={tracking.reason ?? undefined}
              >
                {tracking.reason
                  ? `Razón: ${tracking.reason}`
                  : `Razón: ${absentDataLabel()}`}
              </p>
            </div>
          ) : (
            <p className={cn("leading-snug text-muted-foreground", text.caption)}>
              {tracking.gap ?? "Sin estrategia de seguimiento todavía."}
            </p>
          )}
        </Row>
      ) : null}

      {/* Entrada — fase sin posición */}
      {showTecnico && entry ? (
        <Row
          label="Entrada"
          testId="operativa-analisis-entrada"
          density={density}
        >
          <div className="space-y-0.5">
            <div className="flex flex-wrap items-center gap-1">
              <span
                className={cn(
                  "rounded border border-border/70 bg-background/60 px-1.5 py-0.5 font-semibold uppercase tracking-wide text-foreground",
                  text.micro,
                )}
                data-testid="operativa-analisis-entrada-estado"
              >
                {entry.stateLabel}
              </span>
              {entry.entry != null ? (
                <>
                  <Metric
                    label="Entrada"
                    value={formatPriceOrAbsent(entry.entry)}
                    density={density}
                  />
                  <Metric
                    label="Stop"
                    value={formatPriceOrAbsent(entry.stop)}
                    density={density}
                  />
                  <Metric
                    label="T1"
                    value={formatPriceOrAbsent(entry.target1)}
                    density={density}
                  />
                  <Metric
                    label="T2"
                    value={formatPriceOrAbsent(entry.target2)}
                    density={density}
                  />
                  <Metric
                    label="Dist."
                    value={formatPctOrAbsent(entry.distancePct)}
                    density={density}
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
                    density={density}
                  />
                </>
              ) : null}
            </div>
            {entry.missing ? (
              <p className={cn("leading-snug text-muted-foreground", text.micro)}>
                {entry.missing}
              </p>
            ) : null}
          </div>
        </Row>
      ) : null}

      {/* Salida — posición abierta */}
      {showTecnico && exit ? (
        <Row
          label="Salida"
          testId="operativa-analisis-salida"
          density={density}
        >
          <div className="space-y-0.5">
            <div className="flex flex-wrap items-center gap-1">
              <Metric
                label="Stop vigente"
                value={formatPriceOrAbsent(exit.stop)}
                density={density}
                title="Stop operativo con autoridad; el trailing solo sugiere"
              />
              <StatusChip
                label="T1"
                value={exit.target1Hint}
                density={density}
                title="Estado de T1 (tocado / gestionado)"
              />
              <StatusChip
                label="T2"
                value={exit.target2Hint}
                density={density}
                title="Estado de T2 (tocado / gestionado)"
              />
              <Metric
                label="R"
                value={
                  exit.unrealizedR != null
                    ? `${formatRatio2(exit.unrealizedR)}R`
                    : absentDataLabel()
                }
                density={density}
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
                className={cn(
                  "leading-snug text-amber-900 dark:text-amber-100",
                  text.micro,
                )}
                data-testid="operativa-analisis-trailing"
              >
                ↗ Trailing: {exit.trailingLabel}
              </p>
            ) : null}
            {exit.invalidation ? (
              <p
                className={cn(
                  "min-w-0 truncate leading-snug text-muted-foreground",
                  text.micro,
                )}
                title={exit.invalidation}
              >
                Invalida: {exit.invalidation}
              </p>
            ) : null}
          </div>
        </Row>
      ) : null}

      {showSeguimiento && analysis.gaps.length > 0 ? (
        <p
          className={cn("leading-snug text-muted-foreground", text.micro)}
          data-testid="operativa-analisis-gaps"
        >
          Falta: {analysis.gaps.join(" · ")}
        </p>
      ) : null}
    </section>
  );
}
