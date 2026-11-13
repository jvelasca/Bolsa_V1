/**
 * Lectura de estructura y niveles calculados (S2).
 *
 * Responde de un vistazo: qué estructura hay, qué niveles son `detectado` y por
 * qué los demás NO lo son (no fiable, roto, en precio, no disponible). La fuerza
 * del estudio (ADX/DI) se pinta en una línea aparte: nunca se fusiona con la
 * estructura ni se usa para calcularla.
 *
 * Trazabilidad: cada nivel declara sus pivotes, la ventana y la firma de entrada.
 * Trazable significa reproducible con esas velas y parámetros; no es un hecho
 * durable ni se persiste.
 *
 * @see docs/engineering/metodologia-soportes-resistencias-tendencia-2026-11-12.md
 */

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  MARKET_STRUCTURE_METHOD_LABEL,
  computeMarketStructure,
  formatLevel,
  marketLevelKindLabel,
  marketLevelKindShortLabel,
  marketLevelStateLabel,
  marketStructureTrendLabel,
  marketStructureLevels,
  visibleLevelReasons,
  type MarketLevelV1,
  type MarketStructureResultV1,
  type OhlcvBarDto,
} from "@bolsa/shared";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import {
  OPERATIVA_TEXT,
  type OperativaDensity,
} from "@/features/trading/operativa-density";

export type MarketStructureStudyStrength = {
  /** Fuerza medida del estudio (escala del productor: 0–10 por defecto). */
  value?: number | null;
  max?: 10 | 100;
  band?: string | null;
  /** ADX/DI del estudio, si ya vienen calculados. S2 no los recalcula. */
  adx?: number | null;
  diPlus?: number | null;
  diMinus?: number | null;
};

function finite(value: number | null | undefined): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function roundOne(value: number): string {
  return String(Math.round(value * 10) / 10).replace(".", ",");
}

/** Contexto de fuerza, SIEMPRE separado de la estructura de pivotes. */
export function describeStudyStrength(
  input: MarketStructureStudyStrength | null | undefined,
): { measured: boolean; text: string } {
  if (input) {
    if (finite(input.value)) {
      const band = input.band?.trim();
      const max = input.max ?? 10;
      return {
        measured: true,
        text: `Fuerza del estudio: ${roundOne(input.value)} / ${max}${band ? ` · ${band}` : ""}`,
      };
    }
    if (finite(input.adx)) {
      const parts = [`ADX ${roundOne(input.adx)}`];
      if (finite(input.diPlus)) parts.push(`+DI ${roundOne(input.diPlus)}`);
      if (finite(input.diMinus)) parts.push(`−DI ${roundOne(input.diMinus)}`);
      return { measured: true, text: `Fuerza del estudio: ${parts.join(" · ")}` };
    }
  }
  return { measured: false, text: "Sin dato de fuerza" };
}

function formatDistance(distancePct: number | null): string {
  if (!finite(distancePct)) return "sin distancia medida";
  const sign = distancePct >= 0 ? "+" : "−";
  return `${sign}${Math.abs(distancePct).toFixed(1).replace(".", ",")} %`;
}

function formatShortDate(timestamp: string | null): string {
  if (!timestamp) return "sin fecha";
  const day = timestamp.slice(0, 10);
  return /^\d{4}-\d{2}-\d{2}$/.test(day) ? day : timestamp;
}

/** Color de la estructura: informa, no recomienda. */
function structureTone(id: MarketStructureResultV1["structure"]["id"]): string {
  switch (id) {
    case "ascendente":
      return "text-emerald-600 dark:text-emerald-400";
    case "descendente":
      return "text-rose-600 dark:text-rose-400";
    case "en_rango":
      return "text-amber-600 dark:text-amber-400";
    default:
      return "text-muted-foreground";
  }
}

function stateTone(level: MarketLevelV1): string {
  switch (level.state) {
    case "detectado":
      return "border-teal-600/50 bg-teal-500/10 text-teal-800 dark:text-teal-200";
    case "roto":
      return "border-rose-600/40 bg-rose-500/10 text-rose-800 dark:text-rose-200";
    case "en_precio":
      return "border-amber-600/40 bg-amber-500/10 text-amber-900 dark:text-amber-100";
    default:
      return "border-border bg-muted/40 text-muted-foreground";
  }
}

