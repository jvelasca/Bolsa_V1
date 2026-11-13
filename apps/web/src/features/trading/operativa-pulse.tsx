/**
 * Bloque visual Índice Operativo + gauges TA/FA + ranking «El n de N en estudio».
 * Se muestra en Operativa → Recomendación (detalle) y resumen en cabecera colapsada.
 *
 * @see docs/engineering/trading-operativa-panel-2026-08-04.md
 */

import { cn } from "@/lib/utils";
import { absentDataLabel } from "@/components/absent-data";
import {
  OPERATIVA_TEXT,
  type OperativaDensity,
} from "@/features/trading/operativa-density";
import {
  estudioRankProgressPct,
  formatEstudioRankLabel,
} from "@/features/trading/operativa-index";

function scoreTone(score: number | null): string {
  if (score == null) return "text-muted-foreground";
  if (score >= 70) return "text-emerald-700 dark:text-emerald-300";
  if (score >= 45) return "text-amber-800 dark:text-amber-200";
  return "text-destructive";
}

function scoreRingTone(score: number | null): string {
  if (score == null) return "text-muted-foreground/35";
  if (score >= 70) return "text-emerald-500";
  if (score >= 45) return "text-amber-500";
  return "text-rose-500";
}

function scoreBand(score: number | null): string {
  if (score == null) return "Sin dato";
  if (score >= 70) return "Fuerte";
  if (score >= 45) return "Intermedio";
  return "Débil";
}

type GaugeKind = "io" | "ta" | "fa";

export type { GaugeKind };

const ALL_GAUGES: readonly GaugeKind[] = ["io", "ta", "fa"];

const GAUGE_META: Record<
  GaugeKind,
  { short: string; caption: string; blurb: string }
> = {
  io: {
    short: "IO",
    caption: "índice",
    blurb:
      "Índice operativo 0–100: atractivo relativo ahora (mezcla técnica + fundamental). Si hay alerta fundamental grave, se frena.",
  },
  ta: {
    short: "TA",
    caption: "técnico",
    blurb:
      "Técnico: gráfico y momentum (velas, tendencia). Alto = el precio se comporta bien; bajo = presión bajista o ruido.",
  },
  fa: {
    short: "FA",
    caption: "fundamental",
    blurb:
      "Fundamental: salud del negocio. Alto = empresa sólida; bajo o distress = más riesgo aunque el gráfico pinte bien.",
  },
};

function Gauge({
  kind,
  value,
  emphasize,
  density = "compact",
}: {
  kind: GaugeKind;
  value: number | null;
  emphasize?: boolean;
  density?: OperativaDensity;
}) {
  const meta = GAUGE_META[kind];
  const text = OPERATIVA_TEXT[density];
  const pct = value ?? 0;
  const r = 20;
  const c = 2 * Math.PI * r;
  const dash = value == null ? 0 : (pct / 100) * c;
  const title = [
    `${meta.short} (${meta.caption}): ${value ?? absentDataLabel()} · ${scoreBand(value)}`,
    meta.blurb,
  ].join("\n");

  return (
    <div
      className={cn(
        "flex min-w-0 flex-1 flex-col items-center gap-1 rounded-lg px-1 py-1",
        emphasize && "bg-muted/40 ring-1 ring-border/70",
      )}
      title={title}
    >
      <svg
        width="56"
        height="56"
        viewBox="0 0 56 56"
        className="shrink-0 drop-shadow-sm"
        aria-hidden
      >
        <circle
          cx="28"
          cy="28"
          r={r}
          fill="none"
          stroke="currentColor"
          strokeWidth="5"
          className="text-muted/35"
        />
        <circle
          cx="28"
          cy="28"
          r={r}
          fill="none"
          stroke="currentColor"
          strokeWidth="5"
          strokeLinecap="round"
          strokeDasharray={`${dash} ${c}`}
          transform="rotate(-90 28 28)"
          className={cn(
            "transition-[stroke-dasharray] duration-500",
            scoreRingTone(value),
          )}
        />
        <text
          x="28"
          y="31"
          textAnchor="middle"
          className={cn(
            "fill-current font-semibold tabular-nums",
            scoreTone(value),
          )}
          style={{ fontSize: 13 }}
        >
          {value ?? absentDataLabel()}
        </text>
      </svg>
      <div className="text-center leading-tight">
        <p
          className={cn(
            "font-bold tracking-wide",
            text.caption,
            emphasize ? "text-foreground" : "text-foreground/90",
          )}
        >
          {meta.short}
          <span className="ml-1 font-medium text-muted-foreground">
            {meta.caption}
          </span>
        </p>
        <p className={cn("tabular-nums", text.micro, scoreTone(value))}>
          {scoreBand(value)}
        </p>
      </div>
    </div>
  );
}

