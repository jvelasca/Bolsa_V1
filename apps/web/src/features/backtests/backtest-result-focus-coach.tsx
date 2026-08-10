import type { BacktestEquityPointDto, ChartTimeframe } from "@bolsa/shared";
import { BacktestExploreRanking } from "@/features/backtests/backtest-explore-panel";
import type {
  ExplorePresetRow,
  ExploreSortKey,
} from "@/features/backtests/backtest-explore-value";

interface Props {
  /** Result focus activo (`resultFocus === "coach"`). Gobierna clase/aria y avisos «Sin lote». */
  isCoachFocus: boolean;
  /** Hay lote de exploración (estrellas ★ / dual-audit). */
  hasExploreRows: boolean;
  /** Lista AUTO en marcha (muestra aviso cuando no hay lote). */
  hasListAutoBoard: boolean;
  /** Renderiza el panel del Coach (lote presente + focus coach o lista AUTO en ciclo post-lab). */
  coachPanelVisible: boolean;
  /** initial = Universo; post_lab = tras Reanalizar con Coach. */
  coachPass: "initial" | "post_lab";
  rows: ExplorePresetRow[];
  instrumentId: string | null;
  symbol: string;
  timeframe: ChartTimeframe | string;
  periodLabel?: string;
  sort: ExploreSortKey;
  onSortChange: (sort: ExploreSortKey) => void;
  selectedRunId?: string | null;
  onSelectRun: (runId: string) => void;
  onOptimizeCandidate: (row: ExplorePresetRow) => void;
  onOptimizeSemifinal: (
    candidates: Array<{
      row: ExplorePresetRow;
      stars?: number;
      starsCapped?: boolean;
      rank?: number;
    }>,
  ) => void;
  barLimit?: number | null;
  progress?: { done: number; total: number };
  running?: boolean;
  equityByRunId?: Record<string, BacktestEquityPointDto[] | undefined>;
  futureWeight?: number;
  autoSaveFinalists?: boolean;
  onAutoSaveStatus?: (message: string) => void;
  autoAckOnCycle?: boolean;
  pauseIfAckNeeded?: boolean;
  onAwaitingAckChange?: (awaiting: boolean) => void;
  requireAckBeforeLab?: boolean;
  autoSaveSemifinal?: boolean;
  cycleCoach1Active?: boolean;
  labImprovedCountHint?: number;
  hasExistingTopForSave?: boolean;
  onCoachGateChange?: (gate: {
    needsAck: boolean;
    ack: boolean;
    postLab: boolean;
    canSaveTop: boolean;
  }) => void;
  freshnessInputFingerprint?: string | null;
  llmNarrate?: boolean;
  experimentAsOf?: string | null;
}

/** Resultado «Coach» de la pestaña de backtesting: estrellas ★ + dual-audit del lote.
 * Extraído de `backtests-page.tsx` (feature-slicing F4.8). Los callbacks acoplados
 * de ciclo (`onAutoSaveStatus`→`settleFullCycle`, `onSelectRun`, `onAwaitingAckChange`,
 * `onCoachGateChange`, `onOptimizeCandidate`/`onOptimizeSemifinal`) permanecen en el
 * orquestador como props (Diseño B), de modo que la semántica del ciclo no se mueve. */
export function BacktestResultFocusCoach({
  isCoachFocus,
  hasExploreRows,
  hasListAutoBoard,
  coachPanelVisible,
  coachPass,
  rows,
  instrumentId,
  symbol,
  timeframe,
  periodLabel,
  sort,
  onSortChange,
  selectedRunId,
  onSelectRun,
  onOptimizeCandidate,
  onOptimizeSemifinal,
  barLimit,
  progress,
  running,
  equityByRunId,
  futureWeight,
  autoSaveFinalists,
  onAutoSaveStatus,
  autoAckOnCycle,
  pauseIfAckNeeded,
  onAwaitingAckChange,
  requireAckBeforeLab,
  autoSaveSemifinal,
  cycleCoach1Active,
  labImprovedCountHint,
  hasExistingTopForSave,
  onCoachGateChange,
  freshnessInputFingerprint,
  llmNarrate,
  experimentAsOf,
}: Props) {
  return (
    <>
      {isCoachFocus && !hasExploreRows && !hasListAutoBoard && (
        <p className="text-sm text-muted-foreground">
          Sin lote de coach aún. Pulsa Play en Universo (o Probar + coach) para
          rellenarlo.
        </p>
      )}
      {isCoachFocus && !hasExploreRows && hasListAutoBoard && (
        <p className="text-sm text-muted-foreground">
          Lista AUTO en marcha. El Coach del valor actual aparece aquí al
          terminar su Universo; el tablero completo está en «Lista AUTO».
        </p>
      )}
      {coachPanelVisible && (
        <div
          className={isCoachFocus ? "h-full min-h-0 overflow-auto" : "hidden"}
          aria-hidden={!isCoachFocus}
        >
          <BacktestExploreRanking
            rows={rows}
            instrumentId={instrumentId}
            coachPass={coachPass}
            symbol={symbol}
            timeframe={timeframe}
            periodLabel={periodLabel}
            sort={sort}
            onSortChange={onSortChange}
            selectedRunId={selectedRunId}
            onSelectRun={onSelectRun}
            onOptimizeCandidate={onOptimizeCandidate}
            onOptimizeSemifinal={onOptimizeSemifinal}
            barLimit={barLimit}
            futureWeight={futureWeight}
            llmNarrate={llmNarrate}
            freshnessInputFingerprint={freshnessInputFingerprint}
            autoSaveFinalists={autoSaveFinalists}
            hasExistingTopForSave={hasExistingTopForSave}
            experimentAsOf={experimentAsOf}
            autoSaveSemifinal={autoSaveSemifinal}
            cycleCoach1Active={cycleCoach1Active}
            autoAckOnCycle={autoAckOnCycle}
            pauseIfAckNeeded={pauseIfAckNeeded}
            requireAckBeforeLab={requireAckBeforeLab}
            labImprovedCountHint={labImprovedCountHint}
            onAwaitingAckChange={onAwaitingAckChange}
            onCoachGateChange={onCoachGateChange}
            onAutoSaveStatus={onAutoSaveStatus}
            progress={progress}
            running={running}
            equityByRunId={equityByRunId}
          />
        </div>
      )}
    </>
  );
}
