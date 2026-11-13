/**
 * S4 · Recomendación principal de la ventana maximizada de DECISIÓN.
 *
 * Qué hace: pone en primer nivel **una sola** recomendación (la del dictamen, S1)
 * y, debajo y sin competir con ella, el estado de cartera (clasificador S3) y la
 * vía de actuación. El contexto técnico no entra aquí: vive en su propia columna.
 *
 * Qué NO hace: no recalcula la postura, no combina tendencia ni niveles, no firma
 * ni ejecuta. La firma sigue en Confirm y la operación en ACCIÓN.
 *
 * @see docs/engineering/diseno-decision-maximizada-s4-2026-11-12.md
 */

import type {
  AsesorCarteraStateIdV1,
  AsesorCarteraStateV1,
  InstrumentDailyOpinionV1,
} from "@bolsa/shared";
import { asesorCarteraStateDefinition } from "@bolsa/shared";
import { cn } from "@/lib/utils";
import { OperativaDictamenBlock } from "@/features/trading/operativa-dictamen";
import type { OperativaActionHintV1 } from "@/features/trading/operativa-action-hint";

const STATE_TONE: Record<AsesorCarteraStateIdV1, string> = {
  recomendacion_favorable:
    "border-emerald-600/45 bg-emerald-500/10 text-emerald-900 dark:text-emerald-100",
  posicion_abierta:
    "border-sky-600/45 bg-sky-500/10 text-sky-900 dark:text-sky-100",
  posicion_sin_respaldo:
    "border-amber-600/45 bg-amber-500/10 text-amber-950 dark:text-amber-100",
  evaluado_sin_oportunidad: "border-border bg-muted/30 text-muted-foreground",
  sin_datos: "border-border bg-muted/20 text-muted-foreground",
};

const ACTION_TONE: Record<OperativaActionHintV1["id"], string> = {
  entrada_disponible:
    "border-emerald-600/45 bg-emerald-500/10 text-emerald-900 dark:text-emerald-100",
  entrada_bloqueada:
    "border-amber-600/45 bg-amber-500/10 text-amber-950 dark:text-amber-100",
  salida_en_accion:
    "border-sky-600/45 bg-sky-500/10 text-sky-900 dark:text-sky-100",
  sin_actuacion: "border-border bg-muted/30 text-muted-foreground",
};

export type OperativaRecomendacionPrincipalProps = {
  symbol: string;
  opinion: InstrumentDailyOpinionV1 | null | undefined;
  opinionLoading?: boolean;
  carteraState: AsesorCarteraStateV1;
  actionHint: OperativaActionHintV1;
  className?: string;
};

export function OperativaRecomendacionPrincipal({
  symbol,
  opinion,
  opinionLoading = false,
  carteraState,
  actionHint,
  className,
}: OperativaRecomendacionPrincipalProps) {
  const definition = asesorCarteraStateDefinition(carteraState.id);
  const stateTitle = [definition.meaning, ...carteraState.gaps]
    .filter(Boolean)
    .join(" · ");
  // Mientras se mide el dictamen no se afirma ninguna categoría de cartera: el
  // estado se deriva del dictamen y una ausencia de lectura no es «sin datos».
  const showState = !opinionLoading;

  return (
    <section
      className={cn(
        "min-w-0 space-y-2 rounded-md border border-border/80 bg-card/60 p-2.5",
        className,
      )}
      data-testid="operativa-recomendacion-principal"
      data-state={showState ? carteraState.id : "midiendo"}
      data-action-hint={showState ? actionHint.id : "midiendo"}
      aria-label={`Recomendación principal · ${symbol}`}
    >
      <div className="flex flex-wrap items-center justify-between gap-1.5">
        <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
          Recomendación del día
          <span className="ml-1 font-normal normal-case">· {symbol}</span>
        </p>
        {showState ? (
          <span
            className={cn(
              "rounded border px-1.5 py-0.5 text-[10px] font-semibold",
              STATE_TONE[carteraState.id],
            )}
            data-testid="operativa-cartera-state"
            data-state={carteraState.id}
            title={stateTitle || undefined}
          >
            {carteraState.label}
          </span>
        ) : null}
      </div>

      <OperativaDictamenBlock
        opinion={opinion ?? null}
        loading={opinionLoading}
        variant="hero"
      />

      {showState ? (
        <>
          <div
            className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5 border-t border-border/60 pt-1.5"
            data-testid="operativa-actuacion"
          >
            <span className="text-[9px] font-semibold uppercase tracking-wide text-muted-foreground">
              Actuación
            </span>
            <span
              className={cn(
                "rounded border px-1.5 py-0.5 text-[10px] font-semibold",
                ACTION_TONE[actionHint.id],
              )}
              data-action-hint={actionHint.id}
              data-blocked-reason={actionHint.blockedReason ?? undefined}
            >
              {actionHint.label}
            </span>
            <p className="min-w-0 flex-1 text-[10px] leading-snug text-muted-foreground">
              {actionHint.detail}
            </p>
          </div>

          <p
            className="text-[10px] leading-snug text-muted-foreground"
            data-testid="operativa-recomendacion-aviso"
          >
            Esta ventana informa: la recomendación no ejecuta. La firma vive en
            Confirm y la operación en ACCIÓN. Tendencia, fuerza y niveles son
            contexto técnico, no órdenes.
          </p>
        </>
      ) : (
        <p
          className="text-[10px] text-muted-foreground"
          data-testid="operativa-recomendacion-aviso"
        >
          El estado de cartera se declara cuando termina la medición del
          dictamen.
        </p>
      )}
    </section>
  );
}
