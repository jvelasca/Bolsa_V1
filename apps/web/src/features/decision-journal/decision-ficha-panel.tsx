import { useState } from "react";
import { ChevronDown, PanelRightClose, X } from "lucide-react";
import {
  JOURNAL_STUDY_OPINION_LABELS,
  JOURNAL_STUDY_PERIOD_LABELS,
  JOURNAL_STUDY_STATUS_LABELS,
  buildOperationalPlanFromStudy,
  journalStudyConsensusPercents,
  type DecisionJournalStudyViewV1,
  type JournalStudyOpinion,
  type JournalStudyPeriod,
  type JournalStudyUserStatus,
  type PositionDto,
} from "@bolsa/shared";
import { IconButton } from "@/components/ui/icon-button";
import { DecisionStudyChart } from "@/features/decision-journal/decision-study-chart";
import { openDecisionReplay } from "@/features/decision-journal/decision-journal-helpers";
import { formatPrice } from "@/features/charts/chart-utils";
import { OperationalPlanView } from "@/features/mesa/operational-plan-view";
import { PositionOperatingSummary } from "@/features/trading/position-operating-summary";
import { cn } from "@/lib/utils";

function opinionTone(opinion: string | null): string {
  if (opinion === "bullish") return "text-emerald-700 dark:text-emerald-300";
  if (opinion === "bearish") return "text-rose-700 dark:text-rose-300";
  return "text-muted-foreground";
}

function BiasDonut({
  label,
  count,
  percent,
  color,
}: {
  label: string;
  count: number;
  percent: number;
  color: string;
}) {
  const r = 16;
  const c = 2 * Math.PI * r;
  const dash = (Math.max(0, Math.min(100, percent)) / 100) * c;
  return (
    <div className="flex flex-col items-center gap-1">
      <svg width="44" height="44" viewBox="0 0 44 44" aria-hidden>
        <circle
          cx="22"
          cy="22"
          r={r}
          fill="none"
          stroke="currentColor"
          className="text-muted/40"
          strokeWidth="6"
        />
        <circle
          cx="22"
          cy="22"
          r={r}
          fill="none"
          stroke={color}
          strokeWidth="6"
          strokeDasharray={`${dash} ${c}`}
          strokeLinecap="round"
          transform="rotate(-90 22 22)"
        />
        <text
          x="22"
          y="26"
          textAnchor="middle"
          fontSize="9"
          fill="currentColor"
        >
          {count}
        </text>
      </svg>
      <p className="text-[10px] text-muted-foreground">
        {label} {percent}%
      </p>
    </div>
  );
}

