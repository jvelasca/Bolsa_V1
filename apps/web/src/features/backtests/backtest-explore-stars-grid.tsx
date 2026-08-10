/**
 * Grid de candidatas ★ (TOP-3 a futuro) del panel Coach.
 *
 * Presenta las recomendaciones del coach en tarjetas (rank, label, estrellas,
 * retorno total/reciente/vs B&H/DD, tercios/fallback/calidad, motivo) con acceso
 * a detalle y al Lab. No tiene lógica de ciclo: el orquestador pasa los datos
 * (recommendations + starCeiling + postLab/running) y los callbacks-closure
 * (onSelectRun, onOptimizeCandidate, onOptimizeSemifinal). Extraído de
 * `backtest-explore-panel.tsx` (feature-slicing M5, frente backtest-explore, E.5).
 */

import { formatPct } from '@/features/charts/chart-utils';
import {
  isOptimizableStrategy,
  optimizeFamilyProxyNote,
} from '@/features/backtests/backtest-optimize-seed';
import { BacktestFutureStars } from '@/features/backtests/backtest-future-stars';
import type { TechnicalRecommendation } from '@/features/backtests/backtest-deep-coach';
import type { ExplorePresetRow } from '@/features/backtests/backtest-explore-value';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

interface Props {
  recommendations: TechnicalRecommendation[];
  starCeiling: number;
  postLab: boolean;
  running?: boolean;
  onSelectRun: (runId: string) => void;
  onOptimizeCandidate?: (row: ExplorePresetRow) => void;
  onOptimizeSemifinal?: (
    candidates: Array<{
      row: ExplorePresetRow;
      stars?: number;
      starsCapped?: boolean;
      rank?: number;
    }>,
  ) => void;
}

