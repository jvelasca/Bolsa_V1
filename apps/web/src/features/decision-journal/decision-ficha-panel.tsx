import { useState } from "react";
import { ChevronDown, PanelRightClose, X } from "lucide-react";
import {
  JOURNAL_STUDY_OPINION_LABELS,
  JOURNAL_STUDY_PERIOD_LABELS,
  JOURNAL_STUDY_STATUS_LABELS,
  buildOperationalPlanFromStudy,
  buildEntryOperatingTruth,
  buildExecutionState,
  buildJournalSpineView,
  buildPositionOperatingTruth,
  buildTradeStory,
  formatJournalMfeMaeLine,
  journalStudyConsensusPercents,
  type DecisionJournalEntryV1,
  type DecisionJournalStudyViewV1,
  type JournalStudyOpinion,
  type JournalStudyPeriod,
  type JournalStudyUserStatus,
  type PositionDto,
  type SubmitIntentListItemV1,
} from "@bolsa/shared";
import { IconButton } from "@/components/ui/icon-button";
import { DecisionStudyChart } from "@/features/decision-journal/decision-study-chart";
import { openDecisionReplay } from "@/features/decision-journal/decision-journal-helpers";
import { formatPrice } from "@/features/charts/chart-utils";
import { OperationalPlanView } from "@/features/mesa/operational-plan-view";
import { PositionOperatingSummary } from "@/features/trading/position-operating-summary";
import { EntryOperatingSummary } from "@/features/trading/entry-operating-summary";
import { ExitRouteView } from "@/features/trading/exit-route-view";
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