export function DecisionFichaPanel({
  study,
  position,
  portfolioReconStatus,
  onClose,
  onCollapse,
}: {
  study: DecisionJournalStudyViewV1;
  position?: PositionDto | null;
  portfolioReconStatus?: string | null;
  onClose: () => void;
  onCollapse: () => void;
}) {
  const [fullAnalysis, setFullAnalysis] = useState(false);
  const [techOpen, setTechOpen] = useState(false);
  const pct = journalStudyConsensusPercents(study.consensus);
  const opinionLabel = study.opinion
    ? JOURNAL_STUDY_OPINION_LABELS[study.opinion as JournalStudyOpinion]
    : "—";
  const periodLabel = study.period
    ? JOURNAL_STUDY_PERIOD_LABELS[study.period as JournalStudyPeriod]
    : "—";
  const statusLabel =
    JOURNAL_STUDY_STATUS_LABELS[study.status as JournalStudyUserStatus] ??
    study.status;
  const studied = new Date(study.studiedAt);
  const studiedLabel = Number.isNaN(studied.getTime())
    ? study.studiedAt
    : studied.toLocaleString(undefined, {
        day: "2-digit",
        month: "short",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
  const summaryLines = study.analysisNotes.slice(0, 3);
  const restNotes = study.analysisNotes.slice(3);
  const snapshotEvalNames = [
    ...(study.indicators.primary
      ? study.indicators.primary.split(" + ").map((s) => s.trim())
      : []),
    ...(study.indicators.confirmation
      ? study.indicators.confirmation.split(" + ").map((s) => s.trim())
      : []),
  ].filter(Boolean);

  return (
    <aside
      className="flex h-full min-h-0 flex-col overflow-hidden border-l border-border bg-card"
      data-testid="decision-ficha"
    >
      <header className="flex items-start justify-between gap-2 border-b border-border px-3 py-2">
        <div>
          <p className="text-lg font-semibold leading-tight">
            {study.symbol ?? study.instrumentId}
          </p>
          {study.name ? (
            <p className="text-xs text-muted-foreground">{study.name}</p>
          ) : null}
          <p
            className={cn(
              "mt-1 text-xs font-semibold",
              opinionTone(study.opinion),
            )}
          >
            {opinionLabel} · {periodLabel}
            {study.strength != null ? ` · ${study.strength.toFixed(1)}/10` : ""}
          </p>
          <p className="text-[10px] text-muted-foreground">
            Estudio realizado {studiedLabel}
          </p>
        </div>
        <div className="flex gap-1">
          <IconButton
            icon={PanelRightClose}
            title="Colapsar ficha"
            onClick={onCollapse}
            className="h-7 w-7"
          />
          <IconButton
            icon={X}
            title="Cerrar ficha"
            onClick={onClose}
            className="h-7 w-7"
          />
        </div>
      </header>

      <div className="min-h-0 flex-1 space-y-3 overflow-y-auto px-3 py-3">
        <section className="rounded-lg border border-border/70 bg-muted/20 p-3">
          <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
            Decisión IA
          </p>
          <p
            className={cn(
              "mt-1 text-sm font-semibold",
              opinionTone(study.opinion),
            )}
          >
            {opinionLabel}
          </p>
          <p className="mt-1 text-xs text-foreground/80">
            {study.decisionSummary ?? "Sin resumen persistido en la sesión."}
          </p>
          {study.strength != null ? (
            <p className="mt-2 text-[11px] text-muted-foreground">
              Confianza {study.strength.toFixed(1)} / 10 · {statusLabel}
            </p>
          ) : null}
        </section>

        <section>
          <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
            Gráfico de decisión
          </p>
          <DecisionStudyChart study={study} />
        </section>

        {study.trends.length > 0 ? (
          <section>
            <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
              Tendencias
            </p>
            <ul className="space-y-1 text-xs">
              {study.trends.map((trend) => (
                <li key={trend.key} className="flex justify-between gap-2">
                  <span className="text-muted-foreground">{trend.label}</span>
                  <span>{trend.display ?? "—"}</span>
                </li>
              ))}
            </ul>
          </section>
        ) : null}

        {study.consensus.total > 0 ? (
          <section data-testid="ficha-evaluations">
            <p className="mb-2 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
              Evaluaciones técnicas
            </p>
            <div className="grid grid-cols-3 gap-2 text-center text-xs">
              <BiasDonut
                label="Alcista"
                count={study.consensus.bullish}
                percent={pct.bullish}
                color="#059669"
              />
              <BiasDonut
                label="Neutro"
                count={study.consensus.neutral}
                percent={pct.neutral}
                color="#64748b"
              />
              <BiasDonut
                label="Bajista"
                count={study.consensus.bearish}
                percent={pct.bearish}
                color="#e11d48"
              />
            </div>
            <p className="mt-1 text-[10px] text-muted-foreground">
              {study.consensus.total === 1
                ? "1 evaluación"
                : `${study.consensus.total} evaluaciones`}
            </p>
            {snapshotEvalNames.length > 0 ? (
              <details className="mt-1">
                <summary className="cursor-pointer text-[11px] text-primary">
                  Ver evaluaciones del snapshot
                </summary>
                <ul className="mt-1 list-disc pl-4 text-[11px] text-muted-foreground">
                  {snapshotEvalNames.map((name) => (
                    <li key={name}>{name}</li>
                  ))}
                </ul>
              </details>
            ) : null}
          </section>
        ) : null}

        <section data-testid="ficha-analysis">
          <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
            Análisis
          </p>
          {summaryLines.length === 0 ? (
            <p className="text-xs text-muted-foreground">
              Sin texto de análisis en la sesión.
            </p>
          ) : (
            <ul className="space-y-1 text-xs">
              {(fullAnalysis ? study.analysisNotes : summaryLines).map(
                (line) => (
                  <li key={line}>{line}</li>
                ),
              )}
            </ul>
          )}
          {restNotes.length > 0 ? (
            <button
              type="button"
              className="mt-1 flex items-center gap-1 text-[11px] text-primary"
              onClick={() => setFullAnalysis((v) => !v)}
            >
              <ChevronDown
                className={cn("h-3 w-3", !fullAnalysis && "-rotate-90")}
              />
              {fullAnalysis
                ? "Ocultar análisis completo"
                : "Ver análisis completo"}
            </button>
          ) : null}
        </section>

        {study.invalidation.length > 0 ? (
          <section
            className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-3"
            data-testid="ficha-invalidation"
          >
            <p className="text-[10px] font-semibold uppercase tracking-wide text-amber-800 dark:text-amber-200">
              ¿Qué invalidaría la tesis?
            </p>
            <ul className="mt-1 list-disc space-y-0.5 pl-4 text-xs">
              {study.invalidation.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </section>
        ) : null}

        {study.nextReviewAt ? (
          <section data-testid="ficha-next-review">
            <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
              Próxima revisión
            </p>
            <p className="text-xs">{study.nextReviewAt}</p>
          </section>
        ) : null}

        {position ? (
          <PositionOperatingSummary
            position={position}
            portfolioReconStatus={portfolioReconStatus}
          />
        ) : null}

        {study.hasOperationalPlan ? (
          <OperationalPlanView
            plan={buildOperationalPlanFromStudy(study)}
            testId={`operational-plan-ficha-${study.symbol ?? study.sessionId}`}
          />
        ) : null}

        {study.hasOperationalPlan && study.riskAmount != null ? (
          <p className="text-[11px] text-muted-foreground">
            Pérdida máxima estimada: {formatPrice(study.riskAmount)}
          </p>
        ) : null}

        <details
          className="rounded-md border border-border/60 p-2"
          open={techOpen}
          onToggle={(event) =>
            setTechOpen((event.target as HTMLDetailsElement).open)
          }
        >
          <summary className="cursor-pointer text-[10px] text-muted-foreground">
            Información técnica
          </summary>
          <div className="mt-1 space-y-0.5 text-[11px] text-muted-foreground">
            <p>
              decisionId: <code>{study.decisionId ?? "—"}</code>
            </p>
            <p>
              sessionId: <code>{study.sessionId}</code>
            </p>
            <p>
              instrumentId: <code>{study.instrumentId}</code>
            </p>
            {study.tradePlanStatus ? (
              <p>
                TradePlan.status: <code>{study.tradePlanStatus}</code>
              </p>
            ) : null}
            <button
              type="button"
              className="text-primary underline-offset-2 hover:underline"
              onClick={() => openDecisionReplay(study.sessionId)}
            >
              Abrir Replay
            </button>
          </div>
        </details>
      </div>
    </aside>
  );
}

/** Rail estrecho cuando la ficha está colapsada pero hay tesis seleccionada. */
export function JournalStudyDetailCollapsedRail({
  symbol,
  isWide,
  onExpand,
  onClose,
}: {
  symbol: string;
  isWide: boolean;
  onExpand: () => void;
  onClose: () => void;
}) {
  if (!isWide) {
    return (
      <div className="flex h-full min-h-0 w-full items-center gap-2 bg-muted/30 px-2">
        <IconButton icon={X} title="Quitar selección" onClick={onClose} />
        <button
          type="button"
          className="min-w-0 flex-1 truncate text-left text-[11px] font-semibold text-muted-foreground hover:text-foreground"
          title={`Mostrar ficha · ${symbol}`}
          onClick={onExpand}
        >
          Ficha · {symbol}
        </button>
        <button
          type="button"
          className="rounded p-1 text-muted-foreground hover:bg-accent hover:text-foreground"
          title="Desplegar ficha"
          onClick={onExpand}
        >
          <ChevronDown className="h-3.5 w-3.5" />
        </button>
      </div>
    );
  }

  return (
    <div className="flex h-full min-h-0 w-full flex-col items-center gap-2 border-l border-border/60 bg-muted/30 py-2">
      <IconButton icon={X} title="Quitar selección" onClick={onClose} />
      <button
        type="button"
        className="flex min-h-0 flex-1 flex-col items-center justify-center gap-1 px-1 text-[10px] font-semibold text-muted-foreground hover:text-foreground"
        title={`Mostrar ficha · ${symbol}`}
        onClick={onExpand}
      >
        <span
          className="max-h-[min(12rem,50vh)] truncate [writing-mode:vertical-rl]"
          style={{ textOrientation: "mixed" }}
        >
          {symbol}
        </span>
      </button>
      <button
        type="button"
        className="rounded p-1 text-muted-foreground hover:bg-accent hover:text-foreground"
        title="Desplegar ficha"
        onClick={onExpand}
      >
        <PanelRightClose className="h-3.5 w-3.5 rotate-180" />
      </button>
    </div>
  );
}
