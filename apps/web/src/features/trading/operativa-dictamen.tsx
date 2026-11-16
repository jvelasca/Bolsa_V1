/**
 * Bloque compacto de recomendación del día (OPERATIVA · DECISIÓN).
 *
 * Una sola lectura: qué recomienda el motor, por qué y con cuánta confianza.
 * El motor no cambia: la postura y los motivos llegan con su clave interna y
 * aquí solo se traducen (`market-vocabulary`). Prohibido pintar `snake_case`,
 * un kicker de «postura» o una ★ como autorización de compra.
 */

import type { ReactNode } from "react";
import {
  formatConfidence,
  formatDictamenStars,
  marketReasonLabel,
  marketStanceLabelFromKey,
  type MarketStanceFamily,
  visibleReasons,
} from "@bolsa/shared";
import { cn } from "@/lib/utils";
import {
  OPERATIVA_TEXT,
  type OperativaDensity,
} from "@/features/trading/operativa-density";

const FAMILY_TONE: Record<MarketStanceFamily, string> = {
  alcista:
    "border-emerald-600/40 bg-emerald-500/10 text-emerald-950 dark:text-emerald-50",
  neutral: "border-border/70 bg-muted/30 text-foreground",
  bajista: "border-rose-600/40 bg-rose-500/10 text-rose-950 dark:text-rose-50",
  sin_senal:
    "border-amber-600/40 bg-amber-500/10 text-amber-950 dark:text-amber-50",
};

/**
 * Entrada mínima de dictamen: solo los campos que la superficie realmente trae.
 *
 * `InstrumentDailyOpinionV1` la satisface; además permite que una superficie que
 * no recibe el objeto completo (p. ej. la fila del parte diario) declare lo que
 * sí tiene —postura, motivos y ★— sin fabricar los campos ausentes.
 */
export type OperativaDictamenInputV1 = {
  stance: string;
  reasons?: readonly string[] | null;
  dictamenStars?: number | null;
  ioScore?: number | null;
  distress?: boolean;
};

/** Las ★ del dictamen salen del IO; sin IO medido no se pinta un 3 fabricado. */
function starsText(opinion: OperativaDictamenInputV1): string {
  if (opinion.ioScore == null) return "Sin medir";
  return formatDictamenStars(opinion.dictamenStars);
}

export function OperativaDictamenBlock({
  opinion,
  loading,
  className,
  variant = "compact",
  density = "compact",
  children,
}: {
  opinion: OperativaDictamenInputV1 | null | undefined;
  loading?: boolean;
  className?: string;
  /**
   * S4 — `hero` es la recomendación principal de la ventana maximizada: mismo
   * texto y mismas reglas que `compact`, solo cambia la escala tipográfica.
   * Nunca añade matices ni una segunda lectura de la postura.
   *
   * A2 — `cell` es la celda de tabla o ítem de lista de Asesor: no pinta borde
   * ni fondo propios, usa tipografía compacta y añade un slot de chips debajo.
   * No cambia el texto: la etiqueta, el detalle, la confianza, las ★ y los
   * motivos salen de las mismas funciones canónicas que en `compact`.
   */
  variant?: "compact" | "hero" | "cell";
  /** `dock` sube la escala del bloque compacto para el rail minimizado. */
  density?: OperativaDensity;
  /** Chips propios del panel (riesgo, veto/aviso…). Solo se pintan si existen. */
  children?: ReactNode;
}) {
  const hero = variant === "hero";
  const cell = variant === "cell";
  const text = OPERATIVA_TEXT[density];
  const bodyClass = hero ? "text-sm" : cell ? "text-[11px]" : text.body;
  if (loading) {
    return (
      <p
        className={cn("text-muted-foreground", bodyClass, className)}
        data-testid="operativa-dictamen"
        data-variant={variant}
        data-density={density}
      >
        {hero ? "Midiendo recomendación…" : "Calculando recomendación…"}
      </p>
    );
  }
  if (!opinion) {
    return (
      <p
        className={cn("text-muted-foreground", bodyClass, className)}
        data-testid="operativa-dictamen"
        data-variant={variant}
        data-density={density}
      >
        Sin recomendación todavía.
      </p>
    );
  }

  const resolution = marketStanceLabelFromKey({
    stance: opinion.stance,
    reasons: opinion.reasons,
  });
  if (!resolution) {
    return (
      <p
        className={cn("text-muted-foreground", bodyClass, className)}
        data-testid="operativa-dictamen"
        data-variant={variant}
        data-density={density}
      >
        Sin dictamen.
      </p>
    );
  }
  const reasons = visibleReasons(opinion.reasons, { ioScore: opinion.ioScore });
  const allReasons = (opinion.reasons ?? [])
    .map((reason) => marketReasonLabel(reason))
    .filter((label): label is string => Boolean(label));
  const confidence = formatConfidence(opinion.ioScore);
  const stars = starsText(opinion);

  return (
    <div
      className={cn(
        !cell && "rounded-md border px-2 py-1.5",
        !cell && hero && "px-3 py-2",
        !cell && FAMILY_TONE[resolution.family],
        cell && "space-y-0.5 leading-snug",
        className,
      )}
      data-testid="operativa-dictamen"
      data-variant={variant}
      data-density={density}
      data-stance-family={resolution.family}
      data-diagnostic-only={resolution.diagnosticOnly ? "1" : "0"}
      title={[
        `Recomendación: ${resolution.label}`,
        resolution.detail,
        `Confianza: ${confidence}`,
        allReasons.length > 0 ? `Motivos: ${allReasons.join("; ")}` : null,
      ]
        .filter(Boolean)
        .join(" · ")}
    >
      <p className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
        <span
          className={cn(
            "font-medium uppercase tracking-wide opacity-70",
            hero ? "text-[10px]" : cell ? "text-[9px]" : text.micro,
          )}
        >
          Recomendación
        </span>
        <span
          className={cn(
            "font-semibold tracking-tight",
            hero
              ? "text-2xl leading-tight"
              : density === "dock"
                ? "text-base"
                : cell
                  ? "text-[11px]"
                  : "text-sm",
          )}
        >
          {resolution.label}
        </span>
        {resolution.detail ? (
          <span
            className={cn(
              "font-medium opacity-85",
              hero ? "text-[11px]" : cell ? "text-[10px]" : text.caption,
            )}
          >
            {resolution.detail}
          </span>
        ) : null}
      </p>
      <p
        className={cn(
          "mt-0.5 flex flex-wrap items-baseline gap-x-2 opacity-85",
          hero ? "text-[11px]" : cell ? "text-[10px]" : text.caption,
        )}
      >
        <span className="tabular-nums">Confianza {confidence}</span>
        <span
          className="tabular-nums"
          title="★ de la recomendación del día: no es la ★ de la estrategia del Lab."
        >
          {stars}
        </span>
        {opinion.distress ? (
          <span className="font-semibold">Alerta fundamental</span>
        ) : null}
      </p>
      {reasons.visible.length > 0 ? (
        <p
          className={cn(
            "mt-0.5 leading-snug opacity-80",
            hero ? "text-[11px]" : cell ? "text-[10px]" : text.caption,
          )}
          title={allReasons.join(" · ")}
          data-testid="operativa-dictamen-motivos"
        >
          {reasons.visible.join(" · ")}
          {reasons.hiddenCount > 0 ? ` (+${reasons.hiddenCount})` : ""}
        </p>
      ) : null}
      {children ? (
        <div className="mt-1 flex flex-wrap items-center gap-1">{children}</div>
      ) : null}
    </div>
  );
}