export function BacktestExploreStarsGrid({
  recommendations,
  starCeiling,
  postLab,
  running,
  onSelectRun,
  onOptimizeCandidate,
  onOptimizeSemifinal,
}: Props) {
  const firstLabRec = recommendations.find((r) =>
    isOptimizableStrategy(r.row.strategyType),
  );
  const labRecCount = recommendations.filter((r) =>
    isOptimizableStrategy(r.row.strategyType),
  ).length;

  return recommendations.length > 0 ? (
    <div className="space-y-2">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <p className="text-[11px] font-medium text-foreground">Candidatas ★ (1–5)</p>
          <p className="text-[10px] text-muted-foreground">
            Orden por tramo reciente · techo ★{starCeiling}
            {starCeiling <= 3 ? ' (solo in-sample)' : ' (lab)'}.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          {onOptimizeSemifinal && labRecCount > 0 && !postLab && (
            <Button
              type="button"
              size="sm"
              className="h-7 text-[11px]"
              disabled={running}
              onClick={() =>
                onOptimizeSemifinal(
                  recommendations.map((r) => ({
                    row: r.row,
                    stars: r.stars,
                    starsCapped: r.starsCapped,
                    rank: r.rank,
                  })),
                )
              }
              title={`Pasa hasta ${labRecCount} candidatas al Lab (3 columnas). Encola jobs hold-out/WF y deja config editable por zona.`}
            >
              {labRecCount === 1 ? 'Pasar al Lab' : `Pasar las ${labRecCount} al Lab`}
            </Button>
          )}
          {onOptimizeCandidate && firstLabRec && !postLab && (
            <Button
              type="button"
              size="sm"
              variant="outline"
              className="h-7 text-[11px]"
              disabled={running}
              onClick={() => onOptimizeCandidate(firstLabRec.row)}
              title="Abre Lab con la #1 ★ precargada. Tú lanzas la búsqueda allí."
            >
              Abrir Lab · #1
            </Button>
          )}
        </div>
      </div>

      <div className="grid gap-2 sm:grid-cols-3">
        {recommendations.map((rec) => {
          const proxy = optimizeFamilyProxyNote(rec.row.strategyType);
          const canLab = isOptimizableStrategy(rec.row.strategyType);
          return (
            <div
              key={rec.row.strategyDefinitionId ?? `${rec.row.strategyType}-${rec.rank}`}
              className={cn(
                'flex flex-col gap-1.5 rounded-lg border bg-background/80 px-2.5 py-2',
                rec.rank === 1
                  ? 'border-amber-400/50 ring-1 ring-amber-400/30'
                  : 'border-border/60',
              )}
            >
              <div className="flex items-start justify-between gap-1">
                <div className="min-w-0">
                  <p className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
                    #{rec.rank}
                  </p>
                  <p className="text-xs font-semibold leading-snug text-foreground">
                    {rec.row.label}
                  </p>
                </div>
                <BacktestFutureStars stars={rec.stars} capped={rec.starsCapped} size="sm" />
              </div>
              <p className="text-[10px] tabular-nums text-muted-foreground">
                {rec.row.totalReturnPct != null ? `Total ${formatPct(rec.row.totalReturnPct)}` : '—'}
                {rec.lateReturnPct != null
                  ? ` · reciente ${rec.lateReturnPct >= 0 ? '+' : ''}${rec.lateReturnPct.toFixed(1)}%`
                  : ''}
                {rec.row.excessReturnPct != null
                  ? ` · vs B&H ${formatPct(rec.row.excessReturnPct)}`
                  : ''}
                {rec.row.maxDrawdownPct != null
                  ? ` · DD ${formatPct(rec.row.maxDrawdownPct)}`
                  : ''}
              </p>
              {(rec.earlyReturnPct != null ||
                rec.midReturnPct != null ||
                rec.usedSoftFallback ||
                rec.qualityFlagged) && (
                <p className="text-[10px] tabular-nums text-muted-foreground/90">
                  {rec.earlyReturnPct != null && rec.midReturnPct != null
                    ? `Tercios ${rec.earlyReturnPct.toFixed(0)}/${rec.midReturnPct.toFixed(0)}/${(rec.lateReturnPct ?? 0).toFixed(0)}%`
                    : null}
                  {rec.usedSoftFallback ? ' · sin tercios (fallback)' : ''}
                  {rec.qualityFlagged ? ' · suelo calidad' : ''}
                </p>
              )}
              <p className="line-clamp-2 text-[10px] leading-snug text-muted-foreground">
                {rec.reasons[1] ?? rec.reasons[0]}
              </p>
              <div className="mt-auto flex flex-wrap gap-1 pt-0.5">
                {rec.row.runId && (
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    className="h-7 flex-1 text-[11px]"
                    onClick={() => onSelectRun(rec.row.runId!)}
                    title="Ver detalle / gráfico de esta prueba"
                  >
                    Ver
                  </Button>
                )}
                {onOptimizeCandidate && canLab && !postLab && (
                  <Button
                    type="button"
                    size="sm"
                    variant={rec.rank === 1 ? 'default' : 'outline'}
                    className="h-7 flex-1 text-[11px]"
                    title={
                      proxy
                        ? `${proxy} Abre Lab (tú lanzas).`
                        : 'Abre Lab con esta candidata (tú lanzas).'
                    }
                    onClick={() => onOptimizeCandidate(rec.row)}
                  >
                    {proxy ? 'Lab (aprox.)' : 'Lab'}
                  </Button>
                )}
                {onOptimizeCandidate && !canLab && (
                  <span className="px-1 text-[10px] text-muted-foreground" title="Sin familia de lab">
                    Sin lab
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>

      <p className="text-[10px] leading-snug text-muted-foreground">
        <strong className="font-medium text-foreground/80">Lab</strong> = abre el laboratorio
        con la candidata. <strong className="font-medium text-foreground/80">Encolar</strong> =
        lanza búsquedas en segundo plano. Guardar TOP-3 ≠ optimizar.
      </p>
    </div>
  ) : (
    <p className="text-xs text-muted-foreground">
      Aún no hay candidatas ★. Espera a que termine la batería o lanza «Probar + coach».
    </p>
  );
}
