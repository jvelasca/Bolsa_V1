/**
 * V1.63 — Presentación compacta compartida Entry/Position Decision Surface.
 * Usada en panel (full) y HUD del gráfico (hud). Display-only — no firma · no BUY.
 */

import { useState } from "react";
import type {
  EntryOperatingTruthV1,
  PositionDto,
  PositionJourneyReadoutV1,
  PositionOperationalStateV1,
  PositionOperationalViewV1,
  SubmitIntentListItemV1,
} from "@bolsa/shared";
import {
  assertNever,
  buildExecutionState,
  buildOperatorDecision,
  buildOperatorFourAnswers,
  buildOperatorPositionPlan,
  buildOperatorPositionPlanFromDecision,
  buildOperatorRiskBox,
  buildPositionDecisionFromDto,
  buildPositionReductionReadout,
  formatOperatorAutoHonesty,
  formatPositionDecisionPhrase,
  reconPhraseFromPortfolioStatus,
  resolveOperatorNextAction,
} from "@bolsa/shared";
import { cn } from "@/lib/utils";
import { formatPrice } from "@/features/charts/chart-utils";
import {
  entryDecisionLabel,
  entryExecutionStateLabel,
  entryPhaseHeadline,
  entryPhaseTone,
  entryPhaseToneClasses,
  formatEntryLevel,
} from "@/features/trading/entry-decision-surface";
import {
  formatLevel,
  formatPctSigned,
  formatRSigned,
  povExecutionStateLabel,
  povOperatingStateHeadline,
  povOperatingStateTone,
  povOperatingStateToneClasses,
} from "@/features/trading/position-decision-surface";
import {
  formatPovPrimaryActionLabel,
  usePositionOperationalView,
} from "@/features/trading/use-position-operational-view";
import {
  CABIN_INTERACTIVE,
  CABIN_KV_GRID,
  CABIN_TYPE,
  CABIN_VISUAL_VERSION,
  CabinSectionLabel,
  NextActionHero,
  OperatorCabinLevel,
  OperatorFourAnswersBlock,
  OperatorPositionPlan,
  OperatorProtectionLine,
  OperatorRiskBox,
  cabinNumClass,
} from "@/features/trading/operator-cabin-ui";

type Density = "full" | "hud";

type EntryCompactProps = {
  variant: "entry";
  density?: Density;
  truth: EntryOperatingTruthV1;
  symbol: string;
  orderPendingFill?: boolean;
  submitIntent?: SubmitIntentListItemV1 | null;
  onOpenWhy?: () => void;
  className?: string;
  testId?: string;
};

type PositionCompactProps = {
  variant: "position";
  density?: Density;
  position: PositionDto;
  symbol: string;
  portfolioReconStatus?: string | null;
  /** Evita doble hook cuando el padre ya resolvió la vista. */
  view?: PositionOperationalViewV1;
  viewSource?: "canonical" | "blob";
  /** V2.0 — journey HUD (lifecycle + risk). */
  journey?: PositionJourneyReadoutV1 | null;
  onOpenWhy?: () => void;
  className?: string;
  testId?: string;
};

export type DecisionSurfaceCompactProps =
  | EntryCompactProps
  | PositionCompactProps;

function SectionLabel({ children }: { children: string }) {
  return <CabinSectionLabel>{children}</CabinSectionLabel>;
}

function formatMoney(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return "—";
  return formatPrice(value);
}

function formatDistance(
  entry: number | null | undefined,
  mark: number | null | undefined,
): string | null {
  if (
    entry == null ||
    mark == null ||
    !Number.isFinite(entry) ||
    !Number.isFinite(mark)
  ) {
    return null;
  }
  const delta = mark - entry;
  const sign = delta > 0 ? "+" : "";
  const pct = entry === 0 ? null : (delta / entry) * 100;
  const pctPart =
    pct != null && Number.isFinite(pct) ? ` (${sign}${pct.toFixed(2)}%)` : "";
  return `${sign}${delta.toFixed(2)}${pctPart}`;
}

