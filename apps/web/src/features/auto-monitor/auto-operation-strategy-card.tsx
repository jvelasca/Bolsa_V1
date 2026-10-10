/**
 * Tarjeta «Estrategia que sustenta la señal» (puente P3/P4 de la operación AUTO).
 *
 * Presentacional y pura: recibe la vista ya compuesta (`AutoOperationStrategyViewV1`) y solo la
 * pinta. Conserva la identidad de testids del panel para no romper la auditoría de UI.
 *
 * Honestidad: mientras la vista está `loading`, un hueco es TRANSITORIO (no se pinta un falso
 * «Sin dato todavía»); con `rank !== 1` se declara explícitamente que NO es la #1 del valor.
 *
 * @see apps/web/src/features/auto/auto-operation-strategy.ts
 */

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  AUTO_OPERATION_STRATEGY_DESCRIPTION,
  AUTO_OPERATION_STRATEGY_NO_DATA,
  AUTO_OPERATION_STRATEGY_TITLE,
  type AutoOperationStrategyViewV1,
} from "@/features/auto/auto-operation-strategy";
import { VERIFY_DIA_D_CTA } from "@/features/platform/product-universe";

/** Máximo de razones pintadas (la lista completa puede ser larga; se acota por legibilidad). */
const MAX_REASON_ROWS = 5;

export function AutoOperationStrategyCard({
  view,
  onVerify,
  disabled = false,
  loading = false,
}: {
  view: AutoOperationStrategyViewV1;
  onVerify: () => void;
  disabled?: boolean;
  loading?: boolean;
}): React.ReactElement {
  // Puesto real de la estrategia: solo se rotula «#1» cuando de verdad lo es (o no se sabe).
  const rank = view.rank;
  const notTop1 = rank != null && rank !== 1;
  // En carga, un valor ausente se declara como carga, nunca como ausencia de dato.
  const placeholder = loading ? "Cargando…" : AUTO_OPERATION_STRATEGY_NO_DATA;

  return (
    <Card
      className="rounded-xl border border-border bg-card"
      data-testid="auto-operation-strategy"
      data-match={view.match}
    >
      <CardHeader className="pb-2">
        <CardTitle className="text-sm">
          {AUTO_OPERATION_STRATEGY_TITLE}
        </CardTitle>
        <p className="text-xs text-muted-foreground">
          {AUTO_OPERATION_STRATEGY_DESCRIPTION}
        </p>
      </CardHeader>
      <CardContent className="space-y-2">
        <dl
          className="grid gap-x-4 gap-y-1 text-sm sm:grid-cols-2"
          data-testid="auto-operation-strategy-chain"
        >
          <div>
            <dt className="text-muted-foreground">
              {notTop1 ? "Estrategia del valor" : "Estrategia #1"}
            </dt>
            <dd
              className="font-medium"
              data-testid="auto-operation-strategy-label"
            >
              {view.strategyDefinitionId
                ? `${rank != null ? `#${rank} ` : ""}${view.strategyLabel}`
                : placeholder}
            </dd>
            {notTop1 ? (
              <p
                className="text-[11px] text-amber-600 dark:text-amber-400"
                data-testid="auto-operation-strategy-rank-note"
              >
                No es la #1: el valor sitúa esta estrategia en el puesto #{rank}
                .
              </p>
            ) : null}
          </div>
          <div>
            <dt className="text-muted-foreground">Indicadores</dt>
            <dd data-testid="auto-operation-strategy-indicators">
              {view.indicators.length > 0
                ? view.indicators.join(" · ")
                : placeholder}
            </dd>
          </div>
          <div className="sm:col-span-2">
            <dt className="text-muted-foreground">Razón</dt>
            <dd data-testid="auto-operation-strategy-reason">
              {view.reasons.length > 0 ? (
                <ul className="list-disc space-y-0.5 pl-4 text-xs text-muted-foreground">
                  {view.reasons
                    .slice(0, MAX_REASON_ROWS)
                    .map((reason, index) => (
                      <li key={`${index}-${reason}`}>{reason}</li>
                    ))}
                </ul>
              ) : (
                placeholder
              )}
            </dd>
          </div>
          <div className="sm:col-span-2">
            <dt className="text-muted-foreground">
              Estrategia declarada por el ciclo
            </dt>
            <dd
              data-testid="auto-operation-strategy-match"
              data-match={view.match}
            >
              {view.declaredCycleStrategyVersion ??
                AUTO_OPERATION_STRATEGY_NO_DATA}{" "}
              · {view.matchLabel}
            </dd>
          </div>
        </dl>
        {loading ? (
          <p
            className="text-xs text-muted-foreground"
            data-testid="auto-operation-strategy-loading"
          >
            Cargando…
          </p>
        ) : view.gapReason ? (
          <p
            className="text-xs text-muted-foreground"
            data-testid="auto-operation-strategy-gap"
          >
            {view.gapReason}
          </p>
        ) : null}
        <Button
          type="button"
          size="sm"
          variant="default"
          data-testid="auto-operation-strategy-verify-dia-d"
          className="h-7 rounded px-2 text-xs"
          disabled={disabled}
          title={
            disabled
              ? "Sin dato todavía: falta el instrumento o la estrategia #1"
              : "Verificar D→hoy en LAB (Análisis técnico · Cartera LAB · Auto)"
          }
          onClick={onVerify}
        >
          {VERIFY_DIA_D_CTA}
        </Button>
      </CardContent>
    </Card>
  );
}
