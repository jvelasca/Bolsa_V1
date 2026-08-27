/**
 * Mejores oportunidades para mi cartera (V1.19 Opportunity Discovery).
 * Ranking ≠ Action Queue ≠ BUY. Funnel honesto + TOP 5.
 */

import { useState } from "react";
import { Link } from "react-router-dom";
import {
  ESTUDIO_LIST_ID,
  JOURNAL_STUDY_OPINION_LABELS,
  JOURNAL_STUDY_VIGENCIA_LABELS,
  NO_OPERATIONAL_PLAN_COPY,
  OPPORTUNITY_CATEGORY_LABEL,
  OPPORTUNITY_HIGH_QUALITY_THRESHOLD,
  buildOperationalPlanFromStudy,
  mapCandidateNextAction,
  opportunityQualityBandCounts,
  type MesaCandidateRowV1,
  type OpportunityCategoryV1,
  type OpportunityFunnelV1,
  type OpportunityRankRowV1,
  type OpportunityRankingV1,
  type PortfolioRiskSnapshotV1,
  type PortfolioPositionRiskInput,
} from "@bolsa/shared";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { mesaJournalTesisHref } from "@/features/mesa/mesa-nav-links";
import { OpportunityDrawer } from "@/features/mesa/opportunity-drawer";
import { CONFIRM_PATH } from "@/features/confirm/confirm-nav";
import { SEÑALES_PATH } from "@/features/confirm/daily-nav";
import { MesaWhatIfPanel } from "@/features/mesa/mesa-what-if-panel";
import { OperationalPlanView } from "@/features/mesa/operational-plan-view";
import { OpportunityScoreBars } from "@/features/mesa/opportunity-score-bars";
import {
  PRIORITY_NOT_AN_ORDER,
  buildOpportunityFunnelClocks,
  buildOpportunityFunnelSteps,
  formatFunnelTitle,
  formatPriorityScore,
  opportunityResultLabel,
  opportunityResultTone,
} from "@/features/mesa/mesa-opportunity-language";

/** Universo diario de Opportunity Discovery = Estudio (ADR-024 / V1.21). */
export const DEFAULT_OPPORTUNITY_UNIVERSE_LIST_ID = ESTUDIO_LIST_ID;

export function mesaScreenersUniverseHref(
  listId = DEFAULT_OPPORTUNITY_UNIVERSE_LIST_ID,
): string {
  const params = new URLSearchParams({ listId });
  return `${SEÑALES_PATH}?${params.toString()}`;
}

function CandidateNextAction({
  row,
  entriesBlocked,
}: {
  row: MesaCandidateRowV1;
  entriesBlocked: boolean;
}) {
  const next = mapCandidateNextAction(row, entriesBlocked);
  const label = `Acción: ${next.label}`;

  if (next.kind === "review_proposal") {
    return (
      <Link
        to={CONFIRM_PATH}
        className="rounded border border-primary/40 bg-primary/5 px-1.5 py-0.5 text-[11px] font-medium text-primary hover:underline"
        data-testid={`mesa-candidate-action-${row.symbol}`}
      >
        {label}
      </Link>
    );
  }
  if (next.kind === "view_thesis" && row.instrumentId) {
    return (
      <Link
        to={mesaJournalTesisHref(row.instrumentId, { ficha: true })}
        className="rounded border border-primary/40 bg-primary/5 px-1.5 py-0.5 text-[11px] font-medium text-primary hover:underline"
        data-testid={`mesa-candidate-action-${row.symbol}`}
      >
        {label}
      </Link>
    );
  }
  if (next.kind === "watch") {
    return (
      <span
        className="rounded border border-border/50 px-1.5 py-0.5 text-[11px] text-muted-foreground"
        data-testid={`mesa-candidate-action-${row.symbol}`}
      >
        {label}
      </span>
    );
  }
  if (row.instrumentId) {
    return (
      <Link
        to={mesaJournalTesisHref(row.instrumentId, { ficha: true })}
        className="rounded border border-primary/40 bg-primary/5 px-1.5 py-0.5 text-[11px] text-primary hover:underline"
        data-testid={`mesa-candidate-action-${row.symbol}`}
      >
        Acción: Ver tesis
      </Link>
    );
  }
  return (
    <span
      className="rounded border border-border/50 px-1.5 py-0.5 text-[11px] text-muted-foreground"
      data-testid={`mesa-candidate-action-${row.symbol}`}
    >
      {label}
    </span>
  );
}