function formatStoryAsOf(asOf: string): string {
  const d = new Date(asOf);
  if (Number.isNaN(d.getTime())) return asOf;
  return d.toLocaleString(undefined, {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatRMetric(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return "—";
  const abs = Math.abs(value);
  const body = Number.isInteger(abs) ? String(abs) : abs.toFixed(2);
  return `${value < 0 ? "−" : ""}${body}R`;
}

const LEARNING_VERDICT_LABELS: Record<string, string> = {
  hit: "Acierto",
  miss: "Fallo",
  neutral: "Neutral",
  invalid: "Inválido",
  skipped: "Omitido",
};

function spineStepTone(state: string): string {
  if (state === "done")
    return "border-emerald-500/40 bg-emerald-500/10 text-emerald-800 dark:text-emerald-200";
  if (state === "current")
    return "border-primary/50 bg-primary/10 text-foreground font-semibold";
  if (state === "unknown")
    return "border-amber-500/30 bg-amber-500/5 text-amber-900 dark:text-amber-200";
  return "border-border/60 bg-muted/20 text-muted-foreground";
}

export function DecisionFichaPanel({
  study,
  position,
  portfolioReconStatus,
  entriesBlocked,
  gateStatus,
  orderPending,
  submitIntent,
  inConfirmQueue,
  journalEntries,
  onClose,
  onCollapse,
}: {
  study: DecisionJournalStudyViewV1;
  position?: PositionDto | null;
  portfolioReconStatus?: string | null;
  entriesBlocked?: boolean;
  gateStatus?: string | null;
  orderPending?: boolean;
  submitIntent?: SubmitIntentListItemV1 | null;
  inConfirmQueue?: boolean;
  /** Spine journal rows for this instrument/decision — optional thin wire. */
  journalEntries?: DecisionJournalEntryV1[] | null;
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
  const positionPot = position
    ? buildPositionOperatingTruth({
        position,
        study,
        portfolioReconStatus,
        orderPending,
        submitIntent,
      })
    : null;
  const positionTruth = positionPot?.operational ?? null;
  const entryTruth =
    !position && study.hasOperationalPlan
      ? buildEntryOperatingTruth({
          study,
          entriesBlocked,
          gateStatus,
          orderPendingFill: orderPending,
          inConfirmQueue,
        })
      : null;

  // TradeStory thin wire: only facts with asOf. No invent from tradePlanStatus /
  // orderPending boolean / thin OperationalPositionDto (revisions/T1 stamps missing).
  const tradeStoryExecution =
    orderPending || submitIntent
      ? buildExecutionState({
          instrumentId: study.instrumentId,
          pendingOrder: orderPending,
          submitIntent: submitIntent ?? null,
          asOf: submitIntent?.sendAttemptedAt ?? null,
        })
      : null;
  const tradeStory = buildTradeStory({
    instrumentId: study.instrumentId,
    decisionId: study.decisionId,
    study,
    journalEntries: journalEntries ?? null,
    submitIntent: submitIntent ?? null,
    executionState: tradeStoryExecution,
  });
  const spine = buildJournalSpineView({
    study,
    tradeStory,
    // Thin PositionDto does not carry realizedR / life peaks — do not invent.
    positionState: null,
  });
  const showResultMetrics =
    spine.result.initialRiskR != null ||
    spine.result.realizedR != null ||
    spine.result.finalR != null ||
    spine.result.mfeMae != null ||
    spine.result.learningVerdict != null ||
    study.status === "closed";

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

        {positionPot ? (
          <>
            <PositionOperatingSummary
              pot={positionPot}
              position={position ?? undefined}
              orderPending={orderPending}
              submitIntent={submitIntent}
              portfolioReconStatus={portfolioReconStatus}
            />
            {positionTruth?.plan.hasPlan ? (
              <OperationalPlanView
                plan={positionTruth.plan}
                omitLiveMetrics
                testId={`operational-plan-ficha-${study.symbol ?? study.sessionId}`}
              />
            ) : null}
            {position ? (
              <ExitRouteView
                truth={positionTruth}
                position={position}
                study={study}
              />
            ) : null}
          </>
        ) : entryTruth ? (
          <>
            <EntryOperatingSummary
              truth={entryTruth}
              orderPendingFill={orderPending}
              submitIntent={submitIntent}
            />
            {entryTruth.plan.hasPlan ? (
              <OperationalPlanView
                plan={entryTruth.plan}
                testId={`operational-plan-ficha-${study.symbol ?? study.sessionId}`}
              />
            ) : null}
          </>
        ) : study.hasOperationalPlan ? (
          <OperationalPlanView
            plan={buildOperationalPlanFromStudy(study)}
            testId={`operational-plan-ficha-${study.symbol ?? study.sessionId}`}
          />
        ) : null}

        {entryTruth?.sizing.riskAmount !=
        null ? null : study.hasOperationalPlan && study.riskAmount != null ? (
          <p className="text-[11px] text-muted-foreground">
            Pérdida máxima estimada: {formatPrice(study.riskAmount)}
          </p>
        ) : null}

        <section
          className="rounded-lg border border-border/70 bg-muted/10 p-3"
          data-testid="journal-spine"
          aria-label="Cadena de la operación"
        >
          <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
            Cadena de la operación
          </p>
          <ol className="mt-2 flex flex-wrap gap-1.5">
            {spine.steps.map((step) => (
              <li
                key={step.id}
                className={cn(
                  "rounded-md border px-2 py-1 text-[11px]",
                  spineStepTone(step.state),
                )}
                data-testid={`journal-spine-step-${step.id}`}
                data-state={step.state}
                title={
                  step.asOf
                    ? `${step.label} · ${formatStoryAsOf(step.asOf)}`
                    : step.label
                }
              >
                <span>{step.label}</span>
                {step.state === "done" ? (
                  <span className="ml-1 opacity-70" aria-hidden>
                    ✓
                  </span>
                ) : null}
                {step.state === "current" ? (
                  <span className="ml-1 opacity-70" aria-hidden>
                    ●
                  </span>
                ) : null}
              </li>
            ))}
          </ol>
          <p className="mt-2 text-[10px] text-muted-foreground">
            Solo hechos con marca de tiempo. Plan ≠ alcanzado. Trail hint ≠
            aplicado.
          </p>
        </section>

        {showResultMetrics ? (
          <section
            className="rounded-lg border border-border/70 bg-card p-3"
            data-testid="journal-result-metrics"
            aria-label="Resultado"
          >
            <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
              Resultado
            </p>
            <dl className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1.5 text-xs sm:grid-cols-3">
              <div>
                <dt className="text-muted-foreground">Riesgo inicial</dt>
                <dd
                  className="font-medium tabular-nums"
                  data-testid="journal-initial-risk-r"
                >
                  {formatRMetric(spine.result.initialRiskR)}
                </dd>
              </div>
              <div>
                <dt className="text-muted-foreground">R realizado</dt>
                <dd
                  className="font-medium tabular-nums"
                  data-testid="journal-realized-r"
                >
                  {formatRMetric(spine.result.realizedR)}
                </dd>
              </div>
              <div>
                <dt className="text-muted-foreground">R final</dt>
                <dd
                  className="font-medium tabular-nums"
                  data-testid="journal-final-r"
                >
                  {formatRMetric(spine.result.finalR)}
                </dd>
              </div>
            </dl>
            {spine.result.mfeMae ? (
              <div className="mt-3" data-testid="journal-mfe-mae">
                <p className="text-[10px] font-semibold uppercase text-muted-foreground">
                  Excursión
                </p>
                <p className="mt-1 text-sm tabular-nums">
                  {formatJournalMfeMaeLine(spine.result.mfeMae)}
                </p>
                <p className="mt-0.5 text-[10px] text-muted-foreground">
                  Máximo a favor / máximo en contra (foto de sesión).
                </p>
              </div>
            ) : null}
            {spine.result.learningVerdict ? (
              <p
                className="mt-2 text-[11px] text-muted-foreground"
                data-testid="journal-learning-verdict"
              >
                Aprendizaje tesis:{" "}
                <span className="font-medium text-foreground">
                  {LEARNING_VERDICT_LABELS[spine.result.learningVerdict] ??
                    spine.result.learningVerdict}
                </span>
                <span className="ml-1">· no es R final</span>
              </p>
            ) : null}
          </section>
        ) : null}

        <details
          className="rounded-md border border-border/60 p-2"
          data-testid="ficha-trade-story"
        >
          <summary className="cursor-pointer text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
            Eventos con marca de tiempo
            {tradeStory.events.length > 0
              ? ` · ${tradeStory.events.length}`
              : ""}
          </summary>
          {tradeStory.events.length === 0 ? (
            <p className="mt-1 text-xs text-muted-foreground">
              Sin eventos con marca de tiempo. No se inventan fases desde el
              estado actual (preparada/trigger/T1 sin stamp).
            </p>
          ) : (
            <ol className="mt-2 space-y-1.5 text-xs">
              {tradeStory.events.map((ev) => (
                <li
                  key={ev.eventId}
                  className="flex justify-between gap-2"
                  data-testid={`trade-story-event-${ev.kind}`}
                >
                  <span className="font-medium text-foreground">
                    {ev.label}
                  </span>
                  <span className="shrink-0 text-muted-foreground">
                    {formatStoryAsOf(ev.asOf)}
                  </span>
                </li>
              ))}
            </ol>
          )}
          <p className="mt-1 text-[10px] text-muted-foreground">
            Distinto del Historial técnico (audit spine). Trail hint ≠ aplicado.
          </p>
        </details>

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
