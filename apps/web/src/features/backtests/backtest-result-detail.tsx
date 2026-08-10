import { FileJson, LineChart, SlidersHorizontal, Table } from "lucide-react";
import { PAPER_PATH_LAB } from "@/features/settings/paper-paths-copy";
import { ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { DiaDVerifyHost } from "@/features/backtests/dia-d-verify-host";
import {
  BacktestInstrumentPreview,
  BacktestResultEmpty,
} from "@/features/backtests/backtest-instrument-preview";
import { BacktestResultView } from "@/features/backtests/backtest-result-view";
import {
  type BacktestEquityPointDto,
  type BacktestRunDetailDto,
  type BacktestTradeDto,
  type ChartTimeframe,
  type DrawingReplayMarkerDto,
  type OhlcvBarDto,
  type PaperLabEvidenceSnapshot,
  type ResearchTrialDto,
} from "@bolsa/shared";
import type { FinalistHudBadge } from "@/features/backtests/instrument-top-match";
import type { PeriodPreset } from "@/features/backtests/backtest-period";

interface ManifestSummary {
  engine: string;
  dataVersion: string | null | undefined;
  barCount: number | null | undefined;
  metricsHash: string;
}

interface BacktestResultDetailProps {
  diaDVerifyActive: boolean;
  detail: BacktestRunDetailDto | undefined;
  instrumentId: string;
  selectedId: string | null;
  detailFetching: boolean;
  detailHasData: boolean;
  detailDataInstrumentId: string | undefined;
  detailErrorActive: boolean;
  detailError: unknown;
  instrumentSymbol: string | null;
  instrumentName: string | undefined;
  timeframe: ChartTimeframe;
  periodPreset: PeriodPreset;
  customDateFrom: string;
  customDateTo: string;
  diaD: string | null | undefined;
  preferOpenAnalysis: boolean;
  bars: OhlcvBarDto[] | undefined;
  barsLoading: boolean;
  barsError: boolean;
  equityCurve: BacktestEquityPointDto[];
  focusTimestamp: string | null;
  focusedTrade: BacktestTradeDto | null;
  onSelectTrade: (timestamp: string) => void;
  onJumpToTrade: (timestamp: string) => void;
  displayTrialId: string | null | undefined;
  displayMetrics: Record<string, number | string | null> | null | undefined;
  linkedTrial: ResearchTrialDto | null | undefined;
  drawingMarkers: DrawingReplayMarkerDto[];
  finalistBadge: FinalistHudBadge | null;
  hasRankingRows: boolean;
  onBackToRanking: () => void;
  onStartOptimize: () => void;
  onExportJson: () => void;
  onExportTrades: () => void;
  onExportEquity: () => void;
  deployingPaper: boolean;
  deployError: unknown;
  onDeployPaper: (payload: {
    labEvidence: PaperLabEvidenceSnapshot | null | undefined;
  }) => void;
  manifestSummary: ManifestSummary | null;
}

/** Resultado «detalle» de la pestaña de backtesting: verificación D→hoy,
 * preview/empty/loading/error y la vista de detalle del run (acciones + footer).
 * Extraído de `backtests-page.tsx` (feature-slicing F4.8) sin cambiar la
 * semántica de hooks/handlers del padre. */
export function BacktestResultDetail({
  diaDVerifyActive,
  detail,
  instrumentId,
  selectedId,
  detailFetching,
  detailHasData,
  detailDataInstrumentId,
  detailErrorActive,
  detailError,
  instrumentSymbol,
  instrumentName,
  timeframe,
  periodPreset,
  customDateFrom,
  customDateTo,
  diaD,
  preferOpenAnalysis,
  bars,
  barsLoading,
  barsError,
  equityCurve,
  focusTimestamp,
  focusedTrade,
  onSelectTrade,
  onJumpToTrade,
  displayTrialId,
  displayMetrics,
  linkedTrial,
  drawingMarkers,
  finalistBadge,
  hasRankingRows,
  onBackToRanking,
  onStartOptimize,
  onExportJson,
  onExportTrades,
  onExportEquity,
  deployingPaper,
  deployError,
  onDeployPaper,
  manifestSummary,
}: BacktestResultDetailProps) {
  const detailLoading =
    Boolean(selectedId) &&
    detailFetching &&
    (!detailHasData || detailDataInstrumentId === instrumentId);
  return (
    <>
      {diaDVerifyActive && (
        <div className="flex min-h-0 flex-1 flex-col">
          <DiaDVerifyHost />
        </div>
      )}

      {!diaDVerifyActive && !detail && instrumentId && !detailLoading && (
        <div className="flex min-h-0 flex-1 flex-col">
          <BacktestInstrumentPreview
            key={instrumentId}
            instrumentId={instrumentId}
            symbol={instrumentSymbol ?? "Valor"}
            name={instrumentName}
            timeframe={timeframe}
            periodPreset={periodPreset}
            customDateFrom={customDateFrom}
            customDateTo={customDateTo}
            diaD={diaD ?? undefined}
          />
        </div>
      )}

      {!diaDVerifyActive && !detail && !instrumentId && <BacktestResultEmpty />}

      {!diaDVerifyActive && !detail && detailLoading && (
        <p className="text-sm text-muted-foreground">Cargando resultado…</p>
      )}

      {!diaDVerifyActive && !detail && selectedId && detailErrorActive && (
        <p className="text-sm text-destructive">
          {detailErrorMessage(detailError)}
        </p>
      )}

      {!diaDVerifyActive && detail && (
        <div className="flex min-h-0 flex-1 flex-col">
          <BacktestResultView
            fillHeight
            detail={detail}
            preferOpenAnalysis={preferOpenAnalysis}
            bars={bars}
            barsLoading={barsLoading}
            barsError={barsError}
            equityCurve={equityCurve}
            focusTimestamp={focusTimestamp}
            focusedTrade={focusedTrade}
            onSelectTrade={onSelectTrade}
            onJumpToTrade={onJumpToTrade}
            displayTrialId={displayTrialId}
            displayMetrics={displayMetrics}
            linkedTrial={linkedTrial}
            drawingMarkers={drawingMarkers}
            finalistBadge={finalistBadge}
            actions={
              <>
                {hasRankingRows && (
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={onBackToRanking}
                  >
                    Volver al ranking
                  </Button>
                )}
                <Button
                  type="button"
                  variant="default"
                  size="sm"
                  className="gap-1.5"
                  title="Abre Lab con este valor, esta estrategia y estos resultados como punto de partida."
                  aria-label="Optimizar a partir de esta prueba"
                  onClick={onStartOptimize}
                >
                  <SlidersHorizontal className="h-4 w-4" />
                  Lab
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="h-8 w-8 p-0"
                  title="Exportar resultado completo (JSON)"
                  aria-label="Exportar JSON"
                  onClick={onExportJson}
                >
                  <FileJson className="h-4 w-4" />
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="h-8 w-8 p-0"
                  title="Exportar operaciones (CSV)"
                  aria-label="Exportar trades CSV"
                  disabled={detail.trades.length === 0}
                  onClick={onExportTrades}
                >
                  <Table className="h-4 w-4" />
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="h-8 w-8 p-0"
                  title="Exportar evolución del patrimonio (CSV)"
                  aria-label="Exportar equity CSV"
                  disabled={equityCurve.length === 0}
                  onClick={onExportEquity}
                >
                  <LineChart className="h-4 w-4" />
                </Button>
              </>
            }
            deployingPaper={deployingPaper}
            onDeployPaper={onDeployPaper}
            footerNote={
              <>
                {deployError && (
                  <p className="text-sm text-destructive">
                    {deployErrorMessage(deployError)}
                  </p>
                )}
                {manifestSummary && (
                  <div className="rounded-lg border border-border bg-muted/30 p-3 text-xs">
                    <p className="font-medium text-foreground">
                      Manifiesto de la prueba
                    </p>
                    <ul className="mt-1 space-y-0.5 text-muted-foreground">
                      <li>Motor: {manifestSummary.engine}</li>
                      <li>
                        Versión datos: {manifestSummary.dataVersion ?? "—"}
                      </li>
                      <li>
                        Barras: {manifestSummary.barCount ?? detail.barCount}
                      </li>
                      <li>Hash métricas: {manifestSummary.metricsHash}</li>
                    </ul>
                  </div>
                )}
                <p className="text-xs text-muted-foreground">
                  El checklist Lab habilita «{PAPER_PATH_LAB.cta}» (
                  {PAPER_PATH_LAB.shortTitle}; distinto del Paper automático del
                  rastreador). Cuenta simulada desde este run; sin
                  auto-ejecución.
                </p>
              </>
            }
          />
        </div>
      )}
    </>
  );
}

function deployErrorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "No se pudo crear la cuenta paper";
}

function detailErrorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "No se pudo cargar el detalle de esta prueba.";
}
