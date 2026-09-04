/**
 * Cockpit Mercado — panel DECISIÓN: ¿Qué hago? sobre el valor del gráfico activo.
 *
 * CONTEXTO → ESTADO → ACCIÓN (spec V1.42 §B). Una CTA primaria.
 * Consume EntryOperatingTruth / PositionOperatingTruth / ExecutionState — sin motores nuevos.
 * SEMI: Confirm = única firma. PAPER AUTO (F8): omite Confirm; arm ≠ execute.
 * Ranking ≠ BUY.
 *
 * @see docs/engineering/diseno-mercado-2-0-cockpit-2026-08-27.md §3
 * @see docs/adr/042-operating-excellence.md
 */

import { useEffect, useRef, useState } from "react";
import { OperationalPlanView } from "@/features/mesa/operational-plan-view";
import type {
  InstrumentDailyOpinionV1,
  MesaNextActionKindV1,
  PositionExitCtaKindV1,
} from "@bolsa/shared";
import {
  buildDecisionExplainView,
  buildEntryOperatingTruth,
  buildExecutionState,
  resolveOperatorNextAction,
  buildPositionOperatingTruth,
  mapReconStatusToHealth,
  operatorStageFromCockpitPhase,
  OPERATOR_JOURNEY_STAGE_LABEL,
  RECON_HEALTH_COPY,
} from "@bolsa/shared";
import { openConfirmDrawer } from "@/features/confirm/confirm-drawer";
import { useTradingLayoutStore } from "@/stores/trading-layout-store";
import { cn } from "@/lib/utils";
import {
  useOpsSelfEval,
  portfolioReconStatusFromReport,
} from "@/features/operational-console/use-ops-self-eval";
import {
  mercadoCockpitPosicionPhaseLabel,
  MERCADO_COCKPIT_PHASE_LABEL,
  mercadoCockpitNoLevelsCopy,
  mercadoCockpitPrimaryCta,
  type MercadoCockpitPhase,
} from "@/features/trading/operativa-cockpit-phase";
import { PositionExitDrawerActions } from "@/features/trading/position-exit-drawer-actions";
import { PositionOperationalStarCard } from "@/features/trading/position-operational-star-card";
import {
  mapPovPrimaryActionToExitCtaKind,
  povOperatingStateTone,
  povOperatingStateToneClasses,
} from "@/features/trading/position-decision-surface";
import {
  usePositionOperationalView,
  formatPovPrimaryActionLabel,
} from "@/features/trading/use-position-operational-view";
import { usePositionJourneyReadout } from "@/features/trading/use-position-journey-readout";
import { EntryDecisionSurfaceCard } from "@/features/trading/entry-decision-surface-card";
import {
  entryPhaseTone,
  entryPhaseToneClasses,
} from "@/features/trading/entry-decision-surface";
import { useInstrumentOperationalContext } from "@/features/trading/use-instrument-operational-context";
import { useMesaEntriesBlocked } from "@/features/mesa/use-mesa-entries-blocked";
import { resolvePaperAutoPosture } from "@/features/trading/resolve-paper-auto-posture";
import { useDemoBookPrefs } from "@/features/trading/use-demo-book-prefs";
import { loadAutoArm } from "@/features/trading/demo-book-auto-arm";
import { DecisionSurfacePlacementToggle } from "@/features/trading/decision-surface-placement-toggle";
import { DecisionExplainPanel } from "@/features/trading/decision-explain-panel";
import { useMercadoDecisionSurfacePrefs } from "@/features/trading/use-mercado-decision-surface-prefs";
import { AutoDeskPanel } from "@/features/trading/auto-desk-panel";
import { CABIN_TOUCH_TARGET } from "@/features/trading/cabin-visual";
import {
  CABIN_FOCUS_RING,
  CABIN_INTERACTIVE,
  CABIN_TYPE,
  CABIN_VISUAL_VERSION,
  CabinSectionLabel,
  NextActionHero,
  OperatorCabinLevel,
  OperatorCabinStatus,
} from "@/features/trading/operator-cabin-ui";