function LevelRow({
  level,
  close,
  collision,
  density = "compact",
}: {
  level: MarketLevelV1;
  close: number | null;
  collision: string | null;
  density?: OperativaDensity;
}) {
  const text = OPERATIVA_TEXT[density];
  const stateLabel = marketLevelStateLabel(level.state) ?? "Estado no declarado";
  const reasons = visibleLevelReasons(level.reasons);
  return (
    <li
      className="rounded-md border border-border/70 bg-background/60 px-2 py-1"
      data-testid="market-structure-level"
      data-kind={level.kind}
      data-state={level.state}
      data-touches={level.touches}
    >
      <div className="flex flex-wrap items-baseline justify-between gap-1">
        <span className="font-medium tabular-nums text-foreground">
          {marketLevelKindShortLabel(level.kind)} · {formatLevel(level.price)}
        </span>
        <span
          className={cn(
            "rounded border px-1 py-0.5 leading-none",
            text.micro,
            stateTone(level),
          )}
        >
          {stateLabel}
        </span>
      </div>
      <div
        className={cn(
          "mt-0.5 flex flex-wrap gap-x-2 tabular-nums text-muted-foreground",
          text.micro,
        )}
      >
        <span>{marketLevelKindLabel(level.kind)}</span>
        <span>
          {level.touches} toque{level.touches === 1 ? "" : "s"}
        </span>
        <span>{formatDistance(level.distancePct)}</span>
        <span>zona {formatLevel(level.zoneLow)}–{formatLevel(level.zoneHigh)}</span>
      </div>
      {close != null ? (
        <span className="sr-only">Cierre de referencia {formatLevel(close)}</span>
      ) : null}
      {collision ? (
        <p className={cn("mt-0.5 text-sky-700 dark:text-sky-300", text.micro)}>
          Coincide con {collision}: manda el nivel operativo.
        </p>
      ) : null}
      {reasons.visible.length > 0 ? (
        <p className={cn("mt-0.5 text-muted-foreground", text.micro)}>
          {reasons.visible.join(" · ")}
        </p>
      ) : null}
    </li>
  );
}

