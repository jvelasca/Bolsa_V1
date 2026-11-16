/**
 * Asesor → Laboratorio · historial de experimentos — slice A3.
 *
 * Tabla de experimentos con sus filtros (`instrumentId`, `proposedBy`, `presetKey`,
 * `sort`) y la paginación. El estado NO se lee de la URL aquí: llega por props y
 * cada interacción avisa al contenedor, que es el único que escribe la query string.
 *
 * Sin cambio de comportamiento: mismo marcado, mismos rótulos y mismos `testId`.
 */

import { Link } from "react-router-dom";
import type { ResearchTrialDto, ResearchTrialSort } from "@bolsa/shared";
import { formatPct } from "@/features/charts/chart-utils";
import { summarizeLabEvidenceFromTrial } from "@/features/research/research-lab-evidence";
import { Button } from "@/components/ui/button";
import { TechnicalDetail } from "@/components/technical-detail";
import { absentDataLabel, formatOrAbsent } from "@/components/absent-data";
import { cn } from "@/lib/utils";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
} from "@/components/ui/card";
import { formatShortDate, SectionTitle } from "@/features/research/asesor-ui";

export type LabHistoryFilterPatch = {
  instrumentId?: string;
  proposedBy?: string;
  presetKey?: string;
};

/** Estado de filtros/paginación que el contenedor lee de la URL. */
export type LabHistoryFilters = {
  instrumentId: string;
  proposedBy: string;
  presetKey: string;
  sort: ResearchTrialSort;
  page: number;
  pageSize: number;
};

/**
 * Sorts aceptados por la API de experimentos. El estado vive en la URL para que
 * atrás/adelante y un enlace compartido reconstruyan la misma vista.
 */
const TRIAL_SORTS: readonly ResearchTrialSort[] = [
  "created_at",
  "sharpe",
  "pnl",
  "commission",
  "k_contribution",
];

export function parseTrialSort(raw: string | null): ResearchTrialSort {
  return TRIAL_SORTS.includes(raw as ResearchTrialSort)
    ? (raw as ResearchTrialSort)
    : "created_at";
}

export function parseTrialPage(raw: string | null): number {
  const n = Number.parseInt(raw ?? "", 10);
  return Number.isFinite(n) && n > 0 ? n : 0;
}

type Props = {
  /** Instrumentos disponibles para el filtro (ya cargados por el contenedor). */
  instruments: ReadonlyArray<{ id: string; symbol: string }>;
  filters: LabHistoryFilters;
  trials: readonly ResearchTrialDto[];
  total: number;
  isLoading: boolean;
  isError: boolean;
  selectedTrialId: string | null;
  symbolById: ReadonlyMap<string, string>;
  onFilterChange: (patch: LabHistoryFilterPatch) => void;
  onSortChange: (sort: ResearchTrialSort) => void;
  onPageChange: (page: number) => void;
  onSelectTrial: (id: string) => void;
  className?: string;
};

function metricNum(
  m: Record<string, number | string | null>,
  key: string,
): number | null {
  const v = m[key];
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}

