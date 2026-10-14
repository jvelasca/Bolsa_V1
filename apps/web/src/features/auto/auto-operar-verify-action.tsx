/**
 * AUTO · OPERAR — lanzadera descubrible «Verificar D→hoy» de una operación (P2).
 *
 * Punto de entrada a la verificación DÍA-D desde el LISTADO de operaciones (`/auto/operar`),
 * no solo desde la tarjeta que vive dentro de la operación. Reutiliza el flujo compartido
 * (`useDiaDVerifyLaunch`): NO duplica la lógica de sesión/navegación.
 *
 * Honestidad (fail-closed): el CTA solo aparece cuando la estrategia EJECUTADA del ciclo se
 * resuelve (`verifyTarget === "executed"`). Si no se puede resolver, se declara el hueco visible
 * (`verifyGapReason`); NUNCA se cae al #1 ni se fabrica el enlace. Un hueco transitorio (lectura
 * en vuelo) se anuncia «Comprobando…», no como ausencia.
 *
 * @see apps/web/src/features/trading/use-dia-d-verify-launch.ts
 * @see apps/web/src/features/auto/auto-operation-strategy.ts
 */

import { Button } from "@/components/ui/button";
import { AUTO_OPERATION_STRATEGY_NO_DATA } from "@/features/auto/auto-operation-strategy";
import { useAutoOperationStrategy } from "@/features/auto/use-auto-operation-strategy";
import { VERIFY_DIA_D_CTA } from "@/features/platform/product-universe";
import { useDiaDVerifyLaunch } from "@/features/trading/use-dia-d-verify-launch";

export type AutoOperarVerifyCycle = {
  cycleId: string;
  instrumentId?: string | null;
  strategyPresetKey?: string | null;
  strategyVersion?: string | null;
};

export function AutoOperarVerifyAction({
  cycle,
}: {
  cycle: AutoOperarVerifyCycle;
}): React.ReactElement {
  const { view } = useAutoOperationStrategy({
    cycle: {
      instrumentId: cycle.instrumentId ?? null,
      strategyPresetKey: cycle.strategyPresetKey ?? null,
      strategyVersion: cycle.strategyVersion ?? null,
    },
  });
  const launchDiaDVerify = useDiaDVerifyLaunch();

  // Hueco TRANSITORIO: mientras se lee, no se declara ausencia.
  if (!view || view.loading) {
    return (
      <span
        className="text-[10px] text-muted-foreground"
        data-testid="auto-operar-verify-loading"
        data-cycle-id={cycle.cycleId}
      >
        Comprobando…
      </span>
    );
  }

  const instrumentId = view.instrumentId;
  const symbol = view.symbol;
  const executedStrategyDefinitionId = view.executedStrategyDefinitionId;

  // Fail-closed: el CTA exige la EJECUTADA resuelta; un hueco se declara, no se rellena.
  if (
    view.verifyTarget === "executed" &&
    instrumentId &&
    executedStrategyDefinitionId
  ) {
    return (
      <Button
        type="button"
        size="sm"
        variant="outline"
        className="h-6 shrink-0 rounded px-2 text-[10px]"
        data-testid="auto-operar-verify-dia-d"
        data-cycle-id={cycle.cycleId}
        onClick={() =>
          launchDiaDVerify({
            instrumentId,
            symbol,
            strategyDefinitionId: executedStrategyDefinitionId,
            strategyLabel:
              view.executedStrategyLabel ?? AUTO_OPERATION_STRATEGY_NO_DATA,
            rank: view.executedStrategyRank ?? 1,
            cycleId: cycle.cycleId,
            strategyPresetKey: cycle.strategyPresetKey ?? null,
            strategyVersion: cycle.strategyVersion ?? null,
          })
        }
      >
        {VERIFY_DIA_D_CTA}
      </Button>
    );
  }

  return (
    <span
      className="text-[10px] text-muted-foreground"
      data-testid="auto-operar-verify-gap"
      data-cycle-id={cycle.cycleId}
      title={view.verifyGapReason ?? undefined}
    >
      {view.verifyGapReason ?? AUTO_OPERATION_STRATEGY_NO_DATA}
    </span>
  );
}