export function OperativaPulseBlock({
  io,
  ta,
  fa,
  rank,
  total,
  loading,
  className,
  gauges = ALL_GAUGES,
  showHeader = true,
  showRank = true,
  showHelp = true,
  density = "compact",
}: {
  io: number | null;
  ta: number | null;
  fa: number | null;
  rank: number | null;
  total: number;
  loading?: boolean;
  className?: string;
  /** Ruedas visibles; por defecto las tres (IO/TA/FA). */
  gauges?: readonly GaugeKind[];
  showHeader?: boolean;
  showRank?: boolean;
  showHelp?: boolean;
  density?: OperativaDensity;
}) {
  const text = OPERATIVA_TEXT[density];
  const progress =
    rank != null && total > 0 ? estudioRankProgressPct(rank, total) : 0;
  const rankLabel =
    rank != null && total > 0
      ? formatEstudioRankLabel(rank, total)
      : "Sin ranking en Estudio";
  const values: Record<GaugeKind, number | null> = { io, ta, fa };

  return (
    <div
      className={cn(
        "space-y-2.5 rounded-lg border border-border/70 bg-gradient-to-b from-muted/35 to-transparent px-2 py-2",
        className,
      )}
      data-testid="operativa-pulse"
      data-density={density}
      aria-label="Índice operativo"
    >
      {showHeader ? (
        <div className="space-y-0.5 px-0.5">
          <p className={cn("font-semibold text-foreground", text.body)}>
            Pulso del valor
          </p>
          <p className={cn("leading-snug text-muted-foreground", text.caption)}>
            Tres lecturas 0–100. Pasa el ratón por cada rueda para el detalle.
            Verde ≈ fuerte · ámbar ≈ intermedio · rojo ≈ débil.
          </p>
        </div>
      ) : null}

      <div className="flex items-stretch justify-between gap-0.5">
        {gauges.map((kind) => (
          <Gauge
            key={kind}
            kind={kind}
            value={loading ? null : values[kind]}
            emphasize={kind === "io" && gauges.length > 1}
            density={density}
          />
        ))}
      </div>

      {showRank ? (
        <div className="space-y-1.5 rounded-md border border-border/50 bg-background/50 px-2 py-1.5">
          <p
            className={cn(
              "text-center font-medium text-foreground",
              text.body,
            )}
            data-testid="operativa-rank-label"
          >
            {loading ? "Calculando ranking…" : rankLabel}
          </p>
          <div
            className="h-2 overflow-hidden rounded-full bg-muted"
            title={rankLabel}
            role="meter"
            aria-valuenow={progress}
            aria-valuemin={0}
            aria-valuemax={100}
          >
            <div
              className="h-full rounded-full bg-emerald-500/85 transition-[width] duration-500"
              style={{ width: `${loading ? 0 : progress}%` }}
            />
          </div>
          <p
            className={cn(
              "text-center leading-snug text-muted-foreground",
              text.micro,
            )}
          >
            Compara este valor con los demás de tu lista{" "}
            <span className="font-medium text-foreground/80">Estudio</span> (#1 =
            mejor índice). No es una orden de compra.
          </p>
        </div>
      ) : null}

      {showHelp ? (
        <details className="group rounded-md border border-border/40 bg-background/40 px-2 py-1">
          <summary
            className={cn(
              "cursor-pointer select-none font-medium text-foreground/90 marker:content-none [&::-webkit-details-marker]:hidden",
              text.caption,
            )}
          >
            <span className="underline-offset-2 group-open:underline">
              ¿Qué mirar? (básico)
            </span>
            <span className="ml-1 text-muted-foreground">
              · avanzado al abrir
            </span>
          </summary>
          <div
            className={cn(
              "mt-1.5 space-y-1.5 border-t border-border/40 pt-1.5 leading-snug text-muted-foreground",
              text.caption,
            )}
          >
            <p>
              <span className="font-semibold text-foreground">Básico — </span>
              Si IO y TA van altos y FA no está en distress, el valor suele estar
              en buena forma relativa. Si FA está débil, el gráfico puede engañar.
            </p>
            <p>
              <span className="font-semibold text-foreground">Avanzado — </span>
              IO = Composite 0–100 con suelo ≤40 si hay distress FA. Ranking solo
              entre miembros de Estudio. El dictamen de abajo traduce esto a una
              postura (comprar / esperar / revisar), distinta de las ★ del TOP
              Lab.
            </p>
          </div>
        </details>
      ) : null}
    </div>
  );
}

/** Resumen compacto para cabecera colapsada. */
export function OperativaPulseSummary({
  io,
  rank,
  total,
}: {
  io: number | null;
  rank: number | null;
  total: number;
}) {
  if (rank == null || total <= 0) {
    return (
      <span className={cn("tabular-nums", scoreTone(io))}>
        IO {io ?? absentDataLabel()}
      </span>
    );
  }
  return (
    <span className="truncate text-[10px] text-muted-foreground">
      <span className={cn("font-semibold tabular-nums", scoreTone(io))}>
        IO {io ?? absentDataLabel()}
      </span>
      {" · "}
      {rank}/{total}
    </span>
  );
}