function formatOperatingStatePhrase(
  state: PositionOperationalStateV1,
  portfolioReconStatus?: string | null,
  position?: PositionDto,
): string {
  const decision =
    position != null
      ? buildPositionDecisionFromDto(position, { portfolioReconStatus })
      : null;
  if (decision) {
    if (state === "T2_READY" && decision.nextEvent === "T2") {
      return `${formatPositionDecisionPhrase(decision)} · mesa MONITOR.`;
    }
    if (state === "T2_EXECUTED") {
      return "T2 ejecutado · posición parcial.";
    }
    if (state === "T1_READY" && decision.nextEvent === "T1") {
      return formatPositionDecisionPhrase(decision);
    }
    if (state === "T1_EXECUTED") {
      return "T1 ejecutado · posición parcial.";
    }
  }

  switch (state) {
    case "T2_READY":
      return "T2 alcanzado · mesa MONITOR.";
    case "T2_EXECUTED":
      return "T2 ejecutado · posición parcial.";
    case "T1_READY":
      return "T1 disparado · pendiente de ejecutar.";
    case "T1_EXECUTED":
      return "T1 ejecutado · posición parcial.";
    case "PROTECT_REQUIRED":
      return "Protección requerida · falta stop operativo.";
    case "OPEN_UNPROTECTED":
      return "Sin stop técnico · protección de emergencia (−5 %) disponible.";
    case "EXIT_REQUIRED":
      return "Salida requerida · stop alcanzado o inminente.";
    case "EXIT_PENDING":
      return "Salida pendiente de confirmación.";
    case "TRAILING":
      return "Trailing activo · stop en seguimiento.";
    case "PROTECTED":
      return "Posición protegida · stop operativo vigente.";
    case "PARTIALLY_REDUCED":
      return "Posición reducida parcialmente.";
    case "CLOSED":
      return "Posición cerrada.";
    case "RECONCILIATION_DRIFT":
      return (
        reconPhraseFromPortfolioStatus(portfolioReconStatus ?? "drift") ??
        "Discrepancia de cartera · requiere acción."
      );
    case "RECONCILIATION_ERROR":
      return (
        reconPhraseFromPortfolioStatus("unavailable") ??
        "Reconciliación no disponible."
      );
    default:
      return assertNever(state);
  }
}

function formatStopDelta(delta: number | null | undefined): string | null {
  if (delta == null || !Number.isFinite(delta)) return null;
  const sign = delta > 0 ? "+" : "";
  return `${sign}${delta.toFixed(2)}`;
}

