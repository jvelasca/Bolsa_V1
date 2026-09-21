/**
 * V1.38 — Resumen operativo de entrada («¿qué está pasando?» pre-posición).
 * Fase + frase + trigger + sizing. Niveles en OperationalPlanView.
 * V2.47 — móvil: filas etiqueta→valor apiladas en estrecho (misma información).
 */

import type {
  DecisionJournalStudyViewV1,
  EntryOperatingTruthV1,
  SubmitIntentListItemV1,
} from "@bolsa/shared";
import {
  buildEntryOperatingTruth,
  buildExecutionState,
  formatEntryOperatingAsOf,
  formatExecutionStateCopy,
  formatExpectedValueLabel,
} from "@bolsa/shared";
import { cn } from "@/lib/utils";
import { formatPrice } from "@/features/charts/chart-utils";
import {
  cabinRowClass,
  cabinRowValueClass,
  cabinWidth,
  useNarrowCabin,
} from "@/features/trading/use-narrow-cabin";

function formatMoney(value: number | null | undefined): string | null {
  if (value == null || !Number.isFinite(value)) return null;
  return formatPrice(value);
}

function formatR(value: number | null | undefined): string | null {
  if (value == null || !Number.isFinite(value)) return null;
  return `${value.toFixed(2)}R`;
}

function formatRR(value: number | null | undefined): string | null {
  if (value == null || !Number.isFinite(value)) return null;
  return `${value.toFixed(1)}:1`;
}

/** Fila etiqueta→valor: en estrecho se apila (label arriba, valor debajo). */
function SummaryRow({
  label,
  value,
  narrow,
  testId,
}: {
  label: string;
  value: string;
  narrow: boolean;
  testId?: string;
}) {
  return (
    <div className={cabinRowClass(narrow)}>
      <dt className="text-muted-foreground">{label}</dt>
      <dd
        className={cn("font-medium tabular-nums", cabinRowValueClass(narrow))}
        data-testid={testId}
      >
        {value}
      </dd>
    </div>
  );
}

export function EntryOperatingSummary({
  truth: truthProp,
  study,
  inConfirmQueue,
  orderPendingFill,
  submitIntent,
  entriesBlocked,
  gateStatus,
  className,
}: {
  truth?: EntryOperatingTruthV1 | null;
  study?: DecisionJournalStudyViewV1 | null;
  inConfirmQueue?: boolean;
  orderPendingFill?: boolean;
  submitIntent?: SubmitIntentListItemV1 | null;
  entriesBlocked?: boolean;
  gateStatus?: string | null;
  className?: string;
}) {
  // Hook SIEMPRE antes de cualquier salida temprana (reglas de hooks).
  const narrow = useNarrowCabin();
  const truth =
    truthProp ??
    (study
      ? buildEntryOperatingTruth({
          study,
          inConfirmQueue,
          orderPendingFill,
          entriesBlocked,
          gateStatus,
        })
      : null);
  if (!truth) return null;

  const { sizing, phaseLabel, primaryCta } = truth;
  const asOfLabel = formatEntryOperatingAsOf(truth.asOf);
  const executionState = buildExecutionState({
    instrumentId: truth.instrumentId,
    asOf: truth.asOf,
    pendingOrder: orderPendingFill ?? false,
    submitIntent: submitIntent ?? null,
  });
  const executionCopy = formatExecutionStateCopy(executionState);
  const riskMoney = formatMoney(sizing.riskAmount);
  const riskR = formatR(sizing.riskR);
  const rr = formatRR(sizing.expectedRR);
  // V2.47 — valor esperado neto: formateador PROPIO (el de dinero de la casa no añade
  // símbolo ni signo, y un valor esperado sin signo se lee como un precio). Sin medición
  // devuelve `null` y la fila se OMITE: no se pinta un `0 €` que nadie calculó.
  const expectedValueLabel = formatExpectedValueLabel({
    expectedR: sizing.expectedR,
    netExpectedCurrency: sizing.netExpectedCurrency,
  });
  const notional = formatMoney(sizing.positionValue);
  const qty =
    sizing.quantity != null && Number.isFinite(sizing.quantity)
      ? `${sizing.quantity} uds`
      : null;

  return (
    <div
      className={cn(
        "space-y-2 rounded-md border border-border/60 bg-background/40 px-2.5 py-2",
        narrow && "px-2",
        className,
      )}
      data-testid="entry-operating-summary"
      data-phase={truth.phase}
      data-cta={primaryCta.kind}
      data-execution-lifecycle={executionState.lifecycle}
      data-cabin-width={cabinWidth(narrow)}
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p
          className="text-[11px] font-semibold uppercase tracking-wide"
          data-testid="entry-operating-phase"
        >
          {phaseLabel}
        </p>
        <p
          className="text-[11px] font-medium text-muted-foreground"
          data-testid="entry-operating-trigger"
        >
          Trigger: {truth.triggerLabel}
        </p>
      </div>
      <p
        className="text-[11px] leading-snug text-foreground"
        data-testid="entry-operating-phrase"
      >
        {truth.phrase}
      </p>
      {/* Móvil: el suelo tipográfico sube a 12 px (12/10 px es ilegible en teléfono). */}
      <dl className={cn("grid gap-1", narrow ? "text-xs" : "text-[10px]")}>
        <SummaryRow
          label="Acción"
          value={primaryCta.label}
          narrow={narrow}
          testId="entry-operating-action"
        />
        {riskMoney ? (
          <SummaryRow
            label="Riesgo al stop"
            value={riskMoney}
            narrow={narrow}
          />
        ) : null}
        {riskR ? (
          <SummaryRow label="R planificado" value={riskR} narrow={narrow} />
        ) : null}
        {rr ? (
          <SummaryRow label="R/R esperado" value={rr} narrow={narrow} />
        ) : null}
        {expectedValueLabel ? (
          <SummaryRow
            label="Valor esperado neto"
            value={expectedValueLabel}
            narrow={narrow}
            testId="entry-operating-expected-value"
          />
        ) : null}
        {notional || qty ? (
          <SummaryRow
            label="Tamaño"
            value={[notional, qty].filter(Boolean).join(" · ")}
            narrow={narrow}
          />
        ) : null}
        {truth.expiryLabel ? (
          <SummaryRow
            label="Vigencia"
            value={truth.expiryLabel}
            narrow={narrow}
          />
        ) : null}
        {asOfLabel ? (
          <SummaryRow
            label="Datos"
            value={asOfLabel}
            narrow={narrow}
            testId="entry-operating-asof"
          />
        ) : null}
      </dl>
      {executionCopy ? (
        <p
          className="text-[10px] font-medium text-amber-800 dark:text-amber-200"
          data-testid="entry-operating-execution"
        >
          {executionCopy}
        </p>
      ) : null}
      <p
        className={cn(
          "text-muted-foreground",
          narrow ? "text-[11px]" : "text-[9px]",
        )}
      >
        Ranking ≠ BUY. Confirm = firma.
      </p>
    </div>
  );
}
