/**
 * Primitivas de UI compartidas por las superficies del Asesor (`/research`) — slice A3.
 *
 * `SectionTitle` y `Stat` vivían en `research-page.tsx` como funciones locales; se
 * mueven aquí con el MISMO marcado para que los paneles extraídos los compartan sin
 * duplicarlos. `formatShortDate` es el formateador de fecha corta que usaban el
 * resumen y el historial del laboratorio.
 *
 * A3·b añade las primitivas que Cartera tenía enterradas como funciones locales:
 * los tonos de cambio y de PnL, el mapa de tonos de tendencia y el badge de estado.
 * La tercera ronda de A3 añade `Kpi` (hero del Diario). El slice A4 pasa `Kpi` a
 * tokens del sistema y añade `ASESOR_CHANNEL_TONE`, la única fuente del color de
 * canal («aviso» ámbar / «alarma» rojo) para Análisis y Diario.
 */

import type { ReactNode } from "react";
import type { AsesorCarteraStateIdV1 } from "@bolsa/shared";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

export function SectionTitle({ children }: { children: ReactNode }) {
  return (
    <h2 className="text-lg font-semibold leading-none tracking-tight">
      {children}
    </h2>
  );
}

export function Stat({ label, value }: { label: string; value: string }) {
  return (
    <Card>
      <CardContent className="pt-4">
        <p className="text-xs text-muted-foreground">{label}</p>
        <p className="mt-1 text-2xl font-semibold tabular-nums tracking-tight">
          {value}
        </p>
      </CardContent>
    </Card>
  );
}

/**
 * KPI del hero del Diario (slice A4).
 *
 * Antes asumía un fondo oscuro fijo (`border-white/10`, `bg-black/20`,
 * `text-white`): en tema claro quedaba ilegible. Ahora usa tokens del sistema,
 * así que el mismo marcado funciona en claro y oscuro.
 */
export function Kpi({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: "pos" | "neg" | "neutral";
}) {
  return (
    <div className="rounded-lg border border-border bg-card/60 px-3 py-2">
      <p className="text-[10px] uppercase tracking-wide text-muted-foreground">
        {label}
      </p>
      <p
        className={cn(
          "mt-0.5 text-lg font-semibold tabular-nums text-foreground",
          tone === "pos" && "text-emerald-700 dark:text-emerald-300",
          tone === "neg" && "text-rose-700 dark:text-rose-300",
        )}
      >
        {value}
      </p>
    </div>
  );
}

/** Canal de dictamen del Asesor: los dos únicos niveles visibles. */
export type AsesorChannelLevel = "alarma" | "aviso";

/**
 * Tono ÚNICO del canal de dictamen (slice A4).
 *
 * El mismo concepto «aviso» era ámbar en Análisis y azul en Diario. Aquí vive la
 * única fuente de clases: ambos paneles leen de este mapa y ya no declaran
 * colores propios. `alarma` conserva su rojo.
 *
 * - `badge`: etiqueta compacta de un ítem de lista.
 * - `card` / `label` / `value`: tarjeta de canal del Diario.
 * - `chip`: aviso con borde (p. ej. el estado del Estudio en el hero).
 */
export const ASESOR_CHANNEL_TONE = {
  alarma: {
    badge: "bg-rose-500/15 text-rose-800 dark:text-rose-200",
    card: "border-rose-500/30 bg-rose-500/10",
    label: "text-rose-800/80 dark:text-rose-200/80",
    value: "text-rose-700 dark:text-rose-300",
    chip: "border-rose-500/40 bg-rose-500/10 text-rose-800 dark:text-rose-200",
  },
  aviso: {
    badge: "bg-amber-500/15 text-amber-900 dark:text-amber-100",
    card: "border-amber-500/30 bg-amber-500/10",
    label: "text-amber-900/80 dark:text-amber-100/80",
    value: "text-amber-800 dark:text-amber-200",
    chip: "border-amber-500/40 bg-amber-500/10 text-amber-900 dark:text-amber-100",
  },
} as const satisfies Record<AsesorChannelLevel, Record<string, string>>;

/** Fecha corta (`dd/mm hh:mm`) del histórico de experimentos. */
export function formatShortDate(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleString(undefined, {
      day: "2-digit",
      month: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

/** Tono del cambio diario: verde arriba, rojo abajo, neutro sin dato. */
export function toneForChange(value: number | null): string {
  if (value == null) return "text-muted-foreground";
  if (value < 0) return "text-rose-700 dark:text-rose-300";
  if (value > 0) return "text-emerald-700 dark:text-emerald-300";
  return "text-muted-foreground";
}

/** Tono del P&L no realizado: rojo si pierde, verde si gana, neutro sin dato. */
export function toneForPnl(value: number | null): string {
  if (value == null) return "text-muted-foreground";
  return value < 0
    ? "text-rose-700 dark:text-rose-300"
    : "text-emerald-700 dark:text-emerald-300";
}

/**
 * Tonos del rótulo de tendencia. `unknown` y `neutral` comparten el neutro: la
 * tendencia es contexto, no una señal de compra.
 */
export const ASESOR_TREND_TONE: Record<string, string> = {
  bullish: "text-emerald-700 dark:text-emerald-300",
  bearish: "text-rose-700 dark:text-rose-300",
  neutral: "text-muted-foreground",
  unknown: "text-muted-foreground",
};

/** Badge de la categoría de presentación (`Estado`), no una señal de compra. */
const ASESOR_STATE_BADGE: Record<AsesorCarteraStateIdV1, string> = {
  recomendacion_favorable:
    "border-emerald-500/40 bg-emerald-500/10 text-emerald-800 dark:text-emerald-200",
  evaluado_sin_oportunidad: "border-border bg-muted/40 text-muted-foreground",
  posicion_abierta:
    "border-sky-500/40 bg-sky-500/10 text-sky-800 dark:text-sky-200",
  posicion_sin_respaldo:
    "border-amber-500/50 bg-amber-500/10 text-amber-900 dark:text-amber-100",
  // Violeta es informativo en el resto del producto: la señal de salida sin
  // posición no es una alarma (ámbar) ni una posición viva (azul).
  senal_de_salida_sin_posicion:
    "border-violet-500/40 bg-violet-500/10 text-violet-800 dark:text-violet-200",
  sin_datos: "border-border bg-muted/20 text-muted-foreground",
};

export function AsesorStateBadge({
  stateId,
  label,
  title,
  testId,
}: {
  stateId: AsesorCarteraStateIdV1;
  label: string;
  title?: string;
  testId?: string;
}) {
  return (
    <span
      className={cn(
        "inline-block rounded border px-1.5 py-0.5 text-[10px] font-semibold",
        ASESOR_STATE_BADGE[stateId],
      )}
      data-testid={testId}
      title={title || undefined}
    >
      {label}
    </span>
  );
}