function EntryCompactBody({
  truth,
  symbol,
  orderPendingFill,
  submitIntent,
  onOpenWhy,
  density,
}: Omit<EntryCompactProps, "variant" | "className" | "testId">) {
  const { plan, sizing, phase, primaryCta } = truth;
  const executionState = buildExecutionState({
    instrumentId: truth.instrumentId,
    asOf: truth.asOf,
    pendingOrder: orderPendingFill ?? false,
    submitIntent: submitIntent ?? null,
  });
  const decisionLabel = entryDecisionLabel(primaryCta);
  const executionLabel = entryExecutionStateLabel(
    phase,
    primaryCta,
    executionState,
  );
  const qty =
    sizing.quantity != null && Number.isFinite(sizing.quantity)
      ? `${sizing.quantity}`
      : "—";
  const headline = entryPhaseHeadline(phase);
  const hud = density === "hud";
  const nextAction = resolveOperatorNextAction({ kind: "entry", truth });
  const fourAnswers = buildOperatorFourAnswers({
    phase,
    thesisSummary: headline,
    entry: plan.entry,
    stop: plan.stopVigente,
    triggerLabel: truth.triggerLabel,
    riskAmount: sizing.riskAmount,
    riskR: sizing.riskR,
    target1: plan.target1,
    target2: plan.target2,
  });
  const riskBox = buildOperatorRiskBox({
    entry: plan.entry,
    stop: plan.stopVigente,
    lossAtStop: sizing.riskAmount,
    maxLoss: sizing.riskAmount,
    target1: plan.target1,
    target2: plan.target2,
    quantity: sizing.quantity,
    positionValue: sizing.positionValue,
    riskPct: sizing.riskR != null ? sizing.riskR : null,
  });
  const [advancedOpen, setAdvancedOpen] = useState(false);

  return (
    <>
      {!hud ? (
        <OperatorCabinLevel level={1} showQuestion={false}>
          <NextActionHero action={nextAction} />
        </OperatorCabinLevel>
      ) : null}

      <div className="space-y-1">
        {!hud ? <SectionLabel>Oportunidad</SectionLabel> : null}
        <div
          className="space-y-0.5"
          data-testid="operativa-cockpit-entry-state"
          data-phase={phase}
          data-entry-phase={phase}
        >
          <p
            className={cn(
              "font-semibold leading-snug text-foreground",
              CABIN_TYPE.operativa,
            )}
            data-testid="entry-decision-headline"
          >
            {symbol} · {headline}
          </p>
          <p
            className={cn(CABIN_TYPE.meta, hud && "line-clamp-2")}
            data-testid="entry-operating-phrase"
          >
            {truth.phrase}
          </p>
        </div>

        <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5">
          <p className={CABIN_TYPE.meta}>
            <span className="font-medium text-foreground">{symbol}</span>
          </p>
          <p className={cabinNumClass()} data-testid="entry-operating-trigger">
            Trigger {truth.triggerLabel}
          </p>
        </div>

        {hud ? (
          <p className={cn(cabinNumClass({ size: "meta" }))}>
            <span data-testid="entry-decision-entry">
              E {formatEntryLevel(plan.entry)}
            </span>
            {" · "}
            <span data-testid="entry-decision-stop">
              S {formatEntryLevel(plan.stopVigente)}
            </span>
            {" · "}
            <span data-testid="entry-decision-t1">
              T1 {formatEntryLevel(plan.target1)}
            </span>
          </p>
        ) : (
          <>
            <OperatorCabinLevel level={2}>
              <OperatorRiskBox box={riskBox} />
              <dl className={CABIN_KV_GRID}>
                <div className="flex justify-between gap-2">
                  <dt>Entrada</dt>
                  <dd
                    className={cabinNumClass()}
                    data-testid="entry-decision-entry"
                  >
                    {formatEntryLevel(plan.entry)}
                  </dd>
                </div>
                {plan.currentPrice != null &&
                Number.isFinite(plan.currentPrice) ? (
                  <div className="flex justify-between gap-2">
                    <dt>Precio actual</dt>
                    <dd
                      className={cabinNumClass()}
                      data-testid="entry-decision-mark"
                    >
                      {formatEntryLevel(plan.currentPrice)}
                    </dd>
                  </div>
                ) : null}
                {formatDistance(plan.entry, plan.currentPrice) ? (
                  <div className="flex justify-between gap-2">
                    <dt>Distancia</dt>
                    <dd
                      className={cabinNumClass()}
                      data-testid="entry-decision-distance"
                    >
                      {formatDistance(plan.entry, plan.currentPrice)}
                    </dd>
                  </div>
                ) : null}
                <div className="flex justify-between gap-2">
                  <dt>Stop</dt>
                  <dd
                    className={cabinNumClass()}
                    data-testid="entry-decision-stop"
                  >
                    {formatEntryLevel(plan.stopVigente)}
                  </dd>
                </div>
                <div className="flex justify-between gap-2">
                  <dt>Tamaño</dt>
                  <dd className={cabinNumClass()}>{qty} acciones</dd>
                </div>
                <div className="flex justify-between gap-2">
                  <dt>Riesgo</dt>
                  <dd
                    className={cabinNumClass()}
                    data-testid="entry-decision-risk"
                  >
                    {formatMoney(sizing.riskAmount)}
                    {sizing.riskR != null && Number.isFinite(sizing.riskR)
                      ? ` · ${sizing.riskR.toFixed(2)}R`
                      : ""}
                  </dd>
                </div>
                {truth.expiryLabel ? (
                  <div className="col-span-2 flex justify-between gap-2">
                    <dt>Vigencia</dt>
                    <dd className={cn(CABIN_TYPE.operativa, "font-medium")}>
                      {truth.expiryLabel}
                    </dd>
                  </div>
                ) : null}
              </dl>
            </OperatorCabinLevel>

            <OperatorCabinLevel level={3}>
              <dl className={CABIN_KV_GRID}>
                <div className="flex justify-between gap-2">
                  <dt>T1</dt>
                  <dd
                    className={cabinNumClass()}
                    data-testid="entry-decision-t1"
                  >
                    {formatEntryLevel(plan.target1)}
                  </dd>
                </div>
                <div className="flex justify-between gap-2">
                  <dt>T2</dt>
                  <dd
                    className={cabinNumClass()}
                    data-testid="entry-decision-t2"
                  >
                    {formatEntryLevel(plan.target2)}
                  </dd>
                </div>
              </dl>
            </OperatorCabinLevel>

            <OperatorCabinLevel level={4}>
              <button
                type="button"
                className={CABIN_INTERACTIVE}
                onClick={() => setAdvancedOpen((v) => !v)}
                data-testid="entry-advanced-toggle"
              >
                {advancedOpen ? "Ocultar detalles" : "Detalles avanzados"}
              </button>
              {advancedOpen ? (
                <OperatorFourAnswersBlock answers={fourAnswers} />
              ) : null}
              {onOpenWhy ? (
                <button
                  type="button"
                  className={CABIN_INTERACTIVE}
                  onClick={onOpenWhy}
                  data-testid="entry-decision-why-toggle"
                >
                  ¿Por qué?
                </button>
              ) : null}
            </OperatorCabinLevel>
          </>
        )}
      </div>

      {hud ? (
        <div
          className="space-y-0.5 pt-0.5"
          data-testid="entry-decision-action-block"
        >
          <div
            className={cn(
              "flex flex-wrap items-baseline justify-between gap-2",
              CABIN_TYPE.meta,
            )}
          >
            <p data-testid="operativa-cockpit-entry-action">
              <span className="text-muted-foreground">Decisión</span>{" "}
              <span className="font-semibold text-foreground">
                {decisionLabel}
              </span>
            </p>
            <p data-testid="entry-decision-execution">
              <span className="text-muted-foreground">Ejecución</span>{" "}
              <span className="font-medium text-foreground">
                {executionLabel}
              </span>
            </p>
          </div>
        </div>
      ) : (
        <div
          className="space-y-0.5 border-t border-border/40 pt-1.5"
          data-testid="entry-decision-action-block"
        >
          <div
            className={cn(
              "flex flex-wrap items-baseline justify-between gap-2",
              CABIN_TYPE.meta,
            )}
          >
            <p data-testid="operativa-cockpit-entry-action">
              <span className="text-muted-foreground">Decisión</span>{" "}
              <span className="font-semibold text-foreground">
                {decisionLabel}
              </span>
            </p>
            <p data-testid="entry-decision-execution">
              <span className="text-muted-foreground">Ejecución</span>{" "}
              <span className="font-medium text-foreground">
                {executionLabel}
              </span>
            </p>
          </div>
        </div>
      )}
    </>
  );
}

