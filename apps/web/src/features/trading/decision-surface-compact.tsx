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
  buildOperatorFourAnswers,
  buildOperatorMissionSteps,
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
  NextActionHero,
  OperatorFourAnswersBlock,
  OperatorMissionChecklist,
  OperatorRiskBox,
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
  return (
    <p className="text-[9px] font-semibold uppercase tracking-wider text-muted-foreground/90">
      {children}
    </p>
  );
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
      {!hud ? <NextActionHero action={nextAction} /> : null}

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
              hud ? "text-[10px]" : "text-[11px]",
            )}
            data-testid="entry-decision-headline"
          >
            {symbol} · {headline}
          </p>
          <p
            className={cn(
              "leading-snug text-muted-foreground",
              hud ? "text-[9px] line-clamp-2" : "text-[10px]",
            )}
            data-testid="entry-operating-phrase"
          >
            {truth.phrase}
          </p>
        </div>

        <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5">
          <p className="text-[10px] text-muted-foreground">
            <span className="font-medium text-foreground">{symbol}</span>
          </p>
          <p
            className="text-[10px] font-medium tabular-nums text-foreground"
            data-testid="entry-operating-trigger"
          >
            Trigger {truth.triggerLabel}
          </p>
        </div>

        {hud ? (
          <p className="text-[9px] tabular-nums text-muted-foreground">
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
            <OperatorRiskBox box={riskBox} />
            <dl className="grid grid-cols-2 gap-x-3 gap-y-0.5 text-[10px] text-muted-foreground">
              <div className="flex justify-between gap-2">
                <dt>Entrada</dt>
                <dd
                  className="font-medium tabular-nums text-foreground"
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
                    className="font-medium tabular-nums text-foreground"
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
                    className="font-medium tabular-nums text-foreground"
                    data-testid="entry-decision-distance"
                  >
                    {formatDistance(plan.entry, plan.currentPrice)}
                  </dd>
                </div>
              ) : null}
              <div className="flex justify-between gap-2">
                <dt>Stop</dt>
                <dd
                  className="font-medium tabular-nums text-foreground"
                  data-testid="entry-decision-stop"
                >
                  {formatEntryLevel(plan.stopVigente)}
                </dd>
              </div>
              <div className="flex justify-between gap-2">
                <dt>T1</dt>
                <dd
                  className="font-medium tabular-nums text-foreground"
                  data-testid="entry-decision-t1"
                >
                  {formatEntryLevel(plan.target1)}
                </dd>
              </div>
              <div className="flex justify-between gap-2">
                <dt>T2</dt>
                <dd
                  className="font-medium tabular-nums text-foreground"
                  data-testid="entry-decision-t2"
                >
                  {formatEntryLevel(plan.target2)}
                </dd>
              </div>
              <div className="flex justify-between gap-2">
                <dt>Tamaño</dt>
                <dd className="font-medium tabular-nums text-foreground">
                  {qty} acciones
                </dd>
              </div>
              <div className="flex justify-between gap-2">
                <dt>Riesgo</dt>
                <dd
                  className="font-medium tabular-nums text-foreground"
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
                  <dd className="font-medium text-foreground">
                    {truth.expiryLabel}
                  </dd>
                </div>
              ) : null}
            </dl>
            <button
              type="button"
              className="text-[10px] font-medium text-foreground/90 underline-offset-2 hover:underline"
              onClick={() => setAdvancedOpen((v) => !v)}
              data-testid="entry-advanced-toggle"
            >
              {advancedOpen ? "Ocultar detalles" : "Detalles avanzados"}
            </button>
            {advancedOpen ? (
              <OperatorFourAnswersBlock answers={fourAnswers} />
            ) : null}
          </>
        )}
      </div>

      {hud ? (
        <div
          className="space-y-0.5 pt-0.5"
          data-testid="entry-decision-action-block"
        >
          <div className="flex flex-wrap items-baseline justify-between gap-2 text-[9px]">
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
          <div className="flex flex-wrap items-baseline justify-between gap-2 text-[10px]">
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

      {!hud && onOpenWhy ? (
        <div className="border-t border-border/40 pt-1">
          <button
            type="button"
            className="text-[10px] font-medium text-foreground/90 underline-offset-2 hover:underline"
            onClick={onOpenWhy}
            data-testid="entry-decision-why-toggle"
          >
            ¿Por qué?
          </button>
        </div>
      ) : null}
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
}: {
  journey: PositionJourneyReadoutV1;
  birthQuantity?: number | null;
}) {
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const nextAction = resolveOperatorNextAction({
    kind: "position",
    primaryAction: journey.primaryAction,
    journey,
  });
  const steps = buildOperatorMissionSteps(journey);
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
      data-lifecycle-stage={journey.stageMachine ?? undefined}
      data-lineage-path={journey.lineagePathLabel ?? undefined}
      data-log-has-t2={journey.logHasT2Executed ? "1" : "0"}
    >
      <NextActionHero action={nextAction} testId="journey-next-action" />

      <SectionLabel>Misión de la posición</SectionLabel>
      <OperatorMissionChecklist steps={steps} />

      <OperatorRiskBox box={riskBox} />

      <dl
        className="grid grid-cols-2 gap-x-3 gap-y-0.5 text-[10px] text-muted-foreground"
        data-testid="position-card-levels"
      >
        <div className="flex justify-between gap-2">
          <dt>Stop inicial</dt>
          <dd
            className="font-medium tabular-nums text-foreground"
            data-testid="journey-initial-stop"
          >
            {formatLevel(journey.risk.initialStop)}
          </dd>
        </div>
        <div className="flex justify-between gap-2">
          <dt>Stop vigente</dt>
          <dd className="font-medium tabular-nums text-foreground">
            {formatLevel(journey.trail.currentStop)}
          </dd>
        </div>
        <div className="flex justify-between gap-2">
          <dt>Riesgo inicial</dt>
          <dd
            className="font-medium tabular-nums text-foreground"
            data-testid="journey-initial-risk"
          >
            {journey.risk.initialRisk != null
              ? String(journey.risk.initialRisk)
              : "—"}
          </dd>
        </div>
        <div className="flex justify-between gap-2">
          <dt>R realizado</dt>
          <dd
            className="font-medium tabular-nums text-foreground"
            data-testid="journey-realized-r"
          >
            {journey.risk.realizedR != null
              ? formatRSigned(journey.risk.realizedR)
              : "—"}
          </dd>
        </div>
        <div className="flex justify-between gap-2">
          <dt>Posición</dt>
          <dd
            className="font-medium tabular-nums text-foreground"
            data-testid="journey-birth-qty"
          >
            {reduction.birthQuantity}
          </dd>
        </div>
        <div className="flex justify-between gap-2">
          <dt>Restante</dt>
          <dd
            className="font-medium tabular-nums text-foreground"
            data-testid="journey-remaining"
          >
            {reduction.remainingQuantity}
            {reduction.remainingPct != null
              ? ` · ${reduction.remainingPct}%`
              : ""}
          </dd>
        </div>
        <div className="flex justify-between gap-2">
          <dt>Realizado</dt>
          <dd
            className="font-medium tabular-nums text-foreground"
            data-testid="journey-realized-pct"
          >
            {reduction.realizedPct != null ? `${reduction.realizedPct}%` : "—"}
          </dd>
        </div>
        <div className="flex justify-between gap-2">
          <dt>Entrada</dt>
          <dd
            className="font-medium tabular-nums text-foreground"
            data-testid="journey-entry"
          >
            {formatLevel(journey.entry)}
          </dd>
        </div>
        <div className="col-span-2 flex justify-between gap-2">
          <dt>T1</dt>
          <dd data-testid="journey-t1" className="text-right text-foreground">
            {formatLevel(journey.t1.trigger)}
            {journey.t1.qtyFractionPct != null
              ? ` · ${journey.t1.qtyFractionPct}%`
              : ""}{" "}
            · {formatLegStatus(journey.t1.status)}
          </dd>
        </div>
        <div className="col-span-2 flex justify-between gap-2">
          <dt>T2</dt>
          <dd data-testid="journey-t2" className="text-right text-foreground">
            {formatLevel(journey.t2.trigger)}
            {journey.t2.qtyFractionPct != null
              ? ` · ${journey.t2.qtyFractionPct}%`
              : ""}{" "}
            · {formatLegStatus(journey.t2.status)}
          </dd>
        </div>
        <div className="col-span-2 flex justify-between gap-2">
          <dt>Trailing</dt>
          <dd
            data-testid="journey-trail"
            className="text-right text-foreground"
          >
            {!journey.trail.activationEligible
              ? "Tras T1"
              : journey.trail.active
                ? `Activo · stop ${formatLevel(journey.trail.currentStop)}`
                : "Listo · sin ratchet"}
          </dd>
        </div>
      </dl>

      {autoHonesty ? (
        <p
          className="text-[9px] leading-snug text-muted-foreground"
          data-testid="journey-auto-posture"
        >
          {autoHonesty}
        </p>
      ) : null}

      <button
        type="button"
        className="text-[10px] font-medium text-foreground/90 underline-offset-2 hover:underline"
        onClick={() => setAdvancedOpen((v) => !v)}
        data-testid="journey-advanced-toggle"
      >
        {advancedOpen ? "Ocultar auditoría" : "Detalles avanzados"}
      </button>
      {advancedOpen ? (
        <p
          className="text-[9px] leading-snug text-muted-foreground"
          data-testid="journey-stage-label"
          title="stage derivado · el log es la historia"
        >
          Ciclo: {journey.stageLabel ?? "—"}
          {journey.lineagePathLabel
            ? ` · clasificación ${journey.lineagePathLabel}`
            : ""}
          {journey.logHasT2Executed ? " · log incluye T2" : ""}
        </p>
      ) : null}
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
  });

  return (
    <>
      {!hud && !journey ? <NextActionHero action={nextAction} /> : null}

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
              hud ? "text-[10px]" : "text-[11px]",
            )}
            data-testid="position-decision-headline"
          >
            {headline}
          </p>
          <p
            className={cn(
              "leading-snug text-muted-foreground",
              hud ? "text-[9px] line-clamp-2" : "text-[10px]",
            )}
          >
            {statePhrase}
          </p>
        </div>

        <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5">
          <p className="text-[10px] text-muted-foreground">
            <span className="font-medium text-foreground">{symbol}</span>
            {position.lastPrice != null ? (
              <>
                {" "}
                ·{" "}
                <span
                  className="tabular-nums text-foreground"
                  data-testid="position-decision-price"
                >
                  {formatLevel(position.lastPrice)}
                </span>
              </>
            ) : null}
          </p>
          {!hud && (pnlPct != null || unrealizedR != null) ? (
            <p
              className={cn(
                "text-[10px] font-medium tabular-nums",
                pnlPct != null && pnlPct >= 0
                  ? "text-emerald-800 dark:text-emerald-200"
                  : pnlPct != null
                    ? "text-rose-800 dark:text-rose-200"
                    : "text-foreground",
              )}
              data-testid="position-decision-pnl"
            >
              {pnlPct != null ? formatPctSigned(pnlPct) : null}
              {pnlPct != null && unrealizedR != null ? " · " : null}
              {unrealizedR != null ? formatRSigned(unrealizedR) : null}
            </p>
          ) : null}
        </div>

        {hud ? (
          <p className="text-[9px] tabular-nums text-muted-foreground">
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
        ) : (
          <dl className="grid grid-cols-2 gap-x-3 gap-y-0.5 text-[10px] text-muted-foreground">
            <div className="flex justify-between gap-2">
              <dt>Stop</dt>
              <dd
                className="font-medium tabular-nums text-foreground"
                data-testid="position-decision-stop"
              >
                {formatLevel(view.levels.currentStop)}
              </dd>
            </div>
            <div className="flex justify-between gap-2">
              <dt>T1</dt>
              <dd
                className="font-medium tabular-nums text-foreground"
                data-testid="position-decision-t1"
              >
                {formatLevel(view.levels.target1)}
              </dd>
            </div>
            <div className="flex justify-between gap-2">
              <dt>T2</dt>
              <dd
                className="font-medium tabular-nums text-foreground"
                data-testid="position-decision-t2"
              >
                {formatLevel(view.levels.target2)}
              </dd>
            </div>
            {view.operatingState === "TRAILING" ? (
              <div className="flex justify-between gap-2">
                <dt>Trail</dt>
                <dd className="font-medium text-foreground">Activo</dd>
              </div>
            ) : null}
          </dl>
        )}
        {!hud && journey ? (
          <JourneyHudBlock journey={journey} birthQuantity={view.quantity} />
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
            hud ? "text-[9px]" : "text-[10px]",
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

      {!hud ? (
        <div className="flex flex-wrap items-center gap-2 border-t border-border/40 pt-1">
          {onOpenWhy ? (
            <button
              type="button"
              className="text-[10px] font-medium text-foreground/90 underline-offset-2 hover:underline"
              onClick={onOpenWhy}
              data-testid="position-decision-why-toggle"
            >
              ¿Por qué?
            </button>
          ) : null}
          {view.stopHistory.length > 0 ? (
            <button
              type="button"
              className="text-[10px] font-medium text-foreground/90 underline-offset-2 hover:underline"
              onClick={() => setHistoryOpen((v) => !v)}
              aria-expanded={historyOpen}
              data-testid="operativa-cockpit-stop-history-toggle"
            >
              {historyOpen ? "Ocultar historial de stop" : "Historial de stop"}
            </button>
          ) : null}
        </div>
      ) : null}

      {!hud && historyOpen && view.stopHistory.length > 0 ? (
        <ul
          className="space-y-0.5 text-[10px] text-muted-foreground"
          data-testid="operativa-cockpit-stop-history"
        >
          {view.stopHistory.map((entry, idx) => (
            <li
              key={`${entry.label}-${entry.stop}-${idx}`}
              className="flex justify-between gap-2"
            >
              <span className="truncate">{entry.label}</span>
              <span className="shrink-0 font-medium tabular-nums text-foreground">
                {entry.stop.toFixed(2)}
                {formatStopDelta(entry.delta)
                  ? ` (${formatStopDelta(entry.delta)})`
                  : ""}
              </span>
            </li>
          ))}
        </ul>
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
          "rounded-md border",
          hud ? "space-y-1 px-2 py-1" : "space-y-2 px-2 py-1.5",
          entryPhaseToneClasses(tone),
          props.className,
        )}
        data-testid={props.testId ?? "decision-surface-compact-entry"}
        data-tone={tone}
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
        "rounded-md border",
        hud ? "space-y-1 px-2 py-1" : "space-y-2 px-2 py-1.5",
        povOperatingStateToneClasses(tone),
        props.className,
      )}
      data-testid={props.testId ?? "decision-surface-compact-position"}
      data-tone={tone}
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
