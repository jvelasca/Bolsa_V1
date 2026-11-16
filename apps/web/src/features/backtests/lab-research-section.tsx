/**
 * LAB · salud y experimentos dentro de `/backtests` — R5 (una sola puerta).
 *
 * El Asesor conserva solo un resumen y delega aquí. Este bloque reúne las dos
 * piezas que antes vivían exclusivamente en `/research` y que no se pueden
 * perder: la **salud/cobertura de métricas** (`LabHealthCard`, nivel 3) y el
 * **historial de experimentos con su detalle** (`LabTrialHistoryPanel` +
 * `LabTrialDetailPanel`).
 *
 * Estado en la URL (fuente única): `instrumentId`, `proposedBy`, `presetKey`,
 * `sort`, `page` y `trialId`. El deep-link del Asesor conserva el instrumento y
 * el experimento seleccionado.
 *
 * @see docs/engineering/plan-remediacion-laboratorio-2026-11-16.md §6 (R5)
 */

import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import type { ResearchTrialSort } from "@bolsa/shared";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { TechnicalDetail } from "@/components/technical-detail";
import { LabHealthCard } from "@/features/research/lab-health-card";
import { LabTrialDetailPanel } from "@/features/research/lab-trial-detail-panel";
import {
  LabTrialHistoryPanel,
  parseTrialPage,
  parseTrialSort,
  type LabHistoryFilterPatch,
} from "@/features/research/lab-trial-history-panel";

const PAGE_SIZE = 30;

export function LabResearchSection({ className }: { className?: string }) {
  const [searchParams, setSearchParams] = useSearchParams();

  const instrumentId = searchParams.get("instrumentId") ?? "";
  const proposedBy = searchParams.get("proposedBy") ?? "";
  const presetKey = searchParams.get("presetKey") ?? "";
  const sort = parseTrialSort(searchParams.get("sort"));
  const page = parseTrialPage(searchParams.get("page"));
  const selectedTrialId = searchParams.get("trialId");

  const labHealthQuery = useQuery({
    queryKey: ["research", "lab-health"],
    queryFn: api.getLabHealth,
  });
  const instrumentsQuery = useQuery({
    queryKey: ["instruments"],
    queryFn: api.getInstruments,
  });
  const trialsQuery = useQuery({
    queryKey: [
      "research",
      "trials",
      instrumentId,
      proposedBy,
      presetKey,
      sort,
      page,
    ],
    queryFn: () =>
      api.getResearchTrials({
        instrumentId: instrumentId || undefined,
        proposedBy: proposedBy || undefined,
        presetKey: presetKey || undefined,
        sort,
        sortDir: "desc",
        limit: PAGE_SIZE,
        offset: page * PAGE_SIZE,
      }),
  });
  const trialDetailQuery = useQuery({
    queryKey: ["research", "trial", selectedTrialId],
    queryFn: () => api.getResearchTrial(selectedTrialId!),
    enabled: Boolean(selectedTrialId),
  });

  const instruments = useMemo(
    () =>
      (instrumentsQuery.data?.data ?? []).map((instrument) => ({
        id: instrument.id,
        symbol: instrument.symbol,
      })),
    [instrumentsQuery.data],
  );
  const symbolById = useMemo(
    () =>
      new Map(
        instruments.map((instrument) => [instrument.id, instrument.symbol]),
      ),
    [instruments],
  );

  // Payload defensivo (`UNKNOWN ≠ 0`): una respuesta incompleta se declara ausente.
  const healthRaw = labHealthQuery.data?.data;
  const health =
    healthRaw && typeof healthRaw.coverage === "object" ? healthRaw : null;
  const trialsRaw = trialsQuery.data?.data;
  const trials = Array.isArray(trialsRaw) ? trialsRaw : [];
  const total = trialsQuery.data?.total ?? trials.length;

  /** Escribe un cambio de vista conservando el resto de la URL del LAB. */
  function patchParams(mutate: (params: URLSearchParams) => void) {
    const next = new URLSearchParams(searchParams);
    next.set("tab", "history");
    mutate(next);
    setSearchParams(next, { replace: true });
  }

  function patchHistoryFilters(patch: LabHistoryFilterPatch) {
    patchParams((params) => {
      // Cada filtro se escribe o se borra: vacío = sin filtro.
      for (const [key, value] of Object.entries({
        instrumentId: patch.instrumentId ?? instrumentId,
        proposedBy: patch.proposedBy ?? proposedBy,
        presetKey: patch.presetKey ?? presetKey,
      })) {
        if (value) params.set(key, value);
        else params.delete(key);
      }
      params.delete("page"); // cambiar un filtro vuelve a la primera página
    });
  }

  function changeSort(next: ResearchTrialSort) {
    patchParams((params) => {
      params.set("sort", next);
      params.delete("page");
    });
  }

  function changePage(next: number) {
    patchParams((params) => {
      if (next <= 0) params.delete("page");
      else params.set("page", String(next));
    });
  }

  function selectTrial(id: string) {
    patchParams((params) => {
      params.set("trialId", id);
    });
  }

  return (
    <section
      className={cn("space-y-3", className)}
      data-testid="lab-research-section"
      aria-label="Experimentos del Laboratorio"
    >
      <div>
        <h3 className="text-lg font-semibold tracking-tight">
          Experimentos del Laboratorio
        </h3>
        <p className="text-sm text-muted-foreground">
          Salud de métricas e historial de pruebas de investigación. Antes
          vivían solo en Asesor; ahora están junto a tus backtests.
        </p>
      </div>

      {labHealthQuery.isLoading && (
        <p className="text-sm text-muted-foreground">
          Cargando salud del laboratorio…
        </p>
      )}
      {labHealthQuery.isError && (
        <p className="text-sm text-destructive">
          No se pudo cargar la salud del laboratorio. Revisa la API e inténtalo
          de nuevo.
        </p>
      )}
      {health && (
        <TechnicalDetail testId="lab-research-health-technical">
          <LabHealthCard health={health} />
        </TechnicalDetail>
      )}

      <div className="grid gap-4 lg:grid-cols-5">
        <LabTrialHistoryPanel
          className="lg:col-span-3"
          instruments={instruments}
          filters={{
            instrumentId,
            proposedBy,
            presetKey,
            sort,
            page,
            pageSize: PAGE_SIZE,
          }}
          trials={trials}
          total={total}
          isLoading={trialsQuery.isLoading}
          isError={trialsQuery.isError}
          selectedTrialId={selectedTrialId}
          symbolById={symbolById}
          onFilterChange={patchHistoryFilters}
          onSortChange={changeSort}
          onPageChange={changePage}
          onSelectTrial={selectTrial}
        />
        <LabTrialDetailPanel
          className="lg:col-span-2"
          selectedTrialId={selectedTrialId}
          isLoading={trialDetailQuery.isLoading}
          selected={trialDetailQuery.data?.data}
        />
      </div>
    </section>
  );
}
