import type {
  LabBoardZone,
  LabReanalyzeRequest,
} from "@/features/backtests/backtest-lab-board-types";
import { BacktestLabBoard } from "@/features/backtests/backtest-lab-board";
import type { ProfileHorizon, RiskTolerance } from "@bolsa/shared";
import { Button } from "@/components/ui/button";

interface Props {
  /** El resultado Lab está activo (`resultFocus === "lab"`). Gobierna clase/aria del contenedor. */
  isLabFocus: boolean;
  /** Hay alguna semilla (zona o prefill) para el tablero. */
  hasSeeds: boolean;
  zones: LabBoardZone[];
  instruments: Array<{ id: string; symbol: string; name: string }>;
  defaultInstrumentId: string | null | undefined;
  /** Ciclo completo: al terminar zonas con mejora, pasa solo a Coach². */
  autoHandoff: boolean;
  maxDrawdownSoftPct: number | null | undefined;
  profileId: string | null | undefined;
  profileHorizon: ProfileHorizon | null | undefined;
  profileRiskTolerance: RiskTolerance | null | undefined;
  onClearZoneSeed: (zoneId: string) => void;
  onReanalyzeWithCoach: (
    payload: LabReanalyzeRequest,
  ) => void | Promise<void>;
  onAutoHandoffStatus: (message: string) => void;
  onGoToCoach: () => void;
}

/** Resultado «Lab» de la pestaña de backtesting: tablero 3 zonas + jobs.
 * Extraído de `backtests-page.tsx` (feature-slicing F4.8) sin cambiar la
 * semántica de hooks/handlers del orquestador (cierre de ciclo incluido). */
export function BacktestResultFocusLab({
  isLabFocus,
  hasSeeds,
  zones,
  instruments,
  defaultInstrumentId,
  autoHandoff,
  maxDrawdownSoftPct,
  profileId,
  profileHorizon,
  profileRiskTolerance,
  onClearZoneSeed,
  onReanalyzeWithCoach,
  onAutoHandoffStatus,
  onGoToCoach,
}: Props) {
  return (
    <div
      className={
        isLabFocus
          ? "flex h-full min-h-0 flex-col gap-3 overflow-auto"
          : "hidden"
      }
      aria-hidden={!isLabFocus}
    >
      {!hasSeeds && (
        <div className="rounded-lg border border-dashed border-border bg-muted/10 px-3 py-2.5 text-sm">
          <p className="font-medium text-foreground">Lab sin semillas</p>
          <p className="mt-0.5 text-xs text-muted-foreground">
            Desde Coach: «Pasar al Lab» o «Abrir Lab · #1».
            Aquí optimizas parámetros; no escribe
            Finalistas.
          </p>
          <Button
            type="button"
            size="sm"
            variant="outline"
            className="mt-2"
            onClick={onGoToCoach}
          >
            Ir al Coach
          </Button>
        </div>
      )}
      <BacktestLabBoard
        zones={zones}
        instruments={instruments}
        defaultInstrumentId={defaultInstrumentId ?? undefined}
        onClearZoneSeed={onClearZoneSeed}
        onReanalyzeWithCoach={onReanalyzeWithCoach}
        autoHandoff={autoHandoff}
        maxDrawdownSoftPct={maxDrawdownSoftPct}
        profileId={profileId}
        profileHorizon={profileHorizon}
        profileRiskTolerance={profileRiskTolerance}
        onAutoHandoffStatus={onAutoHandoffStatus}
      />
    </div>
  );
}