export function MarketStructureReadoutView({
  bars,
  timeframe,
  studyStrength,
  planLevels,
  className,
  loading = false,
  error = false,
  showHeading = true,
  density = "compact",
}: {
  bars: readonly OhlcvBarDto[];
  timeframe: string;
  studyStrength?: MarketStructureStudyStrength | null;
  planLevels?: readonly { price: number; title: string }[];
  className?: string;
  loading?: boolean;
  error?: boolean;
  /** En una ficha con su propia tarjeta, el título ya lo pone la tarjeta. */
  showHeading?: boolean;
  density?: OperativaDensity;
}) {
  const text = OPERATIVA_TEXT[density];
  const result = useMemo(
    () => computeMarketStructure({ bars, timeframe }),
    [bars, timeframe],
  );
  const strength = describeStudyStrength(studyStrength);
  const levels = marketStructureLevels(result);
  const drawable = levels.filter((level) => level.state === "detectado");
  const structureLabel =
    marketStructureTrendLabel(result.structure.id) ?? "Sin estructura suficiente";

  const collisions = new Map<MarketLevelV1, string>();
  if (result.atrRef != null && planLevels?.length) {
    const tolerance = result.atrRef * result.params.inPriceAtrMultiple;
    for (const level of levels) {
      const match = planLevels.find(
        (plan) => Math.abs(plan.price - level.price) <= tolerance,
      );
      if (match) collisions.set(level, match.title);
    }
  }

  return (
    <section
      className={cn(
        "rounded-md border border-border/70 bg-card/60",
        density === "dock" ? "text-xs" : "text-[11px]",
        "px-2 py-1.5",
        className,
      )}
      data-testid="market-structure-readout"
      data-status={result.status}
      data-structure={result.structure.id}
      data-drawable={drawable.length}
      data-density={density}
      aria-label="Estructura y niveles calculados"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-1">
        {showHeading ? (
          <h2 className={cn("font-medium text-foreground", text.body)}>
            Estructura y niveles calculados
          </h2>
        ) : (
          <span className="sr-only">Estructura y niveles calculados</span>
        )}
        <span className={cn("text-muted-foreground", text.micro)}>
          {MARKET_STRUCTURE_METHOD_LABEL}
        </span>
      </div>

      {loading ? (
        <p className="mt-1 text-muted-foreground">Leyendo estructura…</p>
      ) : error ? (
        <p className="mt-1 text-destructive">No se pudo medir la estructura.</p>
      ) : result.status !== "ok" ? (
        <p className="mt-1 text-muted-foreground" data-testid="market-structure-gap">
          {result.status === "insufficient_history"
            ? `Histórico insuficiente: ${result.window.bars} velas (mínimo ${result.params.minBars})`
            : result.reasons.includes("sin_velas")
              ? "Sin datos OHLCV"
              : result.reasons.includes("velas_invalidas")
                ? "Velas inválidas en la ventana"
                : result.reasons.includes("sin_atr")
                  ? "Sin ATR calculable en la ventana"
                  : "Sin pivotes confirmados en la ventana"}
        </p>
      ) : (
        <>
          <p className="mt-0.5 flex flex-wrap items-baseline gap-x-2">
            <span className={cn("font-medium", structureTone(result.structure.id))}>
              {structureLabel}
            </span>
            <span className={cn("text-muted-foreground", text.micro)}>
              {result.window.bars} velas · {result.window.timeframe} ·{" "}
              {result.structure.highs.length} máx / {result.structure.lows.length} mín
            </span>
          </p>
          <p
            className={cn("text-muted-foreground", text.micro)}
            data-testid="market-structure-strength"
            data-measured={strength.measured ? "true" : "false"}
          >
            {strength.text}
          </p>

          {levels.length === 0 ? (
            <p className="mt-1 text-muted-foreground">
              Sin niveles fiables en la ventana.
            </p>
          ) : (
            <ul className="mt-1 space-y-1">
              {levels.map((level, index) => (
                <LevelRow
                  key={`${level.kind}:${index}`}
                  level={level}
                  close={result.close}
                  collision={collisions.get(level) ?? null}
                  density={density}
                />
              ))}
            </ul>
          )}

          <details className="mt-1">
            <summary
              className={cn(
                "cursor-pointer font-medium text-muted-foreground underline-offset-2 hover:underline",
                text.micro,
              )}
              data-testid="market-structure-provenance-toggle"
            >
              Ver procedencia
            </summary>
            <div
              className={cn(
                "mt-1 space-y-1 text-muted-foreground",
                text.micro,
              )}
            >
              <p>
                Ventana {formatShortDate(result.window.from)} →{" "}
                {formatShortDate(result.window.to)} · ATR{" "}
                {result.atrRef != null ? formatLevel(result.atrRef) : "sin medir"} ·
                pivote {result.params.pivotLookback} · agrupación{" "}
                {String(result.params.clusterAtrMultiple).replace(".", ",")} ATR
              </p>
              <p className="break-all">
                Método {result.methodId} v{result.methodVersion} · firma{" "}
                {result.inputSignature}
              </p>
              {levels.map((level, index) => (
                <p key={`pivots:${level.kind}:${index}`}>
                  {marketLevelKindShortLabel(level.kind)} ·{" "}
                  {level.pivots
                    .map(
                      (pivot) =>
                        `${formatShortDate(pivot.timestamp)} ${formatLevel(pivot.price)}`,
                    )
                    .join(" · ")}
                  {level.lastTouchAt
                    ? ` · último toque ${formatShortDate(level.lastTouchAt)}`
                    : ""}
                </p>
              ))}
            </div>
          </details>
        </>
      )}
    </section>
  );
}

/**
 * Carga las velas con la MISMA query key que el gráfico (`["ohlcv", id, tf]`)
 * para no duplicar fetch en OPERATIVA.
 */
export function MarketStructureReadout({
  instrumentId,
  timeframe,
  studyStrength,
  planLevels,
  className,
  showHeading,
  density,
}: {
  instrumentId: string | null;
  timeframe: string;
  studyStrength?: MarketStructureStudyStrength | null;
  planLevels?: readonly { price: number; title: string }[];
  className?: string;
  showHeading?: boolean;
  density?: OperativaDensity;
}) {
  const ohlcvQuery = useQuery({
    queryKey: ["ohlcv", instrumentId, timeframe],
    queryFn: () => api.getOhlcv(instrumentId!, 500, timeframe),
    enabled: Boolean(instrumentId),
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });

  return (
    <MarketStructureReadoutView
      bars={ohlcvQuery.data?.data ?? []}
      timeframe={timeframe}
      studyStrength={studyStrength}
      planLevels={planLevels}
      className={className}
      loading={ohlcvQuery.isLoading}
      error={ohlcvQuery.isError}
      showHeading={showHeading}
      density={density}
    />
  );
}
