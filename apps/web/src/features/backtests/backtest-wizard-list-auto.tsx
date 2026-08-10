import {
  LIST_AUTO_BATCH_SIZE,
  listAutoBatchCount,
  listAutoBatchProgressLabel,
  listAutoOverCapWarning,
  listAutoProgressLabel,
  listAutoUniverseHint,
} from "@/features/backtests/backtest-list-auto";
import { BacktestListAutoBoardPanel } from "@/features/backtests/backtest-list-auto-board-panel";
import type { ListAutoBoardState } from "@/features/backtests/backtest-list-auto-board";
import type { AssistantPrefs } from "@/features/backtests/backtest-assistant-prefs";

interface BacktestWizardListAutoProps {
  assistantPrefs: AssistantPrefs;
  onPrefsChange: (next: AssistantPrefs) => void;
  listId: string;
  instrumentCount: number;
  skipWithFinalists: boolean;
  onSkipWithFinalistsChange: (next: boolean) => void;
  board: ListAutoBoardState | null;
  ui: { index: number; total: number; symbol: string } | null;
  selectedInstrumentId: string | null;
  onOpenInstrument: (id: string) => void;
  onPause: () => void;
  onResume: () => void;
  onStop: () => void;
  onForceRescanRemaining: () => void;
}

/** Panel «Lista AUTO · Play» del wizard (solo en modo lista). Jugador del ciclo
 * completo por valor + tablero de campaña. Extraído de `backtests-page.tsx`
 * (feature-slicing F4.8) sin cambiar la semántica de hooks/handlers del padre. */
export function BacktestWizardListAuto({
  assistantPrefs,
  onPrefsChange,
  listId,
  instrumentCount,
  skipWithFinalists,
  onSkipWithFinalistsChange,
  board,
  ui,
  selectedInstrumentId,
  onOpenInstrument,
  onPause,
  onResume,
  onStop,
  onForceRescanRemaining,
}: BacktestWizardListAutoProps) {
  const overManyBatches = instrumentCount > LIST_AUTO_BATCH_SIZE;
  const tanda = ui
    ? listAutoBatchProgressLabel({ index: ui.index, total: ui.total })
    : "";
  return (
    <div className="space-y-1.5 rounded-md border border-border/60 bg-muted/20 px-2.5 py-2">
      <p className="text-[11px] font-medium text-foreground">Lista AUTO · Play</p>
      <p className="text-[10px] leading-snug text-muted-foreground">
        {listAutoUniverseHint()}
      </p>
      {!assistantPrefs.fullCycleOnPlay ? (
        <p className="text-[10px] leading-snug text-amber-700 dark:text-amber-400">
          Activa «Play: ciclo completo» en el Asistente para lanzar Lista AUTO.
        </p>
      ) : !listId ? (
        <p className="text-[10px] leading-snug text-muted-foreground">
          Elige una lista arriba y pulsa Play en el Asistente.
        </p>
      ) : (
        <>
          <label className="flex items-start gap-2 text-[10px] leading-snug text-muted-foreground">
            <input
              type="checkbox"
              className="mt-0.5"
              checked={skipWithFinalists}
              onChange={(e) => onSkipWithFinalistsChange(e.target.checked)}
            />
            <span>
              Solo sin Finalistas (excluye tickers que ya tienen TOP; útil en S&P
              / listas grandes).
            </span>
          </label>
          <label className="flex items-start gap-2 text-[10px] leading-snug text-muted-foreground">
            <input
              type="checkbox"
              className="mt-0.5"
              checked={assistantPrefs.listAutoSkipOverCapConfirm}
              onChange={(e) =>
                onPrefsChange({
                  ...assistantPrefs,
                  listAutoSkipOverCapConfirm: e.target.checked,
                })
              }
            />
            <span>
              No preguntar al superar ~{LIST_AUTO_BATCH_SIZE} (tandas encadenadas;
              N &gt; 200 siempre confirma).
            </span>
          </label>
          <p className="text-[10px] leading-snug text-muted-foreground">
            {instrumentCount} valor{instrumentCount === 1 ? "" : "es"} en cola
            {overManyBatches
              ? ` · ${listAutoBatchCount(instrumentCount)} tandas`
              : ""}
            {skipWithFinalists ? " (antes del filtro)" : ""}. Pulsa Play — no
            elijas estrategia.
          </p>
          {(() => {
            const warn = listAutoOverCapWarning(instrumentCount);
            return warn ? (
              <p className="text-[10px] leading-snug text-amber-700 dark:text-amber-400">
                {warn}
              </p>
            ) : null;
          })()}
          <p className="text-[10px] leading-snug text-muted-foreground">
            Reanalizar aquí (LAB) no cambia Trading: el mandato solo cambia si
            aceptas una propuesta CORE-R en Monitor (o lo cambias a mano).
          </p>
        </>
      )}
      {board ? (
        <BacktestListAutoBoardPanel
          board={board}
          compact
          selectedInstrumentId={selectedInstrumentId}
          onSelectInstrument={onOpenInstrument}
          campaignControls={
            !board.done && !board.aborted
              ? {
                  canPause: !board.paused,
                  canResume:
                    board.paused && !board.rows.some((r) => r.phase === "running"),
                  canStop: true,
                  onPause,
                  onResume,
                  onStop,
                  onForceRescanRemaining,
                }
              : undefined
          }
        />
      ) : ui ? (
        <p
          className="text-[11px] font-medium text-foreground"
          aria-live="polite"
        >
          {`${listAutoProgressLabel(ui)}${tanda ? ` · ${tanda}` : ""} en curso… ↻ cancela.`}
        </p>
      ) : null}
    </div>
  );
}
