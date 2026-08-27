/**
 * Candidatos agrupados + Operational Priority + Portfolio Scenario.
 */

import { Link } from "react-router-dom";
import {
  JOURNAL_STUDY_OPINION_LABELS,
  JOURNAL_STUDY_VIGENCIA_LABELS,
  NO_OPERATIONAL_PLAN_COPY,
  mapCandidateNextAction,
  sortByOperationalPriority,
  type MesaCandidateRowV1,
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
import { formatPrice } from "@/features/charts/chart-utils";
import { cn } from "@/lib/utils";
import { mesaJournalTesisHref } from "@/features/mesa/mesa-nav-links";
import { CONFIRM_PATH } from "@/features/confirm/confirm-nav";
import { MesaWhatIfPanel } from "@/features/mesa/mesa-what-if-panel";

type CandidateGroup = {
  status: string;
  label: string;
  items: MesaCandidateRowV1[];
  entriesBlocked: boolean;
};

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

function CandidateCard({
  row,
  entriesBlocked,
  portfolioRisk,
  positions = [],
  equity,
  cash,
  operableRank,
  sectorExposurePct,
  sectorByInstrumentId,
}: {
  row: MesaCandidateRowV1;
  entriesBlocked: boolean;
  portfolioRisk: PortfolioRiskSnapshotV1 | null;
  positions?: ReadonlyArray<PortfolioPositionRiskInput>;
  equity: number | null;
  cash: number | null;
  operableRank?: number;
  sectorExposurePct?: Record<string, number>;
  sectorByInstrumentId?: Record<string, string | null | undefined>;
}) {
  const study = row.study;
  const opinion =
    study?.opinion != null ? JOURNAL_STUDY_OPINION_LABELS[study.opinion] : "—";
  const priority = sortByOperationalPriority([row], {
    entriesBlocked,
    portfolioRisk,
    sectorExposurePct,
    sectorByInstrumentId,
    maxSectorExposurePct: 40,
  })[0]?.operationalPriority;

  return (
    <div
      className="rounded-md border border-border/60 bg-muted/20 px-3 py-2"
      data-testid={`mesa-candidate-${row.symbol}`}
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="font-medium">
            {operableRank != null ? `#${operableRank} ` : ""}
            {row.symbol}
          </p>
          <p className="text-xs text-muted-foreground">
            {row.statusLabel} · Gate {row.gate}
          </p>
        </div>
        <div className="text-right">
          {study?.strength != null ? (
            <span className="text-sm font-semibold tabular-nums">
              {study.strength.toFixed(1)}
            </span>
          ) : null}
          {priority?.verdict === "OPERABLE" ? (
            <p className="text-[10px] font-medium text-emerald-700 dark:text-emerald-300">
              OPERABLE
            </p>
          ) : priority?.verdict === "NO_OPERAR" ? (
            <p
              className="text-[10px] font-medium text-rose-700 dark:text-rose-300"
              data-testid={`mesa-candidate-no-operar-${row.symbol}`}
            >
              NO OPERAR
              {priority.suitability.value < 50 && priority.quality.value >= 70
                ? " · no encaja"
                : ""}
            </p>
          ) : null}
        </div>
      </div>
      {priority ? (
        <p className="mt-1 text-[10px] text-muted-foreground">
          Q {priority.quality.value} · Encaje {priority.suitability.value} · Op{" "}
          {priority.operability.value}
          <span className="ml-1 italic">(orden provisional)</span>
        </p>
      ) : null}
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
              <dt className="text-muted-foreground">TP1</dt>
              <dd>
                {study.target1 != null ? formatPrice(study.target1) : "—"}
              </dd>
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
            <div>
              <dt className="text-muted-foreground">Notional</dt>
              <dd>
                {study.positionValue != null
                  ? formatPrice(study.positionValue)
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
      {!priority?.operability.operable &&
      (priority?.operability.blockReasons.length ?? 0) > 0 ? (
        <p className="mt-1 text-[10px] text-amber-800 dark:text-amber-200">
          No operable: {priority?.operability.blockReasons.join(" · ")}
        </p>
      ) : null}
      <div className="mt-2 flex flex-wrap items-center gap-2">
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

export function MesaCandidatesPanel({
  groups,
  entriesBlocked,
  portfolioRisk = null,
  positions = [],
  equity = null,
  cash = null,
  useOperableRanking = true,
  sectorExposurePct,
  sectorByInstrumentId,
}: {
  groups: CandidateGroup[];
  entriesBlocked: boolean;
  portfolioRisk?: PortfolioRiskSnapshotV1 | null;
  /** @deprecated Usar portfolioRisk */
  portfolioRiskR?: number | null;
  positions?: ReadonlyArray<PortfolioPositionRiskInput>;
  equity?: number | null;
  cash?: number | null;
  useOperableRanking?: boolean;
  sectorExposurePct?: Record<string, number>;
  sectorByInstrumentId?: Record<string, string | null | undefined>;
}) {
  const total = groups.reduce((sum, g) => sum + g.items.length, 0);
  const allRows = groups.flatMap((g) => g.items);
  const operableOrder = useOperableRanking
    ? sortByOperationalPriority(allRows, {
        entriesBlocked,
        portfolioRisk,
        sectorExposurePct,
        sectorByInstrumentId,
        maxSectorExposurePct: 40,
      })
    : null;
  const rankBySymbol = new Map<string, number>();
  operableOrder?.forEach((row, i) => {
    if (row.operationalPriority.verdict === "OPERABLE") {
      rankBySymbol.set(row.symbol, i + 1);
    }
  });

  const readyCount =
    groups.find((g) => g.status === "TRIGGERED")?.items.length ?? 0;

  return (
    <Card data-testid="mesa-candidates-panel">
      <CardHeader className="pb-2">
        <CardTitle className="text-base">Candidatos de la mesa</CardTitle>
        <CardDescription>
          {entriesBlocked ? (
            <span className="text-rose-600 dark:text-rose-400">
              Nuevas entradas: BLOQUEADAS
            </span>
          ) : readyCount > 0 ? (
            `Hoy: ${readyCount} operación${readyCount === 1 ? "" : "es"} posible${readyCount === 1 ? "" : "s"}`
          ) : (
            `${total} candidato${total === 1 ? "" : "s"} en cola`
          )}
          {" · "}
          <span className="text-muted-foreground">
            Prioridad operativa (provisional)
          </span>
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {groups.length === 0 ? (
          <div
            className="rounded-md border border-dashed border-border/60 px-4 py-6 text-center"
            data-testid="mesa-no-operations"
          >
            <p className="font-medium">Hoy no hay operaciones recomendadas</p>
            <p className="mt-1 text-sm text-muted-foreground">
              La decisión correcta puede ser no operar.
            </p>
          </div>
        ) : (
          groups.map((group) => (
            <section
              key={group.status}
              data-testid={`mesa-group-${group.status}`}
            >
              <h3
                className={cn(
                  "mb-2 text-xs font-semibold uppercase tracking-wide",
                  group.status === "BLOCKED"
                    ? "text-rose-600"
                    : group.status === "TRIGGERED"
                      ? "text-emerald-700 dark:text-emerald-300"
                      : "text-muted-foreground",
                )}
              >
                {group.label} ({group.items.length})
              </h3>
              <div className="grid gap-2 sm:grid-cols-2">
                {group.items.map((row) => (
                  <CandidateCard
                    key={`${row.symbol}-${row.status}`}
                    row={row}
                    entriesBlocked={entriesBlocked}
                    portfolioRisk={portfolioRisk}
                    positions={positions}
                    equity={equity}
                    cash={cash}
                    operableRank={rankBySymbol.get(row.symbol)}
                    sectorExposurePct={sectorExposurePct}
                    sectorByInstrumentId={sectorByInstrumentId}
                  />
                ))}
              </div>
            </section>
          ))
        )}
      </CardContent>
    </Card>
  );
}