type OperativaCockpitCardProps = {
  instrumentId: string | null;
  symbol: string;
  opinion?: InstrumentDailyOpinionV1 | null;
  opinionLoading?: boolean;
  onAddToEstudio?: () => void;
  onPropose?: () => void;
  proposePending?: boolean;
  canPropose?: boolean;
  className?: string;
  /** Last close / mark already in context. Omit → distances hidden. */
  markPrice?: number | null;
};

const EXIT_CTA_KINDS = new Set<MesaNextActionKindV1>([
  "maintain",
  "protect",
  "reduce",
  "exit",
  "review",
]);

function asExitCtaKind(
  kind: MesaNextActionKindV1 | undefined,
): PositionExitCtaKindV1 | undefined {
  if (!kind || !EXIT_CTA_KINDS.has(kind)) return undefined;
  return kind as PositionExitCtaKindV1;
}

function phaseTone(
  phase: MercadoCockpitPhase,
  opts?: {
    povTone?: ReturnType<typeof povOperatingStateTone>;
    entryTone?: ReturnType<typeof entryPhaseTone>;
  },
): string {
  if (phase === "posicion" && opts?.povTone) {
    return povOperatingStateToneClasses(opts.povTone);
  }
  if (opts?.entryTone && phase !== "posicion") {
    return entryPhaseToneClasses(opts.entryTone);
  }
  switch (phase) {
    case "posicion":
      return "border-emerald-600/40 bg-emerald-500/5";
    case "confirmada":
      return "border-teal-600/40 bg-teal-500/5";
    case "disparada":
    case "propuesta":
      return "border-amber-600/40 bg-amber-500/5";
    case "preparada":
      return "border-sky-600/40 bg-sky-500/5";
    case "bloqueada":
      return "border-rose-600/40 bg-rose-500/5";
    case "caducada":
      return "border-amber-700/35 bg-amber-500/5";
    case "descubierto":
      return "border-violet-600/30 bg-violet-500/5";
    default:
      return "border-border/60 bg-muted/15";
  }
}

function SectionLabel({ children }: { children: string }) {
  return <CabinSectionLabel>{children}</CabinSectionLabel>;
}

