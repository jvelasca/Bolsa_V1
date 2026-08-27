/**
 * Mejores oportunidades para mi cartera (V1.19 Opportunity Discovery).
 * Ranking ≠ Action Queue ≠ BUY. Funnel honesto + TOP 5.
 */

import { useState } from "react";
import { Link } from "react-router-dom";
import {
  JOURNAL_STUDY_OPINION_LABELS,
  JOURNAL_STUDY_VIGENCIA_LABELS,
  NO_OPERATIONAL_PLAN_COPY,
  OPPORTUNITY_CATEGORY_LABEL,
  OPPORTUNITY_HIGH_QUALITY_THRESHOLD,
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
import { formatPrice } from "@/features/charts/chart-utils";
import { cn } from "@/lib/utils";
import { mesaJournalTesisHref } from "@/features/mesa/mesa-nav-links";
import { OpportunityDrawer } from "@/features/mesa/opportunity-drawer";
import { CONFIRM_PATH } from "@/features/confirm/confirm-nav";
import { SEÑALES_PATH } from "@/features/confirm/daily-nav";
import { MesaWhatIfPanel } from "@/features/mesa/mesa-what-if-panel";

export const DEFAULT_OPPORTUNITY_UNIVERSE_LIST_ID = "ibex35";

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

  return (
    <div
      className="rounded-md border border-border/60 bg-muted/20 px-3 py-2"
      data-testid={`mesa-candidate-${row.symbol}`}
      data-category={rankRow.category}
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="font-medium">
            {rankRow.rank != null ? `#${rankRow.rank} ` : ""}
            {row.symbol}
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
            Opportunity {rankRow.quality}/100
          </p>
          <p className="text-[10px] text-muted-foreground">
            {rankRow.qualityLabel}
          </p>
        </div>
      </div>
      <p className="mt-1 text-[10px] text-muted-foreground">
        Quality {rankRow.quality} · Portfolio Fit {rankRow.suitability} ·
        Operability {rankRow.operability}
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
          <>
            <div>
              <dt className="text-muted-foreground">Entrada</dt>
              <dd>{study.entry != null ? formatPrice(study.entry) : "—"}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Stop</dt>
              <dd>{study.stop != null ? formatPrice(study.stop) : "—"}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">R/R</dt>
              <dd>
                {study.expectedRR != null
                  ? `1:${study.expectedRR.toFixed(2)}`
                  : "—"}
              </dd>
            </div>
            <div>
              <dt className="text-muted-foreground">R plan</dt>
              <dd>
                {study.initialRiskR != null
                  ? `${study.initialRiskR.toFixed(2)}R`
                  : "—"}
              </dd>
            </div>
          </>
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
  return (
    <div
      className="rounded-md border border-border/50 bg-background/40 px-3 py-2 text-[11px]"
      data-testid="mesa-opportunity-funnel"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-muted-foreground">
          Universo {funnel.universeCount} → Screening {funnel.screenedCount} →
          Hits {funnel.hitCount} → Analizadas {funnel.analyzedCount} → Setup{" "}
          {funnel.setupCount} → Encaje {funnel.portfolioFitCount} → Operables{" "}
          {funnel.operableCount}
        </p>
        <button
          type="button"
          className="text-primary hover:underline"
          onClick={onToggle}
          data-testid="mesa-funnel-why"
        >
          {expanded ? "Ocultar embudo" : "¿Por qué no aparecen más?"}
        </button>
      </div>
      {expanded ? (
        <ol
          className="mt-2 list-decimal space-y-0.5 pl-4 text-muted-foreground"
          data-testid="mesa-funnel-detail"
        >
          <li>Universo configurado: {funnel.universeCount}</li>
          <li>Screening (último scan): {funnel.screenedCount}</li>
          <li>Hits: {funnel.hitCount}</li>
          <li>Análisis reciente: {funnel.analyzedCount}</li>
          <li>Con setup (strength + R/R): {funnel.setupCount}</li>
          <li>Encaje cartera: {funnel.portfolioFitCount}</li>
          <li>Operables ahora: {funnel.operableCount}</li>
          {funnel.scanStale ? (
            <li className="text-amber-800 dark:text-amber-200">
              Scan ausente o &gt;48h — amplía/actualiza en Señales
            </li>
          ) : null}
        </ol>
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
              Amplíalo a IBEX35 (o tu lista) y ejecuta un scan en Señales para
              alimentar oportunidades. Esto no ejecuta órdenes.
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
              La decisión correcta puede ser no operar. Corre un scan o amplía
              el universo.
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
      </CardContent>
      <OpportunityDrawer
        open={drawerRow != null}
        onClose={() => setDrawerRow(null)}
        rankRow={drawerRow}
        portfolioRisk={portfolioRisk}
        positions={positions}
        equity={equity}
        cash={cash}
        sectorByInstrumentId={sectorByInstrumentId}
      />
    </Card>
  );
}
