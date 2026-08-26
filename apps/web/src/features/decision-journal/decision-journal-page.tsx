/**
 * Decision Journal 2.0 — Tesis (vista) + Historial técnico (ADR-029).
 * Solo lectura. No muta TradePlan ni journal.
 */

import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { RefreshCw } from "lucide-react";
import type { DecisionJournalStudyViewV1 } from "@bolsa/shared";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { useMediaQuery } from "@/lib/use-media-query";
import { useActiveAccount } from "@/features/accounts/use-active-account";
import { JournalTimeline } from "@/features/decision-journal/journal-timeline";
import {
  DEFAULT_JOURNAL_STUDY_FILTERS,
  JournalStudiesFilters,
  type JournalStudyFilters,
} from "@/features/decision-journal/journal-studies-filters";
import { JournalStudiesTable } from "@/features/decision-journal/journal-studies-table";
import {
  DecisionFichaPanel,
  JournalStudyDetailCollapsedRail,
} from "@/features/decision-journal/decision-ficha-panel";
import { JournalEvolutionPanel } from "@/features/decision-journal/journal-evolution-panel";
import {
  JournalStudiesSplitLayout,
  loadJournalStudiesSplitPrefs,
  persistJournalStudiesSplitPrefs,
} from "@/features/decision-journal/journal-studies-split-layout";

type JournalTab = "tesis" | "evolucion" | "historial";

const STUDIES_PAGE_LIMIT = 200;