export function OperativaCockpitCard({
  instrumentId,
  symbol,
  opinion,
  opinionLoading,
  onAddToEstudio,
  onPropose,
  proposePending,
  canPropose = true,
  className,
  markPrice,
}: OperativaCockpitCardProps) {
  const [whyOpen, setWhyOpen] = useState(false);
  const actionFocusRef = useRef<HTMLDivElement>(null);
  const context = useInstrumentOperationalContext(instrumentId);
  const { entriesBlocked, paperDExecuteEnv, killOn } = useMesaEntriesBlocked();
  const bookPrefs = useDemoBookPrefs();
  const paperAuto = resolvePaperAutoPosture({
    bookMode: bookPrefs.mode,
    autoArmed: loadAutoArm().armed,
    paperDExecuteEnv,
  });
  const operationsOpen = useTradingLayoutStore((s) => s.operationsOpen);
  const toggleOperations = useTradingLayoutStore((s) => s.toggleOperations);
  const { placement: decisionSurfacePlacement } =
    useMercadoDecisionSurfacePrefs();

  // V2.41 — land keyboard focus on primary L1 CTA when cabin has an action
  // and focus is still on the document body (first Tab path from shell).
  useEffect(() => {
    if (!instrumentId) return;
    const active = document.activeElement;
    if (active && active !== document.body) return;
    const root = actionFocusRef.current;
    if (!root) return;
    const btn = root.querySelector<HTMLElement>(
      "button:not([disabled]), [role='button']",
    );
    btn?.focus({ preventScroll: true });
  }, [instrumentId, symbol]);

  const { phase, plan, study, position } = context;
  const opsEval = useOpsSelfEval(context.accountId);
  const reconStatus = portfolioReconStatusFromReport(opsEval.data);
  const positionPovResult = usePositionOperationalView(
    phase === "posicion" && position ? position : null,
    reconStatus,
  );
  const positionPov = positionPovResult?.view ?? null;
  const positionJourney = usePositionJourneyReadout({
    position: phase === "posicion" ? position : null,
    view: positionPov,
    autoPosture: paperAuto,
    killOn,
    enabled: phase === "posicion",
  });
  const resolvedMark =
    (typeof markPrice === "number" && Number.isFinite(markPrice)
      ? markPrice
      : null) ??
    (typeof position?.lastPrice === "number" &&
    Number.isFinite(position.lastPrice)
      ? position.lastPrice
      : null);
  const entryTruth =
    study && phase !== "posicion"
      ? buildEntryOperatingTruth({
          study,
          hasOpenPosition: Boolean(position),
          inConfirmQueue: context.inConfirmQueue,
          orderPendingFill: context.orderPendingFill,
          entriesBlocked,
          gateStatus: opinion?.gateStatus ?? null,
          paperAuto,
          markPrice: resolvedMark,
        })
      : null;
  const positionPot =
    phase === "posicion" && position
      ? buildPositionOperatingTruth({
          position,
          study,
          originStudy: context.originStudy,
          portfolioReconStatus: reconStatus,
          orderPending: context.orderPendingFill,
          submitIntent: context.submitIntent,
        })
      : null;
  const executionState =
    positionPot?.execution ??
    (instrumentId != null
      ? buildExecutionState({
          instrumentId,
          pendingOrder: context.orderPendingFill,
          submitIntent: context.submitIntent,
          portfolioReconStatus: reconStatus,
        })
      : null);
  const unknownExecution = executionState?.lifecycle === "unknown";
  const primaryLabel = unknownExecution
    ? (executionState?.nextAction?.label ?? "Ver operaciones")
    : ((positionPov
        ? formatPovPrimaryActionLabel(positionPov.primaryAction)
        : null) ??
      positionPot?.primaryCta.label ??
      entryTruth?.primaryCta.label ??
      mercadoCockpitPrimaryCta(phase));
  const noLevelsCopy = mercadoCockpitNoLevelsCopy(phase);
  const reconHealthFromStatus =
    reconStatus == null ? null : mapReconStatusToHealth(reconStatus);
  const reconHealth =
    positionPov?.operatingState === "RECONCILIATION_DRIFT"
      ? "CRITICAL"
      : positionPov?.operatingState === "RECONCILIATION_ERROR"
        ? "ATTENTION"
        : reconHealthFromStatus;
  const phaseLabel =
    phase === "posicion"
      ? mercadoCockpitPosicionPhaseLabel(positionPov?.operatingState)
      : MERCADO_COCKPIT_PHASE_LABEL[phase];
  const operatorStage = operatorStageFromCockpitPhase(phase);
  const operatorStageLabel = OPERATOR_JOURNEY_STAGE_LABEL[operatorStage];
  const templateId =
    position?.operational &&
    typeof (position.operational as { templateId?: unknown }).templateId ===
      "string"
      ? ((position.operational as { templateId?: string }).templateId ?? null)
      : ((study as { templateId?: string } | null)?.templateId ?? null);

  const potExitKind =
    positionPov != null
      ? asExitCtaKind(
          mapPovPrimaryActionToExitCtaKind(positionPov.primaryAction),
        )
      : asExitCtaKind(positionPot?.primaryCta.kind);
  const showOpsFromPot =
    Boolean(positionPot) &&
    potExitKind === "review" &&
    /operaciones/i.test(positionPot!.primaryCta.label);

  /** SEMI: cola Confirm. AUTO (F8): omite firma — no abrir Confirm. */
  const inConfirmPath =
    paperAuto.requiresHumanConfirm &&
    (phase === "propuesta" ||
      (phase === "disparada" && context.confirmQueueCount > 0));
  const showPropose =
    paperAuto.requiresHumanConfirm &&
    !unknownExecution &&
    !inConfirmPath &&
    (phase === "preparada" || phase === "disparada") &&
    Boolean(onPropose);
  const showConfirm = !unknownExecution && inConfirmPath;
  const showAutoPosture =
    paperAuto.autoActive &&
    !unknownExecution &&
    (phase === "preparada" || phase === "disparada" || phase === "propuesta");
  const showOpsCta =
    unknownExecution ||
    showOpsFromPot ||
    (!unknownExecution && phase === "confirmada");

  const povTone =
    phase === "posicion" && positionPov
      ? povOperatingStateTone(positionPov.operatingState)
      : undefined;
  const entryTone =
    entryTruth != null
      ? entryPhaseTone(entryTruth.phase, {
          entriesBlocked: entryTruth.entriesBlocked,
          gateStatus: entryTruth.gateStatus,
        })
      : undefined;

  const explainView =
    study != null
      ? buildDecisionExplainView({
          study,
          entriesBlocked: entryTruth?.entriesBlocked ?? entriesBlocked,
          gateStatus: entryTruth?.gateStatus ?? opinion?.gateStatus ?? null,
          phase:
            entryTruth?.phase ?? (phase === "posicion" ? "posicion" : phase),
          secondaryConditions: positionPot?.secondaryConditions ?? [],
          asOf:
            entryTruth?.asOf ??
            positionPot?.asOf ??
            opinion?.asOfBarDate ??
            null,
          source: opinion?.source ?? null,
          markPrice: resolvedMark,
        })
      : null;

  if (!instrumentId) {
    return (
      <div
        className={cn(
          "space-y-2 rounded-md border border-border/60 px-3 py-2",
          className,
        )}
        data-testid="operativa-cockpit"
        data-phase="sin_contexto"
        data-cabin-composition="4-levels"
        data-cabin-visual={CABIN_VISUAL_VERSION}
      >
        <OperatorCabinLevel level={1} showQuestion={false}>
          <NextActionHero
            action={resolveOperatorNextAction({
              kind: "cockpit_phase",
              phase: "sin_contexto",
            })}
          />
        </OperatorCabinLevel>
        <OperatorCabinStatus kind="empty">
          {noLevelsCopy ?? "Selecciona un valor en ESTUDIO para decidir."}
        </OperatorCabinStatus>
      </div>
    );
  }

  return (
    <section
      className={cn(
        "min-w-0 space-y-2 rounded-md border px-3 py-2",
        phaseTone(phase, { povTone, entryTone }),
        className,
      )}
      data-testid="operativa-cockpit"
      data-cabin-composition="4-levels"
      data-cabin-density="v2.25"
      data-cabin-visual={CABIN_VISUAL_VERSION}
      data-phase={phase}
      data-instrument-id={instrumentId}
      data-symbol={symbol}
      data-execution-lifecycle={executionState?.lifecycle ?? undefined}
      data-position-id={positionPov?.positionId ?? position?.id ?? undefined}
      data-trade-plan-id={positionPov?.tradePlanId ?? undefined}
      data-decision-id={positionPov?.decisionId ?? undefined}
      aria-label={`DECISIÓN · ${symbol}`}
    >
      {/* CONTEXTO */}
      <div className="space-y-1" data-testid="decision-contexto">
        <SectionLabel>Contexto</SectionLabel>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold tracking-tight">
              {symbol}
            </p>
            <p className={CABIN_TYPE.meta}>
              Universo: {context.inEstudio ? "Estudio" : "fuera de Estudio"}
              {opinion?.asOfBarDate ? ` · as-of ${opinion.asOfBarDate}` : null}
            </p>
          </div>
          <div className="flex shrink-0 flex-wrap items-center gap-1">
            {reconHealth ? (
              <span
                className={cn(
                  "rounded border px-1.5 py-0.5 font-semibold tracking-wide",
                  CABIN_TYPE.meta,
                  reconHealth === "CRITICAL"
                    ? "border-rose-600/50 bg-rose-500/10"
                    : reconHealth === "ATTENTION"
                      ? "border-amber-600/45 bg-amber-500/10"
                      : "border-emerald-600/40 bg-emerald-500/10",
                )}
                data-testid="operativa-cockpit-recon"
                data-recon={reconHealth}
              >
                {RECON_HEALTH_COPY[reconHealth]}
              </span>
            ) : null}
            <span
              className={cn(
                "rounded border border-border/70 bg-background/60 px-1.5 py-0.5 font-semibold uppercase tracking-wide",
                CABIN_TYPE.meta,
              )}
              data-testid="operativa-cockpit-phase"
              title={`${operatorStageLabel} · ${phaseLabel}`}
            >
              {phase === "posicion" ? phaseLabel : operatorStageLabel}
            </span>
          </div>
        </div>
      </div>

      {/* ESTADO */}
      <div className="space-y-1.5" data-testid="decision-estado">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <SectionLabel>Estado</SectionLabel>
          <DecisionSurfacePlacementToggle />
        </div>
        {context.loading ? (
          <OperatorCabinStatus kind="loading">
            Cargando plan…
          </OperatorCabinStatus>
        ) : decisionSurfacePlacement === "chart" &&
          (phase === "posicion" && position ? true : Boolean(entryTruth)) ? (
          <p
            className="text-[11px] leading-snug text-muted-foreground"
            data-testid="decision-surface-on-chart-hint"
          >
            Estado operativo en el gráfico · ACCIÓN sigue aquí
          </p>
        ) : phase === "posicion" && position ? (
          <PositionOperationalStarCard
            position={position}
            symbol={symbol}
            portfolioReconStatus={reconStatus}
            view={positionPov ?? undefined}
            viewSource={positionPovResult?.source}
            journey={positionJourney}
            onOpenWhy={() => setWhyOpen(true)}
          />
        ) : entryTruth ? (
          <EntryDecisionSurfaceCard
            truth={entryTruth}
            symbol={symbol}
            orderPendingFill={context.orderPendingFill}
            submitIntent={context.submitIntent}
            onOpenWhy={() => setWhyOpen(true)}
          />
        ) : context.showsPlanLevels ? (
          <OperationalPlanView
            plan={plan}
            testId={`operativa-cockpit-plan-${symbol}`}
          />
        ) : (
          <div className="space-y-1.5">
            <OperatorCabinLevel level={1} showQuestion={false}>
              <NextActionHero
                action={resolveOperatorNextAction({
                  kind: "cockpit_phase",
                  phase,
                })}
              />
            </OperatorCabinLevel>
            <OperatorCabinStatus
              kind="empty"
              testId="operativa-cockpit-no-levels"
            >
              {noLevelsCopy ?? plan.emptyCopy}
            </OperatorCabinStatus>
          </div>
        )}
      </div>

      {/* ACCIÓN — L1 companion (CTA firma / prepare) */}
      <div
        ref={actionFocusRef}
        className="flex flex-col gap-1"
        data-testid="decision-accion"
        data-cabin-level={1}
      >
        <SectionLabel>Acción</SectionLabel>

        {showOpsCta ? (
          <button
            type="button"
            className={cn(
              CABIN_TOUCH_TARGET,
              "w-full justify-start rounded-md border border-amber-700/35 bg-amber-500/10 px-3 text-left text-xs font-medium hover:bg-amber-500/20",
              CABIN_FOCUS_RING,
            )}
            onClick={() => {
              if (!operationsOpen) toggleOperations();
            }}
            data-testid="operativa-cockpit-cta-operaciones"
            title={
              unknownExecution
                ? "Orden desconocida — no reenviar. Revisar Operaciones."
                : "Firma hecha · fill pendiente — mira Operaciones abajo"
            }
          >
            {primaryLabel}
          </button>
        ) : null}

        {!unknownExecution &&
        !showOpsFromPot &&
        phase === "descubierto" &&
        onAddToEstudio ? (
          <button
            type="button"
            className={cn(
              CABIN_TOUCH_TARGET,
              "w-full justify-start rounded-md border border-violet-600/35 bg-violet-500/10 px-3 text-left text-xs font-medium hover:bg-violet-500/20",
              CABIN_FOCUS_RING,
            )}
            onClick={onAddToEstudio}
            data-testid="operativa-cockpit-cta-estudio"
          >
            {primaryLabel}
          </button>
        ) : null}

        {showPropose ? (
          <button
            type="button"
            disabled={
              proposePending ||
              !canPropose ||
              entryTruth?.primaryCta.kind === "none"
            }
            className={cn(
              CABIN_TOUCH_TARGET,
              "w-full justify-start rounded-md border border-emerald-700/35 bg-emerald-500/10 px-3 text-left text-xs font-medium text-emerald-950 hover:bg-emerald-500/20 disabled:opacity-50 dark:text-emerald-50",
              CABIN_FOCUS_RING,
            )}
            onClick={onPropose}
            data-testid="operativa-cockpit-cta-preparar"
            title="Propose → cola Confirm · Ranking ≠ BUY · Confirm = firma"
          >
            {proposePending ? "Proponiendo…" : primaryLabel}
          </button>
        ) : null}

        {showAutoPosture ? (
          <div
            className="rounded-md border border-sky-700/35 bg-sky-500/10 px-3 py-2 text-left text-xs font-medium"
            data-testid="operativa-cockpit-auto-posture"
            title={paperAuto.modeDetail}
          >
            {paperAuto.executeEligible
              ? "ENTRADA LISTA · AUTO ejecutará si está armado"
              : "ENTRADA LISTA · AUTO armado · ejecución off"}
            <p className={cn("mt-0.5 font-normal", CABIN_TYPE.meta)}>
              Armado ≠ ejecución · puedes intervenir
            </p>
          </div>
        ) : null}

        {showConfirm ? (
          <button
            type="button"
            className={cn(
              CABIN_TOUCH_TARGET,
              "w-full justify-start rounded-md border border-amber-700/35 bg-amber-500/10 px-3 text-left text-xs font-medium hover:bg-amber-500/20",
              CABIN_FOCUS_RING,
            )}
            onClick={() => openConfirmDrawer()}
            data-testid="operativa-cockpit-cta-confirm"
            title="Confirm es la única firma — no ejecuta desde DECISIÓN"
          >
            {primaryLabel}
            {context.confirmQueueCount > 1
              ? ` (${context.confirmQueueCount})`
              : ""}
          </button>
        ) : null}

        {!unknownExecution &&
        !showOpsFromPot &&
        phase === "posicion" &&
        position ? (
          <PositionExitDrawerActions
            position={position}
            portfolioReconStatus={reconStatus}
            primaryOnly
            primaryCtaKind={potExitKind}
          />
        ) : null}

        {!unknownExecution &&
        (phase === "vigilar" ||
          phase === "bloqueada" ||
          phase === "caducada") ? (
          <button
            type="button"
            className={cn(
              CABIN_TOUCH_TARGET,
              "w-fit justify-start rounded-md border border-border px-3 text-[11px] font-medium hover:bg-accent",
              CABIN_FOCUS_RING,
            )}
            onClick={() => setWhyOpen(true)}
            data-testid={
              phase === "vigilar"
                ? "operativa-cockpit-cta-vigilar"
                : `operativa-cockpit-cta-${phase}`
            }
            title={
              phase === "bloqueada"
                ? "Plan bloqueado — mira el motivo en ¿Por qué?"
                : phase === "caducada"
                  ? "Plan caducado — niveles residuales no autorizan"
                  : "Ya está en Estudio: sin disparador todavía — mira el análisis"
            }
          >
            {primaryLabel}
          </button>
        ) : null}
      </div>

      {/* L4 — ¿Por qué? · AUTO (plegados) */}
      <OperatorCabinLevel
        level={4}
        showQuestion={false}
        className="border-t border-border/50 pt-1.5"
      >
        <button
          type="button"
          className={CABIN_INTERACTIVE}
          onClick={() => setWhyOpen((v) => !v)}
          data-testid="operativa-cockpit-why"
        >
          {whyOpen ? "Ocultar ¿Por qué?" : "¿Por qué?"}
        </button>
        {whyOpen ? (
          <DecisionExplainPanel view={explainView} loading={opinionLoading} />
        ) : null}
        <AutoDeskPanel templateId={templateId} journey={positionJourney} />
      </OperatorCabinLevel>
    </section>
  );
}