function categoryTone(category: OpportunityCategoryV1): string {
  switch (category) {
    case "TOP":
      return "text-emerald-700 dark:text-emerald-300";
    case "NOT_FOR_PORTFOLIO":
      return "text-amber-800 dark:text-amber-200";
    case "STALE":
      return "text-amber-800 dark:text-amber-200";
    case "BLOCKED":
      return "text-rose-700 dark:text-rose-300";
    default:
      return "text-muted-foreground";
  }
}

function OpportunityCard({
  rankRow,
  entriesBlocked,
  portfolioRisk,
  positions = [],
  equity,
  cash,
  sectorByInstrumentId,
  onOpenDrawer,
}: {
  rankRow: OpportunityRankRowV1;
  entriesBlocked: boolean;
  portfolioRisk: PortfolioRiskSnapshotV1 | null;
  positions?: ReadonlyArray<PortfolioPositionRiskInput>;
  equity: number | null;
  cash: number | null;
  sectorByInstrumentId?: Record<string, string | null | undefined>;
  onOpenDrawer: (row: OpportunityRankRowV1) => void;
}) {
  const row = rankRow.candidate;
  const study = row.study;
  const opinion =
    study?.opinion != null ? JOURNAL_STUDY_OPINION_LABELS[study.opinion] : "—";
  const priority = rankRow.operationalPriority;
  const result = opportunityResultLabel(rankRow, entriesBlocked);

  return (
    <div
      className="rounded-md border border-border/60 bg-muted/20 px-3 py-2"
      data-testid={`mesa-candidate-${row.symbol}`}
      data-category={rankRow.category}
      data-result={result}
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="font-medium">
            {rankRow.rank != null ? `#${rankRow.rank} ` : ""}
            {row.symbol}
            <span
              className={cn(
                "ml-2 text-[10px] font-semibold uppercase tracking-wide",
                opportunityResultTone(result),
              )}
              data-testid={`mesa-candidate-result-${row.symbol}`}
            >
              {result}
            </span>
          </p>
          <p
            className={cn(
              "text-xs font-medium",
              categoryTone(rankRow.category),
            )}
          >
            {OPPORTUNITY_CATEGORY_LABEL[rankRow.category]}
            {rankRow.categoryReason ? ` · ${rankRow.categoryReason}` : ""}
          </p>
          <p className="text-xs text-muted-foreground">
            {row.statusLabel} · Gate {row.gate}
          </p>
        </div>
        <div className="text-right">
          <p className="text-sm font-semibold tabular-nums">
            {formatPriorityScore(rankRow.quality)}
          </p>
          <p
            className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground"
            data-testid={`mesa-candidate-not-order-${row.symbol}`}
          >
            {PRIORITY_NOT_AN_ORDER}
          </p>
          <p className="text-[10px] text-muted-foreground">
            {rankRow.qualityLabel}
          </p>
        </div>
      </div>
      <OpportunityScoreBars
        rankRow={rankRow}
        className="mt-2"
        testId={`mesa-candidate-bars-${row.symbol}`}
      />
      <p className="mt-1 text-[10px] text-muted-foreground">
        Resultado: {result}
        <span className="ml-1 italic">(provisional · ≠ permiso)</span>
      </p>
      <dl className="mt-2 grid gap-1 text-[11px] sm:grid-cols-2">
        <div>
          <dt className="text-muted-foreground">Opinión</dt>
          <dd>{opinion}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Vigencia</dt>
          <dd>
            {study?.vigencia
              ? JOURNAL_STUDY_VIGENCIA_LABELS[study.vigencia]
              : "—"}
          </dd>
        </div>
        {study?.hasOperationalPlan ? (
          <div className="mt-2 sm:col-span-2">
            <OperationalPlanView
              plan={buildOperationalPlanFromStudy(study)}
              testId={`operational-plan-candidate-${row.symbol}`}
            />
          </div>
        ) : (
          <div className="sm:col-span-2">
            <p className="text-muted-foreground">{NO_OPERATIONAL_PLAN_COPY}</p>
          </div>
        )}
      </dl>
      {!(sectorByInstrumentId?.[row.instrumentId ?? ""] ?? "").trim() ? (
        <p
          className="mt-1 text-[10px] text-amber-800 dark:text-amber-200"
          data-testid={`mesa-candidate-sector-missing-${row.symbol}`}
        >
          Sector: — (dato incompleto)
        </p>
      ) : null}
      {!priority.operability.operable &&
      priority.operability.blockReasons.length > 0 ? (
        <p className="mt-1 text-[10px] text-amber-800 dark:text-amber-200">
          No operable: {priority.operability.blockReasons.join(" · ")}
        </p>
      ) : null}
      <div className="mt-2 flex flex-wrap items-center gap-2">
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="h-7 text-[11px]"
          onClick={() => onOpenDrawer(rankRow)}
          data-testid={`mesa-candidate-view-${row.symbol}`}
        >
          Ver oportunidad
        </Button>
        <CandidateNextAction row={row} entriesBlocked={entriesBlocked} />
        <MesaWhatIfPanel
          row={row}
          portfolioRisk={portfolioRisk}
          positions={positions}
          candidateSector={
            row.instrumentId
              ? (sectorByInstrumentId?.[row.instrumentId] ?? null)
              : null
          }
          equity={equity}
          cash={cash}
        />
      </div>
    </div>
  );
}