function formatLegStatus(
  status: PositionJourneyReadoutV1["t1"]["status"],
): string {
  switch (status) {
    case "executed":
      return "✓ ejecutado";
    case "triggered":
      return "● disparado";
    case "pending":
      return "○ pendiente";
    case "failed":
      return "fallido";
    case "absent":
      return "—";
    default:
      return String(status);
  }
}

function JourneyHudBlock({
  journey,
  birthQuantity,
  hasProtectRevision,
  hasTrailRevision,
  plannedStop,
}: {
  journey: PositionJourneyReadoutV1;
  birthQuantity?: number | null;
  hasProtectRevision?: boolean;
  hasTrailRevision?: boolean;
  plannedStop?: number | null;
}) {
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const decision = buildOperatorDecision({
    kind: "position",
    primaryAction: journey.primaryAction,
    journey,
    birthQuantity: birthQuantity ?? null,
    currentStop: journey.trail.currentStop,
    plannedStop: plannedStop ?? journey.risk.initialStop,
    hasProtectRevision: hasProtectRevision === true,
    hasTrailRevision:
      hasTrailRevision === true || journey.trail.active === true,
    entry: journey.entry,
  });
  const nextAction = decision.currentAction;
  const positionPlan = buildOperatorPositionPlan(journey, {
    birthQuantity: birthQuantity ?? null,
  });
  const reduction = buildPositionReductionReadout({
    birthQuantity: birthQuantity ?? journey.remainingQuantity,
    remainingQuantity: journey.remainingQuantity,
    t1QtyFractionPct: journey.t1.qtyFractionPct,
    t2QtyFractionPct: journey.t2.qtyFractionPct,
  });
  const riskBox = buildOperatorRiskBox({
    entry: journey.entry,
    stop: journey.trail.currentStop ?? journey.risk.initialStop,
    lossAtStop: journey.risk.currentProtected,
    maxLoss: journey.risk.initialRisk,
    target1: journey.t1.trigger,
    target2: journey.t2.trigger,
    quantity: journey.remainingQuantity,
    positionValue:
      journey.entry != null ? journey.remainingQuantity * journey.entry : null,
  });
  const autoHonesty = formatOperatorAutoHonesty(
    journey.autoPosture,
    journey.killOn,
  );

  return (
    <div
      className="space-y-1.5 border-t border-border/40 pt-1.5"
      data-testid="position-journey-hud"
      data-cabin-composition="4-levels"
      data-operator-journey="v2.32"
      data-lifecycle-stage={journey.stageMachine ?? undefined}
      data-lineage-path={journey.lineagePathLabel ?? undefined}
      data-log-has-t2={journey.logHasT2Executed ? "1" : "0"}
    >
      <OperatorCabinLevel level={1} showQuestion={false}>
        <NextActionHero action={nextAction} testId="journey-next-action" />
      </OperatorCabinLevel>

      <OperatorCabinLevel level={2}>
        <OperatorProtectionLine protection={decision.protection} />
        <OperatorRiskBox box={riskBox} />
        <dl className={CABIN_KV_GRID} data-testid="position-card-risk-levels">
          <div className="flex justify-between gap-2">
            <dt>Stop inicial</dt>
            <dd className={cabinNumClass()} data-testid="journey-initial-stop">
              {formatLevel(journey.risk.initialStop)}
            </dd>
          </div>
          <div className="flex justify-between gap-2">
            <dt>Stop vigente</dt>
            <dd className={cabinNumClass()} data-testid="journey-current-stop">
              {formatLevel(journey.trail.currentStop)}
            </dd>
          </div>
          <div className="flex justify-between gap-2">
            <dt>Riesgo inicial</dt>
            <dd className={cabinNumClass()} data-testid="journey-initial-risk">
              {journey.risk.initialRisk != null
                ? String(journey.risk.initialRisk)
                : "—"}
            </dd>
          </div>
          <div className="flex justify-between gap-2">
            <dt>R realizado</dt>
            <dd className={cabinNumClass()} data-testid="journey-realized-r">
              {journey.risk.realizedR != null
                ? formatRSigned(journey.risk.realizedR)
                : "—"}
            </dd>
          </div>
          <div className="flex justify-between gap-2">
            <dt>Posición</dt>
            <dd className={cabinNumClass()} data-testid="journey-birth-qty">
              {reduction.birthQuantity}
            </dd>
          </div>
          <div className="flex justify-between gap-2">
            <dt>RESTANTE</dt>
            <dd className={cabinNumClass()} data-testid="journey-remaining">
              {reduction.remainingQuantity}
              {reduction.remainingPct != null
                ? ` · ${reduction.remainingPct}%`
                : ""}
            </dd>
          </div>
          <div className="flex justify-between gap-2">
            <dt>Realizado</dt>
            <dd className={cabinNumClass()} data-testid="journey-realized-pct">
              {reduction.realizedPct != null
                ? `${reduction.realizedPct}%`
                : "—"}
            </dd>
          </div>
          <div className="flex justify-between gap-2">
            <dt>Entrada</dt>
            <dd className={cabinNumClass()} data-testid="journey-entry">
              {formatLevel(journey.entry)}
            </dd>
          </div>
        </dl>
      </OperatorCabinLevel>

      <OperatorCabinLevel level={3}>
        <div data-testid="operator-exit-ladder">
          <OperatorPositionPlan plan={positionPlan} />
        </div>
        {/* Precios T1/T2/Trail para tests journey-* existentes */}
        <dl className="sr-only" data-testid="position-card-plan-levels">
          <div>
            <dt>T1</dt>
            <dd data-testid="journey-t1">
              {formatLevel(journey.t1.trigger)}
              {journey.t1.qtyFractionPct != null
                ? ` · ${journey.t1.qtyFractionPct}%`
                : ""}{" "}
              · {formatLegStatus(journey.t1.status)}
            </dd>
          </div>
          <div>
            <dt>T2</dt>
            <dd data-testid="journey-t2">
              {formatLevel(journey.t2.trigger)}
              {journey.t2.qtyFractionPct != null
                ? ` · ${journey.t2.qtyFractionPct}%`
                : ""}{" "}
              · {formatLegStatus(journey.t2.status)}
            </dd>
          </div>
          <div>
            <dt>Trailing</dt>
            <dd data-testid="journey-trail">
              {!journey.trail.activationEligible
                ? "Tras T1"
                : journey.trail.active
                  ? `Activo · stop ${formatLevel(journey.trail.currentStop)}`
                  : "Listo · sin ratchet"}
            </dd>
          </div>
        </dl>
      </OperatorCabinLevel>

      <OperatorCabinLevel level={4}>
        <button
          type="button"
          className={CABIN_INTERACTIVE}
          onClick={() => setAdvancedOpen((v) => !v)}
          data-testid="journey-advanced-toggle"
        >
          {advancedOpen ? "Ocultar detalles" : "¿Por qué? · AUTO"}
        </button>
        {advancedOpen ? (
          <div className="space-y-1">
            {autoHonesty ? (
              <p className={CABIN_TYPE.meta} data-testid="journey-auto-posture">
                {autoHonesty}
              </p>
            ) : null}
            <p
              className={CABIN_TYPE.meta}
              data-testid="journey-stage-label"
              title="stage derivado · el log es la historia"
            >
              Ciclo: {journey.stageLabel ?? "—"}
              {journey.lineagePathLabel
                ? ` · clasificación ${journey.lineagePathLabel}`
                : ""}
              {journey.logHasT2Executed ? " · log incluye T2" : ""}
            </p>
          </div>
        ) : null}
      </OperatorCabinLevel>
    </div>
  );
}