export function DecisionJournalPage() {
  const { effectiveAccountId } = useActiveAccount();
  const [searchParams] = useSearchParams();
  const isWide = useMediaQuery("(min-width: 1024px)");
  const splitPrefs = useMemo(() => loadJournalStudiesSplitPrefs(), []);
  const initialTab = searchParams.get("tab");
  const [tab, setTab] = useState<JournalTab>(
    initialTab === "evolucion" || initialTab === "historial"
      ? initialTab
      : "tesis",
  );
  const [filters, setFilters] = useState<JournalStudyFilters>(
    DEFAULT_JOURNAL_STUDY_FILTERS,
  );
  const [debouncedQ, setDebouncedQ] = useState("");
  const [selected, setSelected] = useState<DecisionJournalStudyViewV1 | null>(
    null,
  );
  const [fichaCollapsed, setFichaCollapsed] = useState(false);
  const [listWidthPct, setListWidthPct] = useState(splitPrefs.listWidthPct);
  const [stackHeightPct, setStackHeightPct] = useState(
    splitPrefs.stackHeightPct,
  );
  const [historialInstrumentFilter, setHistorialInstrumentFilter] = useState<
    string | null
  >(null);
  const [evolutionInstrumentId, setEvolutionInstrumentId] = useState<
    string | null
  >(null);

  useEffect(() => {
    persistJournalStudiesSplitPrefs({ listWidthPct, stackHeightPct });
  }, [listWidthPct, stackHeightPct]);

  useEffect(() => {
    const handle = window.setTimeout(() => setDebouncedQ(filters.q), 250);
    return () => window.clearTimeout(handle);
  }, [filters.q]);

  const listsQuery = useQuery({
    queryKey: ["lists"],
    queryFn: () => api.getLists(),
  });

  const studiesQuery = useQuery({
    queryKey: [
      "decision-studies",
      effectiveAccountId,
      filters.listId,
      debouncedQ,
      filters.period,
      filters.opinion,
      filters.status,
      filters.strengthBand,
      filters.dateFrom,
      filters.dateTo,
      STUDIES_PAGE_LIMIT,
    ],
    enabled:
      Boolean(effectiveAccountId) && (tab === "tesis" || tab === "evolucion"),
    queryFn: () =>
      api.getDecisionStudies(effectiveAccountId!, {
        listId: filters.listId === "todas" ? undefined : filters.listId,
        q: debouncedQ.trim() || undefined,
        period: filters.period === "all" ? undefined : filters.period,
        opinion: filters.opinion === "all" ? undefined : filters.opinion,
        status: filters.status === "all" ? undefined : filters.status,
        strengthBand:
          filters.strengthBand === "all" ? undefined : filters.strengthBand,
        from: filters.dateFrom
          ? `${filters.dateFrom}T00:00:00.000Z`
          : undefined,
        to: filters.dateTo ? `${filters.dateTo}T23:59:59.000Z` : undefined,
        limit: STUDIES_PAGE_LIMIT,
      }),
    refetchInterval: 60_000,
  });

  const journalQuery = useQuery({
    queryKey: [
      "decision-journal",
      effectiveAccountId,
      historialInstrumentFilter,
    ],
    enabled: Boolean(effectiveAccountId) && tab === "historial",
    queryFn: () =>
      api.getDecisionJournal(effectiveAccountId!, {
        instrumentId: historialInstrumentFilter ?? undefined,
      }),
    refetchInterval: 60_000,
  });

  const studies = useMemo(
    () => studiesQuery.data?.data.studies ?? [],
    [studiesQuery.data],
  );
  const studiesTotal = studiesQuery.data?.data.total ?? studies.length;
  const journal = journalQuery.data?.data;
  const lists = useMemo(
    () =>
      (listsQuery.data?.data ?? []).map((item) => ({
        id: item.id,
        name: item.name,
      })),
    [listsQuery.data],
  );

  const showFicha = Boolean(selected) && !fichaCollapsed;

  useEffect(() => {
    const instrumentParam = searchParams.get("instrument");
    if (!instrumentParam || studies.length === 0) return;
    const match = studies.find((s) => s.instrumentId === instrumentParam);
    if (match) {
      setSelected(match);
      if (searchParams.get("ficha") === "1") {
        setFichaCollapsed(false);
      }
    }
  }, [searchParams, studies]);

  return (
    <div
      className="flex h-[calc(100dvh-3.5rem)] min-h-[480px] flex-col gap-3 overflow-hidden p-4 md:p-6"
      data-testid="decision-journal"
    >
      <div className="flex shrink-0 flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-serif text-2xl font-semibold text-foreground sm:text-3xl">
            Decision Journal
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Seguimiento de análisis y tesis
          </p>
        </div>
        <div className="flex items-center gap-3">
          {studiesQuery.isSuccess && tab === "tesis" ? (
            <p className="text-[11px] tabular-nums text-muted-foreground">
              {studies.length === studiesTotal
                ? `${studiesTotal} tesis`
                : `${studies.length} / ${studiesTotal}`}
            </p>
          ) : null}
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={() => {
              void studiesQuery.refetch();
              void journalQuery.refetch();
            }}
          >
            <RefreshCw className="h-3.5 w-3.5" />
            Actualizar
          </Button>
        </div>
      </div>

      <div className="flex shrink-0 gap-1 rounded-lg border border-border bg-muted/30 p-0.5">
        <button
          type="button"
          data-testid="tab-tesis"
          className={cn(
            "rounded-md px-3 py-1.5 text-xs font-medium",
            tab === "tesis"
              ? "bg-card text-foreground shadow-sm"
              : "text-muted-foreground",
          )}
          onClick={() => setTab("tesis")}
        >
          Tesis
        </button>
        <button
          type="button"
          data-testid="tab-evolucion"
          className={cn(
            "rounded-md px-3 py-1.5 text-xs font-medium",
            tab === "evolucion"
              ? "bg-card text-foreground shadow-sm"
              : "text-muted-foreground",
          )}
          onClick={() => setTab("evolucion")}
        >
          Evolución
        </button>
        <button
          type="button"
          data-testid="tab-historial"
          className={cn(
            "rounded-md px-3 py-1.5 text-xs font-medium",
            tab === "historial"
              ? "bg-card text-foreground shadow-sm"
              : "text-muted-foreground",
          )}
          onClick={() => setTab("historial")}
        >
          Historial técnico
        </button>
      </div>

      {tab === "tesis" ? (
        <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-hidden">
          <JournalStudiesFilters
            value={filters}
            onChange={setFilters}
            lists={lists}
          />

          {studiesQuery.isLoading && studies.length === 0 ? (
            <p className="text-sm text-muted-foreground">Cargando tesis…</p>
          ) : null}

          {studiesQuery.isError ? (
            <Card className="rounded-xl border-destructive/40 bg-destructive/5 p-4">
              <p
                className="text-sm text-destructive"
                data-testid="studies-error"
              >
                No se pudo cargar las tesis. Revisa la API.
              </p>
            </Card>
          ) : null}

          {studiesQuery.isSuccess ? (
            <JournalStudiesSplitLayout
              className="min-h-0 flex-1"
              isWide={isWide}
              showDetail={Boolean(selected)}
              detailCollapsed={Boolean(selected) && fichaCollapsed}
              listWidthPct={listWidthPct}
              stackHeightPct={stackHeightPct}
              onListWidthPctChange={setListWidthPct}
              onStackHeightPctChange={setStackHeightPct}
              list={
                <JournalStudiesTable
                  studies={studies}
                  selectedSessionId={selected?.sessionId ?? null}
                  onSelect={(study) => {
                    setSelected(study);
                    setFichaCollapsed(false);
                    setEvolutionInstrumentId(study.instrumentId);
                  }}
                />
              }
              detail={
                selected ? (
                  showFicha ? (
                    <DecisionFichaPanel
                      study={selected}
                      onClose={() => setSelected(null)}
                      onCollapse={() => setFichaCollapsed(true)}
                    />
                  ) : (
                    <JournalStudyDetailCollapsedRail
                      symbol={selected.symbol ?? selected.instrumentId}
                      isWide={isWide}
                      onExpand={() => setFichaCollapsed(false)}
                      onClose={() => setSelected(null)}
                    />
                  )
                ) : (
                  <div className="flex h-full items-center justify-center p-4 text-[11px] text-muted-foreground">
                    Selecciona una tesis en la lista
                  </div>
                )
              }
            />
          ) : null}
        </div>
      ) : tab === "evolucion" ? (
        <JournalEvolutionPanel
          accountId={effectiveAccountId!}
          studiesCatalog={studies}
          initialInstrumentId={evolutionInstrumentId ?? selected?.instrumentId}
          onOpenHistorial={(instrumentId) => {
            setHistorialInstrumentFilter(instrumentId);
            setTab("historial");
          }}
        />
      ) : (
        <div className="min-h-0 flex-1 overflow-auto space-y-3">
          {journalQuery.isLoading && !journal ? (
            <p className="text-sm text-muted-foreground">Cargando…</p>
          ) : null}
          {journalQuery.isError ? (
            <Card className="rounded-xl border-destructive/40 bg-destructive/5 p-4">
              <p
                className="text-sm text-destructive"
                data-testid="journal-error"
              >
                No se pudo cargar el Decision Journal. Revisa la API.
              </p>
            </Card>
          ) : null}
          {journal ? (
            <>
              <Card
                className="rounded-xl border-border bg-card px-4 py-3"
                data-testid="journal-meta"
              >
                <p className="text-xs text-muted-foreground">
                  Cuenta{" "}
                  <code className="text-[10px]">{journal.accountId}</code>
                  {" · "}
                  {journal.total} entrada{journal.total === 1 ? "" : "s"}
                  {journal.total > journal.entries.length
                    ? ` (mostrando ${journal.entries.length})`
                    : null}
                  {historialInstrumentFilter ? (
                    <>
                      {" · filtro activo "}
                      <code className="text-[10px]">
                        {historialInstrumentFilter}
                      </code>
                      <button
                        type="button"
                        className="ml-2 text-primary underline-offset-2 hover:underline"
                        onClick={() => setHistorialInstrumentFilter(null)}
                      >
                        Quitar filtro
                      </button>
                    </>
                  ) : null}
                </p>
              </Card>
              <JournalTimeline entries={journal.entries} />
            </>
          ) : null}
        </div>
      )}
    </div>
  );
}