function FunnelStrip({
  funnel,
  expanded,
  onToggle,
}: {
  funnel: OpportunityFunnelV1;
  expanded: boolean;
  onToggle: () => void;
}) {
  const steps = buildOpportunityFunnelSteps(funnel);
  const clocks = buildOpportunityFunnelClocks(funnel);
  return (
    <div
      className="rounded-md border border-border/50 bg-background/40 px-3 py-2 text-[11px]"
      data-testid="mesa-opportunity-funnel"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-muted-foreground">
          {steps.map((s, i) => (
            <span key={s.label}>
              {i > 0 ? " → " : null}
              {s.label} {s.count}
            </span>
          ))}
        </p>
        <button
          type="button"
          className="text-primary hover:underline"
          onClick={onToggle}
          data-testid="mesa-funnel-why"
        >
          {expanded
            ? "Ocultar embudo"
            : formatFunnelTitle(funnel.operableCount)}
        </button>
      </div>
      {expanded ? (
        <div className="mt-2 space-y-2" data-testid="mesa-funnel-detail">
          <ol className="list-decimal space-y-0.5 pl-4 text-muted-foreground">
            {steps.map((s) => (
              <li key={s.label}>
                {s.label}: {s.count}
                <span className="ml-1 text-[10px]">({s.hint})</span>
              </li>
            ))}
            {funnel.scanStale ? (
              <li className="text-amber-800 dark:text-amber-200">
                Scan ausente o &gt;48h — amplía/actualiza en Señales
              </li>
            ) : null}
          </ol>
          <dl
            className="grid gap-1 rounded border border-border/40 bg-muted/20 px-2 py-1.5 sm:grid-cols-3"
            data-testid="mesa-funnel-clocks"
          >
            {clocks.map((c) => (
              <div key={c.id}>
                <dt className="text-[10px] text-muted-foreground">{c.label}</dt>
                <dd className="tabular-nums font-medium">{c.value}</dd>
              </div>
            ))}
          </dl>
        </div>
      ) : null}
    </div>
  );
}

function categorySections(
  all: OpportunityRankRowV1[],
): Array<{ category: OpportunityCategoryV1; items: OpportunityRankRowV1[] }> {
  const order: OpportunityCategoryV1[] = [
    "TOP",
    "WATCH",
    "STALE",
    "NOT_FOR_PORTFOLIO",
    "BLOCKED",
  ];
  return order
    .map((category) => ({
      category,
      items: all.filter((r) => r.category === category),
    }))
    .filter((s) => s.items.length > 0);
}

