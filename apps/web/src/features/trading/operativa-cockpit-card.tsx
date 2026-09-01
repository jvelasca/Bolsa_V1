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

import { useState } from "react";
import { OperationalPlanView } from "@/features/mesa/operational-plan-view";
import type {
  InstrumentDailyOpinionV1,
  MesaNextActionKindV1,
  PositionExitCtaKindV1,
} from "@bolsa/shared";
import {
  buildEntryOperatingTruth,
  buildExecutionState,
  buildPositionOperatingTruth,
  mapMesaStatusDimensions,
  mapReconStatusToHealth,
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
import { PositionOperatingSummary } from "@/features/trading/position-operating-summary";
import { usePositionOperationalView } from "@/features/trading/use-position-operational-view";
import { EntryOperatingSummary } from "@/features/trading/entry-operating-summary";
import { ExitRouteView } from "@/features/trading/exit-route-view";
import { useInstrumentOperationalContext } from "@/features/trading/use-instrument-operational-context";
import { useMesaEntriesBlocked } from "@/features/mesa/use-mesa-entries-blocked";
import { resolvePaperAutoPosture } from "@/features/trading/resolve-paper-auto-posture";
import { useDemoBookPrefs } from "@/features/trading/use-demo-book-prefs";
import { loadAutoArm } from "@/features/trading/demo-book-auto-arm";

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

function phaseTone(phase: MercadoCockpitPhase): string {
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
  return (
    <p className="text-[9px] font-semibold uppercase tracking-wider text-muted-foreground/90">
      {children}
    </p>
  );
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
}: OperativaCockpitCardProps) {
  const [whyOpen, setWhyOpen] = useState(false);
  const context = useInstrumentOperationalContext(instrumentId);
  const { entriesBlocked, paperDExecuteEnv } = useMesaEntriesBlocked();
  const bookPrefs = useDemoBookPrefs();
  const paperAuto = resolvePaperAutoPosture({
    bookMode: bookPrefs.mode,
    autoArmed: loadAutoArm().armed,
    paperDExecuteEnv,
  });
  const operationsOpen = useTradingLayoutStore((s) => s.operationsOpen);
  const toggleOperations = useTradingLayoutStore((s) => s.toggleOperations);

  const { phase, plan, study, position } = context;
  const opsEval = useOpsSelfEval(context.accountId);
  const reconStatus = portfolioReconStatusFromReport(opsEval.data);
  const positionPov = usePositionOperationalView(
    phase === "posicion" && position ? position : null,
    reconStatus,
  );
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
    : (positionPot?.primaryCta.label ??
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

  const potExitKind = asExitCtaKind(positionPot?.primaryCta.kind);
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

  if (!instrumentId) {
    return (
      <div
        className={cn(
          "rounded-md border border-border/60 px-3 py-2 text-xs text-muted-foreground",
          className,
        )}
        data-testid="operativa-cockpit"
        data-phase="sin_contexto"
      >
        {noLevelsCopy}
      </div>
    );
  }

  return (
    <section
      className={cn(
        "space-y-2 rounded-md border px-3 py-2",
        phaseTone(phase),
        className,
      )}
      data-testid="operativa-cockpit"
      data-phase={phase}
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
            <p className="text-[10px] text-muted-foreground">
              Universo: {context.inEstudio ? "Estudio" : "fuera de Estudio"}
              {opinion?.asOfBarDate ? ` · as-of ${opinion.asOfBarDate}` : null}
            </p>
          </div>
          <div className="flex shrink-0 flex-wrap items-center gap-1">
            {reconHealth ? (
              <span
                className={cn(
                  "rounded border px-1.5 py-0.5 text-[10px] font-semibold tracking-wide",
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
              className="rounded border border-border/70 bg-background/60 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide"
              data-testid="operativa-cockpit-phase"
            >
              {phaseLabel}
            </span>
          </div>
        </div>
      </div>

      {/* ESTADO */}
      <div className="space-y-1.5" data-testid="decision-estado">
        <SectionLabel>Estado</SectionLabel>
        {context.loading ? (
          <p className="text-[11px] text-muted-foreground">Cargando plan…</p>
        ) : phase === "posicion" && position ? (
          <>
            <PositionOperationalStarCard
              position={position}
              portfolioReconStatus={reconStatus}
            />
            <PositionOperatingSummary
              pot={positionPot}
              position={position}
              portfolioReconStatus={reconStatus}
              orderPending={context.orderPendingFill}
              submitIntent={context.submitIntent}
            />
            {context.showsPlanLevels ? (
              <OperationalPlanView
                plan={plan}
                omitLiveMetrics
                testId={`operativa-cockpit-plan-${symbol}`}
              />
            ) : null}
            <ExitRouteView
              truth={positionPot?.operational ?? null}
              position={position}
              study={study}
              originStudy={context.originStudy}
            />
          </>
        ) : entryTruth ? (
          <>
            <EntryOperatingSummary
              truth={entryTruth}
              orderPendingFill={context.orderPendingFill}
              submitIntent={context.submitIntent}
            />
            {context.showsPlanLevels ? (
              <OperationalPlanView
                plan={plan}
                testId={`operativa-cockpit-plan-${symbol}`}
              />
            ) : null}
          </>
        ) : context.showsPlanLevels ? (
          <OperationalPlanView
            plan={plan}
            testId={`operativa-cockpit-plan-${symbol}`}
          />
        ) : (
          <p
            className="text-[11px] leading-snug text-muted-foreground"
            data-testid="operativa-cockpit-no-levels"
          >
            {noLevelsCopy ?? plan.emptyCopy}
          </p>
        )}
      </div>

      {/* ACCIÓN — una CTA primaria */}
      <div className="flex flex-col gap-1" data-testid="decision-accion">
        <SectionLabel>Acción</SectionLabel>

        {showOpsCta ? (
          <button
            type="button"
            className="rounded-md border border-amber-700/35 bg-amber-500/10 px-2 py-1.5 text-left text-xs font-medium hover:bg-amber-500/20"
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
            className="rounded-md border border-violet-600/35 bg-violet-500/10 px-2 py-1.5 text-left text-xs font-medium hover:bg-violet-500/20"
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
            className="rounded-md border border-emerald-700/35 bg-emerald-500/10 px-2 py-1.5 text-left text-xs font-medium text-emerald-950 hover:bg-emerald-500/20 disabled:opacity-50 dark:text-emerald-50"
            onClick={onPropose}
            data-testid="operativa-cockpit-cta-preparar"
            title="Propose → cola Confirm · Ranking ≠ BUY · Confirm = firma"
          >
            {proposePending ? "Proponiendo…" : primaryLabel}
          </button>
        ) : null}

        {showAutoPosture ? (
          <div
            className="rounded-md border border-sky-700/35 bg-sky-500/10 px-2 py-1.5 text-left text-xs font-medium"
            data-testid="operativa-cockpit-auto-posture"
            title={paperAuto.modeDetail}
          >
            {paperAuto.statusBadge ?? primaryLabel}
            <p className="mt-0.5 text-[10px] font-normal text-muted-foreground">
              {paperAuto.executeEligible
                ? "Sin Confirm · misma spine SEMI (paper)"
                : "Arm ≠ execute · PAPER_D_EXECUTE off"}
            </p>
          </div>
        ) : null}

        {showConfirm ? (
          <button
            type="button"
            className="rounded-md border border-amber-700/35 bg-amber-500/10 px-2 py-1.5 text-left text-xs font-medium hover:bg-amber-500/20"
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
            className="w-fit rounded-md border border-border px-2 py-1 text-[11px] font-medium hover:bg-accent"
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

      {/* Avanzado colapsado: Gate · DS-05 · TTL · UNKNOWN detail */}
      <div className="border-t border-border/50 pt-1.5">
        <button
          type="button"
          className="text-[10px] font-medium text-foreground/90 underline-offset-2 hover:underline"
          onClick={() => setWhyOpen((v) => !v)}
          data-testid="operativa-cockpit-why"
        >
          {whyOpen ? "Ocultar ¿Por qué?" : "¿Por qué?"}
        </button>
        {whyOpen ? (
          <dl
            className="mt-1.5 space-y-1 text-[10px] text-muted-foreground"
            data-testid="operativa-cockpit-why-body"
          >
            <div className="flex justify-between gap-2">
              <dt>Dictamen</dt>
              <dd className="font-medium text-foreground">
                {opinionLoading
                  ? "…"
                  : (opinion?.stance ?? study?.opinion ?? "—")}
              </dd>
            </div>
            <div className="flex justify-between gap-2">
              <dt>Gate</dt>
              <dd className="font-medium text-foreground">
                {opinion?.gateStatus ?? "—"}
              </dd>
            </div>
            <div className="flex justify-between gap-2">
              <dt>Plan</dt>
              <dd className="font-medium text-foreground">
                {plan.phaseLabel ||
                  (study?.tradePlanStatus
                    ? mapMesaStatusDimensions({
                        tradePlanStatus: study.tradePlanStatus,
                      }).operational
                    : "—")}
              </dd>
            </div>
            <div className="flex justify-between gap-2">
              <dt>Fuente opinión</dt>
              <dd className="font-medium text-foreground">
                {opinion?.source ?? "—"}
              </dd>
            </div>
            {executionState?.lifecycle === "unknown" ? (
              <div className="flex justify-between gap-2">
                <dt>Orden</dt>
                <dd className="font-medium text-amber-800 dark:text-amber-200">
                  UNKNOWN — no reenviar · reconciliar
                </dd>
              </div>
            ) : null}
            <p className="pt-0.5 leading-snug">
              {paperAuto.autoActive
                ? `PAPER AUTO · ${paperAuto.statusBadge ?? "armado"} · Ranking ≠ BUY · trail ≠ currentStop.`
                : "La IA no firma. Confirm es la única firma · Ranking ≠ BUY · trail = propuesta."}
            </p>
          </dl>
        ) : null}
      </div>
    </section>
  );
}