export function LabTrialHistoryPanel({
  instruments,
  filters,
  trials,
  total,
  isLoading,
  isError,
  selectedTrialId,
  symbolById,
  onFilterChange,
  onSortChange,
  onPageChange,
  onSelectTrial,
  className,
}: Props) {
  const { instrumentId, proposedBy, presetKey, sort, page, pageSize } = filters;

  return (
    <Card className={cn(className)}>
      <CardHeader className="pb-3">
        <SectionTitle>Historial de experimentos</SectionTitle>
        <CardDescription>
          Cada fila es un experimento de investigación
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex flex-wrap gap-2">
          <select
            className="h-9 rounded-md border border-input bg-background px-2 text-sm"
            value={instrumentId}
            onChange={(e) => {
              onFilterChange({ instrumentId: e.target.value });
            }}
          >
            <option value="">Todos los instrumentos</option>
            {instruments.map((inst) => (
              <option key={inst.id} value={inst.id}>
                {inst.symbol}
              </option>
            ))}
          </select>
          <select
            className="h-9 rounded-md border border-input bg-background px-2 text-sm"
            value={sort}
            onChange={(e) => onSortChange(e.target.value as ResearchTrialSort)}
          >
            <option value="created_at">Fecha</option>
            <option value="sharpe">Calidad</option>
            <option value="pnl">Resultado (PnL)</option>
            <option value="commission">Comisión</option>
            <option value="k_contribution">Pruebas</option>
          </select>
        </div>
        <TechnicalDetail
          className="text-xs"
          testId="research-history-technical-filters"
        >
          <div className="flex flex-wrap gap-2">
            <select
              className="h-9 rounded-md border border-input bg-background px-2 text-sm"
              value={proposedBy}
              onChange={(e) => {
                onFilterChange({ proposedBy: e.target.value });
              }}
            >
              <option value="">Cualquier origen</option>
              <option value="human">human</option>
              <option value="grid">grid</option>
              <option value="optuna">optuna</option>
              <option value="ai">ai</option>
              <option value="system">system</option>
            </select>
            <input
              className="h-9 w-40 rounded-md border border-input bg-background px-2 text-sm"
              placeholder="configuración"
              value={presetKey}
              onChange={(e) => {
                onFilterChange({ presetKey: e.target.value });
              }}
            />
          </div>
        </TechnicalDetail>

        {isLoading && (
          <p className="text-sm text-muted-foreground">
            Cargando experimentos…
          </p>
        )}
        {isError && (
          <p className="text-sm text-destructive">
            No se pudo cargar el historial. Revisa la API e inténtalo de nuevo.
          </p>
        )}

        <div className="max-h-[28rem] overflow-auto rounded-md border border-border">
          <table className="w-full text-left text-xs">
            <thead className="sticky top-0 bg-muted/80 text-muted-foreground">
              <tr>
                <th className="px-2 py-2 font-medium">Fecha</th>
                <th className="px-2 py-2 font-medium">Valor</th>
                <th className="px-2 py-2 font-medium">Configuración</th>
                <th className="px-2 py-2 font-medium">Propuesto por</th>
                <th className="px-2 py-2 font-medium">Resultado</th>
                <th className="px-2 py-2 font-medium">Calidad</th>
                <th className="px-2 py-2 font-medium">Evidencia</th>
                <th className="px-2 py-2 font-medium">Pruebas</th>
              </tr>
            </thead>
            <tbody>
              {trials.map((trial) => {
                const pnl = metricNum(trial.isMetrics, "totalReturnPct");
                const sharpe = metricNum(trial.isMetrics, "sharpeRatio");
                const active = trial.id === selectedTrialId;
                const labEvidence = summarizeLabEvidenceFromTrial(trial);
                return (
                  <tr
                    key={trial.id}
                    className={cn(
                      "cursor-pointer border-t border-border/60 hover:bg-accent/40",
                      active && "bg-accent/60",
                    )}
                    onClick={() => onSelectTrial(trial.id)}
                  >
                    <td className="px-2 py-1.5 whitespace-nowrap">
                      {formatShortDate(trial.createdAt)}
                    </td>
                    <td className="px-2 py-1.5 font-medium">
                      {symbolById.get(trial.instrumentId) ??
                        trial.instrumentId.slice(0, 6)}
                    </td>
                    <td className="px-2 py-1.5">
                      {formatOrAbsent(trial.presetKey, (v) => v)}
                    </td>
                    <td className="px-2 py-1.5">{trial.proposedBy}</td>
                    <td className="px-2 py-1.5 tabular-nums">
                      {formatOrAbsent(pnl, formatPct)}
                    </td>
                    <td className="px-2 py-1.5 tabular-nums">
                      {formatOrAbsent(sharpe, (v) => v.toFixed(2))}
                    </td>
                    <td
                      className="max-w-[14rem] truncate px-2 py-1.5"
                      title={labEvidence.hasLab ? labEvidence.title : undefined}
                    >
                      {labEvidence.hasLab
                        ? labEvidence.modeLabel
                        : absentDataLabel()}
                    </td>
                    <td className="px-2 py-1.5 tabular-nums">
                      {trial.kContribution}
                    </td>
                  </tr>
                );
              })}
              {trials.length === 0 && !isLoading && !isError && (
                <tr>
                  <td
                    colSpan={8}
                    className="px-2 py-6 text-center text-muted-foreground"
                  >
                    <p>No hay experimentos con estos filtros.</p>
                    <Link
                      to="/backtests?tab=run"
                      className="mt-2 inline-block text-xs font-medium text-primary hover:underline"
                    >
                      Ir a Probar estrategia
                    </Link>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        <div className="flex items-center justify-between gap-2 text-xs text-muted-foreground">
          <span>
            {total} experimento{total === 1 ? "" : "s"} · página {page + 1}
          </span>
          <div className="flex gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={page === 0}
              onClick={() => onPageChange(page - 1)}
            >
              Anterior
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={(page + 1) * pageSize >= total}
              onClick={() => onPageChange(page + 1)}
            >
              Siguiente
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