export function MesaCandidatesPanel({
  ranking,
  entriesBlocked,
  portfolioRisk = null,
  positions = [],
  equity = null,
  cash = null,
  sectorExposurePct: _sectorExposurePct,
  sectorByInstrumentId,
  universeListId = DEFAULT_OPPORTUNITY_UNIVERSE_LIST_ID,
}: {
  ranking: OpportunityRankingV1 | null;
  entriesBlocked: boolean;
  portfolioRisk?: PortfolioRiskSnapshotV1 | null;
  positions?: ReadonlyArray<PortfolioPositionRiskInput>;
  equity?: number | null;
  cash?: number | null;
  /** Reservado — suitability ya viene en ranking.operationalPriority. */
  sectorExposurePct?: Record<string, number>;
  sectorByInstrumentId?: Record<string, string | null | undefined>;
  universeListId?: string;
}) {
  const [funnelOpen, setFunnelOpen] = useState(false);
  const [showAll, setShowAll] = useState(false);
  const [drawerRow, setDrawerRow] = useState<OpportunityRankRowV1 | null>(null);

  const funnel = ranking?.funnel;
  const top = ranking?.top ?? [];
  const all = ranking?.all ?? [];
  const discovered = ranking?.discovered ?? [];
  const maxQuality = ranking?.maxQuality ?? 0;
  const threshold =
    ranking?.highQualityThreshold ?? OPPORTUNITY_HIGH_QUALITY_THRESHOLD;
  const lowQualityDay = all.length > 0 && maxQuality < threshold;
  const smallUniverse = (funnel?.universeCount ?? 0) < 20;
  const needsScanCta = Boolean(funnel?.scanStale || smallUniverse);
  const bands = opportunityQualityBandCounts(all);
  const updatedLabel = funnel?.asOf
    ? new Date(funnel.asOf).toLocaleTimeString(undefined, {
        hour: "2-digit",
        minute: "2-digit",
      })
    : "—";

  const visibleSections = showAll
    ? categorySections(all)
    : [{ category: "TOP" as const, items: top }];

  return (
    <Card data-testid="mesa-candidates-panel">
      <CardHeader className="pb-2">
        <CardTitle className="text-base">
          Mejores oportunidades para mi cartera
        </CardTitle>
        <CardDescription>
          {entriesBlocked ? (
            <span className="text-rose-600 dark:text-rose-400">
              Nuevas entradas: BLOQUEADAS
            </span>
          ) : (
            <>
              Actualizado: {updatedLabel}
              {" · "}
              Universo {funnel?.universeCount ?? 0}
              {" · "}
              Oportunidades {all.length}
              {" · "}
              Operables {funnel?.operableCount ?? 0}
              {" · "}
              Top {top.length}
            </>
          )}
          {" · "}
          <span className="text-muted-foreground">
            Ranking provisional · ≠ permiso · ≠ BUY
          </span>
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {funnel ? (
          <FunnelStrip
            funnel={funnel}
            expanded={funnelOpen}
            onToggle={() => setFunnelOpen((v) => !v)}
          />
        ) : null}

        {needsScanCta ? (
          <div
            className="rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-sm"
            data-testid="mesa-universe-cta"
          >
            <p className="font-medium text-amber-900 dark:text-amber-100">
              {smallUniverse
                ? "Tu universo de análisis es pequeño"
                : "No hay un scan reciente del universo"}
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              Añade valores a Estudio y ejecuta Actualizar / un scan sobre
              Estudio para alimentar oportunidades. Esto no ejecuta órdenes.
            </p>
            <Link
              to={mesaScreenersUniverseHref(universeListId)}
              className="mt-2 inline-block text-xs font-medium text-primary hover:underline"
            >
              Abrir Señales · lista {universeListId} →
            </Link>
          </div>
        ) : null}

        {lowQualityDay ? (
          <div
            className="rounded-md border border-amber-500/40 bg-amber-500/5 px-3 py-2 text-sm"
            data-testid="mesa-low-quality-day"
          >
            <p className="font-medium">
              No hay oportunidades de alta calidad hoy
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              Top disponible: {maxQuality}/100 · Umbral recomendado: {threshold}
              → No abrir nuevas posiciones por ranking solo.
            </p>
            <p className="mt-1 text-[10px] text-muted-foreground">
              ⭐⭐⭐⭐⭐ {bands.Excelente} · ⭐⭐⭐⭐ {bands.Alta} · ⭐⭐⭐{" "}
              {bands.Buena} · ⭐⭐ {bands.Débil} · ⭐ {bands["No atractiva"]}
            </p>
          </div>
        ) : null}

        {all.length === 0 ? (
          <div
            className="rounded-md border border-dashed border-border/60 px-4 py-6 text-center"
            data-testid="mesa-no-operations"
          >
            <p className="font-medium">Hoy no hay operaciones recomendadas</p>
            <p className="mt-1 text-sm text-muted-foreground">
              La decisión correcta puede ser no operar. Añade valores a Estudio
              o corre Actualizar / scan sobre Estudio.
            </p>
            <Link
              to={mesaScreenersUniverseHref(universeListId)}
              className="mt-3 inline-block text-xs text-primary hover:underline"
            >
              Ir a Señales →
            </Link>
          </div>
        ) : (
          <>
            {visibleSections.map((section) => (
              <section
                key={section.category}
                data-testid={`mesa-opp-group-${section.category}`}
              >
                <h3
                  className={cn(
                    "mb-2 text-xs font-semibold uppercase tracking-wide",
                    categoryTone(section.category),
                  )}
                >
                  {OPPORTUNITY_CATEGORY_LABEL[section.category]} (
                  {section.items.length})
                </h3>
                <div className="grid gap-2 sm:grid-cols-2">
                  {section.items.map((rankRow) => (
                    <OpportunityCard
                      key={`${rankRow.symbol}-${rankRow.category}`}
                      rankRow={rankRow}
                      entriesBlocked={entriesBlocked}
                      portfolioRisk={portfolioRisk}
                      positions={positions}
                      equity={equity}
                      cash={cash}
                      sectorByInstrumentId={sectorByInstrumentId}
                      onOpenDrawer={setDrawerRow}
                    />
                  ))}
                </div>
              </section>
            ))}
            {all.length > top.length ? (
              <button
                type="button"
                className="text-xs text-primary hover:underline"
                onClick={() => setShowAll((v) => !v)}
                data-testid="mesa-show-all-opportunities"
              >
                {showAll
                  ? "Ver solo TOP"
                  : `Ver las ${all.length} oportunidades`}
              </button>
            ) : null}
          </>
        )}

        {discovered.length > 0 ? (
          <section
            className="rounded-md border border-dashed border-border/60 px-3 py-2"
            data-testid="mesa-discovered-outside-estudio"
          >
            <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Descubierto fuera de Estudio ({discovered.length})
            </h3>
            <p className="mb-2 text-[11px] text-muted-foreground">
              Interesante, pero no operable en el ciclo diario hasta añadirlo a
              Estudio. Ranking ≠ BUY.
            </p>
            <ul className="flex flex-wrap gap-2 text-xs">
              {discovered.slice(0, 8).map((row) => (
                <li
                  key={`disc-${row.instrumentId ?? row.symbol}`}
                  className="rounded border border-border/50 bg-muted/30 px-2 py-1"
                >
                  {row.symbol}
                  {row.quality > 0 ? ` · ${row.quality}` : ""}
                </li>
              ))}
            </ul>
          </section>
        ) : null}
      </CardContent>
      <OpportunityDrawer
        open={drawerRow != null}
        onClose={() => setDrawerRow(null)}
        rankRow={drawerRow}
        entriesBlocked={entriesBlocked}
        portfolioRisk={portfolioRisk}
        positions={positions}
        equity={equity}
        cash={cash}
        sectorByInstrumentId={sectorByInstrumentId}
      />
    </Card>
  );
}
