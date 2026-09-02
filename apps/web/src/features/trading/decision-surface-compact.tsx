/**
 * V1.63 — Presentación compacta compartida Entry/Position Decision Surface.
 * Usada en panel (full) y HUD del gráfico (hud). Display-only — no firma · no BUY.
 */

import { useState } from "react";
import type {
  EntryOperatingTruthV1,
  PositionDto,
  PositionOperationalStateV1,
  PositionOperationalViewV1,
  SubmitIntentListItemV1,
} from "@bolsa/shared";
import {
  assertNever,
  buildExecutionState,
  buildPositionDecisionFromDto,
  formatPositionDecisionPhrase,
  reconPhraseFromPortfolioStatus,
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

function formatRR(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return "—";
  return `${value.toFixed(1)}:1`;
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
      return "Posición abierta sin protección registrada.";
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

  return (
    <>
      <div className="space-y-1">
        {!hud ? <SectionLabel>Estado de la entrada</SectionLabel> : null}
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
            {headline}
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
            {plan.currentPrice != null && Number.isFinite(plan.currentPrice) ? (
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
                {qty}
              </dd>
            </div>
            <div className="flex justify-between gap-2">
              <dt>Riesgo</dt>
              <dd
                className="font-medium tabular-nums text-foreground"
                data-testid="entry-decision-risk"
              >
                {formatMoney(sizing.riskAmount)}
              </dd>
            </div>
            <div className="flex justify-between gap-2">
              <dt>R/R</dt>
              <dd className="font-medium tabular-nums text-foreground">
                {formatRR(sizing.expectedRR)}
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
        )}
      </div>

      <div
        className={cn(
          "space-y-0.5",
          hud ? "pt-0.5" : "border-t border-border/40 pt-1.5",
        )}
        data-testid="entry-decision-action-block"
      >
        {!hud ? <SectionLabel>Próxima acción</SectionLabel> : null}
        <div
          className={cn(
            "flex flex-wrap items-baseline justify-between gap-2",
            hud ? "text-[9px]" : "text-[10px]",
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

      {!hud && onOpenWhy ? (
        <div className="border-t border-border/40 pt-1">
          <button
            type="button"
            className="text-[10px] font-medium text-foreground/90 underline-offset-2 hover:underline"
            onClick={onOpenWhy}
            data-testid="entry-decision-why-toggle"
          >
            Ver por qué
          </button>
        </div>
      ) : null}
    </>
  );
}

function PositionCompactBody({
  position,
  symbol,
  portfolioReconStatus,
  view,
  viewSource,
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

  return (
    <>
      <div className="space-y-1">
        {!hud ? <SectionLabel>Estado de la operación</SectionLabel> : null}
        <div
          className="space-y-0.5"
          data-testid="operativa-cockpit-pov-state"
          data-state={view.operatingState}
          data-pov-state={view.operatingState}
          data-pov-source={viewSource ?? "canonical"}
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
      </div>

      <div
        className={cn(
          "space-y-0.5",
          hud ? "pt-0.5" : "border-t border-border/40 pt-1.5",
        )}
        data-testid="position-decision-action-block"
      >
        {!hud ? <SectionLabel>Próxima acción</SectionLabel> : null}
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
              Ver por qué
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