function PositionCompactBody({
  position,
  symbol,
  portfolioReconStatus,
  view,
  viewSource,
  journey,
  onOpenWhy,
  density,
}: Omit<PositionCompactProps, "variant" | "className" | "testId"> & {
  view: PositionOperationalViewV1;
}) {
  const [historyOpen, setHistoryOpen] = useState(false);
  const headline = povOperatingStateHeadline(view.operatingState);
  const statePhrase = formatOperatingStatePhrase(
    view.operatingState,
    portfolioReconStatus,
    position,
  );
  const decisionLabel = formatPovPrimaryActionLabel(view.primaryAction);
  const executionLabel = povExecutionStateLabel(
    view.operatingState,
    view.primaryAction,
  );
  const pnlPct = position.unrealizedPnlPct;
  const unrealizedR =
    view.levels.unrealizedR ?? position.operational?.unrealizedR;
  const hud = density === "hud";
  const nextAction = resolveOperatorNextAction({
    kind: "position",
    primaryAction: journey?.primaryAction ?? view.primaryAction,
    journey,
    currentStop: view.levels.currentStop,
    entry: view.levels.entry,
    birthQuantity: view.quantity,
  });

  return (
    <>
      {!hud && !journey ? (
        <OperatorCabinLevel level={1} showQuestion={false}>
          <NextActionHero action={nextAction} />
        </OperatorCabinLevel>
      ) : null}

      <div className="space-y-1">
        {!hud ? <SectionLabel>Posición</SectionLabel> : null}
        <div
          className="space-y-0.5"
          data-testid="operativa-cockpit-pov-state"
          data-state={view.operatingState}
          data-pov-state={view.operatingState}
          data-pov-source={viewSource ?? "canonical"}
          data-remaining-quantity={String(view.remainingQuantity)}
          data-birth-quantity={String(view.quantity)}
        >
          <p
            className={cn(
              "font-semibold leading-snug text-foreground",
              CABIN_TYPE.operativa,
            )}
            data-testid="position-decision-headline"
          >
            {headline}
          </p>
          <p className={cn(CABIN_TYPE.meta, hud && "line-clamp-2")}>
            {statePhrase}
          </p>
        </div>

        <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5">
          <p className={CABIN_TYPE.meta}>
            <span className="font-medium text-foreground">{symbol}</span>
            {position.lastPrice != null ? (
              <>
                {" "}
                ·{" "}
                <span
                  className={cabinNumClass()}
                  data-testid="position-decision-price"
                >
                  {formatLevel(position.lastPrice)}
                </span>
              </>
            ) : null}
          </p>
          {!hud && (pnlPct != null || unrealizedR != null) ? (
            <p
              className={cabinNumClass({ signed: true, value: pnlPct })}
              data-testid="position-decision-pnl"
            >
              {pnlPct != null ? formatPctSigned(pnlPct) : null}
              {pnlPct != null && unrealizedR != null ? " · " : null}
              {unrealizedR != null ? formatRSigned(unrealizedR) : null}
            </p>
          ) : null}
        </div>

        {hud ? (
          <p className={cabinNumClass({ size: "meta" })}>
            <span data-testid="position-decision-stop">
              S {formatLevel(view.levels.currentStop)}
            </span>
            {" · "}
            <span data-testid="position-decision-t1">
              T1 {formatLevel(view.levels.target1)}
            </span>
            {" · "}
            <span data-testid="position-decision-t2">
              T2 {formatLevel(view.levels.target2)}
            </span>
          </p>
        ) : journey ? null : (
          <>
            <OperatorCabinLevel level={2}>
              <dl className={CABIN_KV_GRID}>
                <div className="flex justify-between gap-2">
                  <dt>Stop</dt>
                  <dd
                    className={cabinNumClass()}
                    data-testid="position-decision-stop"
                  >
                    {formatLevel(view.levels.currentStop)}
                  </dd>
                </div>
              </dl>
            </OperatorCabinLevel>
            <OperatorCabinLevel level={3}>
              <OperatorPositionPlan
                plan={(() => {
                  const decision = buildOperatorDecision({
                    kind: "position",
                    primaryAction: view.primaryAction,
                    journey: null,
                    currentStop: view.levels.currentStop,
                    plannedStop: view.levels.currentStop,
                    hasProtectRevision: view.stopHistory.some(
                      (h) => h.origin === "protect",
                    ),
                    hasTrailRevision:
                      view.stopHistory.some((h) => h.origin === "trail") ||
                      view.operatingState === "TRAILING",
                    entry: view.levels.entry,
                    birthQuantity: view.quantity,
                    templateId: view.templateId,
                  });
                  return buildOperatorPositionPlanFromDecision(
                    {
                      ...decision,
                      plan: {
                        ...decision.plan,
                        entry: view.levels.entry ?? decision.plan.entry,
                        stop: view.levels.currentStop ?? decision.plan.stop,
                        t1: view.levels.target1 ?? decision.plan.t1,
                        t2: view.levels.target2 ?? decision.plan.t2,
                      },
                      remaining: buildPositionReductionReadout({
                        birthQuantity: view.quantity,
                        remainingQuantity: view.remainingQuantity,
                        t1QtyFractionPct: decision.plan.t1Pct,
                        t2QtyFractionPct: decision.plan.t2Pct,
                      }),
                    },
                    {
                      t1Done: view.t1?.status === "executed",
                      t2Done: view.t2?.status === "executed",
                      trailActive: view.operatingState === "TRAILING",
                    },
                  );
                })()}
              />
              {/* Compat testids for surface without journey HUD */}
              <dl className="sr-only">
                <dd data-testid="position-decision-t1">
                  {formatLevel(view.levels.target1)}
                </dd>
                <dd data-testid="position-decision-t2">
                  {formatLevel(view.levels.target2)}
                </dd>
              </dl>
            </OperatorCabinLevel>
          </>
        )}
        {!hud && journey ? (
          <>
            <JourneyHudBlock
              journey={journey}
              birthQuantity={view.quantity}
              hasProtectRevision={view.stopHistory.some(
                (h) => h.origin === "protect",
              )}
              hasTrailRevision={
                view.stopHistory.some((h) => h.origin === "trail") ||
                view.operatingState === "TRAILING"
              }
              plannedStop={journey.risk.initialStop}
            />
            {/* Compat testids for assertOperationalTruth (journey HUD hides Stop KV) */}
            <dl className="sr-only">
              <dd data-testid="position-decision-stop">
                {formatLevel(view.levels.currentStop)}
              </dd>
              <dd data-testid="position-decision-t1">
                {formatLevel(view.levels.target1)}
              </dd>
              <dd data-testid="position-decision-t2">
                {formatLevel(view.levels.target2)}
              </dd>
            </dl>
          </>
        ) : null}
      </div>

      <div
        className={cn(
          "space-y-0.5",
          hud ? "pt-0.5" : "border-t border-border/40 pt-1.5",
        )}
        data-testid="position-decision-action-block"
      >
        <div
          className={cn(
            "flex flex-wrap items-baseline justify-between gap-2",
            CABIN_TYPE.meta,
          )}
        >
          <p data-testid="operativa-cockpit-pov-action">
            <span className="text-muted-foreground">Decisión</span>{" "}
            <span className="font-semibold text-foreground">
              {decisionLabel}
            </span>
          </p>
          <p data-testid="position-decision-execution">
            <span className="text-muted-foreground">Ejecución</span>{" "}
            <span className="font-medium text-foreground">
              {executionLabel}
            </span>
          </p>
        </div>
      </div>

      {!hud && journey ? (
        <div className="flex flex-wrap items-center gap-2 border-t border-border/40 pt-1">
          {onOpenWhy ? (
            <button
              type="button"
              className={CABIN_INTERACTIVE}
              onClick={onOpenWhy}
              data-testid="position-decision-why-toggle"
            >
              ¿Por qué?
            </button>
          ) : null}
          {view.stopHistory.length > 0 ? (
            <button
              type="button"
              className={CABIN_INTERACTIVE}
              onClick={() => setHistoryOpen((v) => !v)}
              aria-expanded={historyOpen}
              data-testid="operativa-cockpit-stop-history-toggle"
            >
              {historyOpen ? "Ocultar historial de stop" : "Historial de stop"}
            </button>
          ) : null}
          {historyOpen && view.stopHistory.length > 0 ? (
            <ul
              className={cn("w-full space-y-0.5", CABIN_TYPE.meta)}
              data-testid="operativa-cockpit-stop-history"
            >
              {view.stopHistory.map((entry, idx) => (
                <li
                  key={`${entry.label}-${entry.stop}-${idx}`}
                  className="flex justify-between gap-2"
                >
                  <span className="truncate">{entry.label}</span>
                  <span className={cn("shrink-0", cabinNumClass())}>
                    {entry.stop.toFixed(2)}
                    {formatStopDelta(entry.delta)
                      ? ` (${formatStopDelta(entry.delta)})`
                      : ""}
                  </span>
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}

      {!hud && !journey ? (
        <OperatorCabinLevel
          level={4}
          className="border-t border-border/40 pt-1"
        >
          <div className="flex flex-wrap items-center gap-2">
            {onOpenWhy ? (
              <button
                type="button"
                className={CABIN_INTERACTIVE}
                onClick={onOpenWhy}
                data-testid="position-decision-why-toggle"
              >
                ¿Por qué?
              </button>
            ) : null}
            {view.stopHistory.length > 0 ? (
              <button
                type="button"
                className={CABIN_INTERACTIVE}
                onClick={() => setHistoryOpen((v) => !v)}
                aria-expanded={historyOpen}
                data-testid="operativa-cockpit-stop-history-toggle"
              >
                {historyOpen
                  ? "Ocultar historial de stop"
                  : "Historial de stop"}
              </button>
            ) : null}
          </div>
          {historyOpen && view.stopHistory.length > 0 ? (
            <ul
              className={cn("space-y-0.5", CABIN_TYPE.meta)}
              data-testid="operativa-cockpit-stop-history"
            >
              {view.stopHistory.map((entry, idx) => (
                <li
                  key={`${entry.label}-${entry.stop}-${idx}`}
                  className="flex justify-between gap-2"
                >
                  <span className="truncate">{entry.label}</span>
                  <span className={cn("shrink-0", cabinNumClass())}>
                    {entry.stop.toFixed(2)}
                    {formatStopDelta(entry.delta)
                      ? ` (${formatStopDelta(entry.delta)})`
                      : ""}
                  </span>
                </li>
              ))}
            </ul>
          ) : null}
        </OperatorCabinLevel>
      ) : null}
    </>
  );
}

export function DecisionSurfaceCompact(props: DecisionSurfaceCompactProps) {
  const density = props.density ?? "full";
  const hud = density === "hud";
  const positionHook = usePositionOperationalView(
    props.variant === "position" && !props.view ? props.position : null,
    props.variant === "position" ? props.portfolioReconStatus : undefined,
  );

  if (props.variant === "entry") {
    const tone = entryPhaseTone(props.truth.phase, {
      entriesBlocked: props.truth.entriesBlocked,
      gateStatus: props.truth.gateStatus,
    });
    return (
      <div
        className={cn(
          hud ? "space-y-1 px-2 py-1 rounded-md border" : "space-y-2",
          hud ? entryPhaseToneClasses(tone) : null,
          props.className,
        )}
        data-testid={props.testId ?? "decision-surface-compact-entry"}
        data-tone={tone}
        data-cabin-visual={CABIN_VISUAL_VERSION}
      >
        <EntryCompactBody {...props} density={density} />
      </div>
    );
  }

  const view = props.view ?? positionHook?.view;
  if (!view) return null;

  const tone = povOperatingStateTone(view.operatingState);
  return (
    <div
      className={cn(
        hud ? "space-y-1 px-2 py-1 rounded-md border" : "space-y-2",
        hud ? povOperatingStateToneClasses(tone) : null,
        props.className,
      )}
      data-testid={props.testId ?? "decision-surface-compact-position"}
      data-tone={tone}
      data-cabin-visual={CABIN_VISUAL_VERSION}
    >
      <PositionCompactBody
        {...props}
        view={view}
        viewSource={props.viewSource ?? positionHook?.source}
        density={density}
      />
    </div>
  );
}
