/**
 * V1.66 / V1.72 — Panel «¿Por qué?» determinista sobre DecisionExplainViewV1.
 * Layout TOP: score · LONG · factors · geometría · invalidación · autorización.
 * V2.47 — móvil: filas y factores apilados en estrecho; misma información, sin
 * eliminar secciones (regla 2 de docs/RESPONSIVE_PREMISES.md).
 */

import type { DecisionExplainViewV1 } from "@bolsa/shared";
import { cn } from "@/lib/utils";
import {
  cabinWidth,
  cabinRowClass,
  cabinRowValueClass,
  useNarrowCabin,
} from "@/features/trading/use-narrow-cabin";
import {
  CABIN_TYPE,
  CabinSectionLabel,
  cabinNumClass,
} from "@/features/trading/operator-cabin-ui";

type DecisionExplainPanelProps = {
  view: DecisionExplainViewV1 | null;
  loading?: boolean;
  className?: string;
};

function SectionLabel({ children }: { children: string }) {
  return <CabinSectionLabel>{children}</CabinSectionLabel>;
}

function KeyValueRows({
  rows,
  narrow,
  testId,
}: {
  rows: Array<{ label: string; value: string; testId?: string }>;
  narrow: boolean;
  testId?: string;
}) {
  if (rows.length === 0) return null;
  return (
    <dl className={cn("space-y-0.5", CABIN_TYPE.meta)} data-testid={testId}>
      {rows.map((row) => (
        <div key={row.label} className={cabinRowClass(narrow)}>
          <dt>{row.label}</dt>
          <dd
            className={cn(cabinRowValueClass(narrow), cabinNumClass())}
            data-testid={row.testId}
          >
            {row.value}
          </dd>
        </div>
      ))}
    </dl>
  );
}

function BulletList({ items }: { items: string[] }) {
  if (items.length === 0) return null;
  return (
    <ul className={cn("list-disc space-y-0.5 pl-4", CABIN_TYPE.operativa)}>
      {items.map((item) => (
        <li key={item}>{item}</li>
      ))}
    </ul>
  );
}

function factorMark(state: "pass" | "fail" | "unknown"): string {
  if (state === "pass") return "✓";
  if (state === "fail") return "✗";
  return "·";
}

function formatLevel(value: number | null): string | null {
  if (value == null || !Number.isFinite(value)) return null;
  return value.toFixed(2);
}

function formatDistance(abs: number | null, pct: number | null): string | null {
  if (abs == null || !Number.isFinite(abs)) return null;
  const sign = abs > 0 ? "+" : "";
  const pctPart =
    pct != null && Number.isFinite(pct) ? ` (${sign}${pct.toFixed(2)}%)` : "";
  return `${sign}${abs.toFixed(2)}${pctPart}`;
}

/** V2.47 — `+34.00 €` / `−12.50 €`: signo y moneda explícitos (R se publica aparte). */
function formatExpectedCurrency(value: number | null): string | null {
  if (value == null || !Number.isFinite(value)) return null;
  const sign = value > 0 ? "+" : value < 0 ? "−" : "";
  return `${sign}${Math.abs(value).toFixed(2)} €`;
}

/** V2.47 — `0.80`: magnitud adimensional del valor esperado. */
function formatExpectedR(value: number | null): string | null {
  if (value == null || !Number.isFinite(value)) return null;
  return value.toFixed(2);
}

export function DecisionExplainPanel({
  view,
  loading = false,
  className,
}: DecisionExplainPanelProps) {
  // Hook SIEMPRE antes de las salidas tempranas (loading / sin vista).
  const narrow = useNarrowCabin();
  if (loading) {
    return (
      <p
        className={cn("mt-1.5", CABIN_TYPE.meta, className)}
        data-testid="decision-explain-panel"
      >
        Cargando explicación…
      </p>
    );
  }
  if (!view) {
    return (
      <p
        className={cn("mt-1.5", CABIN_TYPE.meta, className)}
        data-testid="decision-explain-panel"
      >
        Sin explicación disponible.
      </p>
    );
  }

  const heroParts = [view.symbol, view.score?.label].filter(
    (part): part is string => Boolean(part),
  );

  const thesisRows = [
    view.thesis.opinion
      ? { label: "Dictamen", value: view.thesis.opinion }
      : null,
    view.thesis.strength
      ? { label: "Fuerza", value: view.thesis.strength }
      : null,
    view.thesis.summary
      ? { label: "Resumen", value: view.thesis.summary }
      : null,
  ].filter((row): row is { label: string; value: string } => row != null);

  const signalItems = [
    ...view.signals.consensus,
    ...view.signals.indicators,
    ...view.signals.trends,
  ];

  const conditionRows = [
    view.conditions.phase
      ? { label: "Fase", value: view.conditions.phase }
      : null,
    view.conditions.entryCondition
      ? { label: "Condición", value: view.conditions.entryCondition }
      : null,
  ].filter((row): row is { label: string; value: string } => row != null);

  const whyNotItems = view.conditions.whyNot.map((item) => item.label);

  const entryRows = [
    formatLevel(view.entryGeometry.entry)
      ? {
          label: "Entrada",
          value: formatLevel(view.entryGeometry.entry)!,
        }
      : null,
    formatLevel(view.entryGeometry.currentPrice)
      ? {
          label: "Precio actual",
          value: formatLevel(view.entryGeometry.currentPrice)!,
        }
      : null,
    formatDistance(
      view.entryGeometry.distanceAbs,
      view.entryGeometry.distancePct,
    )
      ? {
          label: "Distancia",
          value: formatDistance(
            view.entryGeometry.distanceAbs,
            view.entryGeometry.distancePct,
          )!,
          testId: "decision-explain-entry-distance",
        }
      : null,
  ].filter(
    (row): row is { label: string; value: string; testId?: string } =>
      row != null,
  );

  const protectionRows = formatLevel(view.levels.stop)
    ? [{ label: "Stop", value: formatLevel(view.levels.stop)! }]
    : [];

  const objectiveRows = [
    formatLevel(view.levels.target1)
      ? { label: "T1", value: formatLevel(view.levels.target1)! }
      : null,
    formatLevel(view.levels.target2)
      ? { label: "T2", value: formatLevel(view.levels.target2)! }
      : null,
  ].filter((row): row is { label: string; value: string } => row != null);

  // V2.47 — economía medida: se publica SOLO lo que existe. Sin R ni neto no hay fila
  // (un `0 €` afirmaría que la operación no deja dinero, que es otra cosa que no medirlo).
  const expectedValueRows = [
    formatExpectedCurrency(view.expectedValue?.netExpectedCurrency ?? null)
      ? {
          label: "Valor esperado neto",
          value: formatExpectedCurrency(
            view.expectedValue?.netExpectedCurrency ?? null,
          )!,
          testId: "decision-explain-expected-currency",
        }
      : null,
    formatExpectedR(view.expectedValue?.expectedR ?? null)
      ? {
          label: "R esperado",
          value: formatExpectedR(view.expectedValue?.expectedR ?? null)!,
          testId: "decision-explain-expected-r",
        }
      : null,
  ].filter(
    (row): row is { label: string; value: string; testId: string } =>
      row != null,
  );

  const authRows = [
    {
      label: "Estado",
      value: view.authorization.entriesBlocked
        ? "Entradas bloqueadas"
        : "Sin bloqueo de entradas",
    },
    view.authorization.gateStatus
      ? { label: "Gate", value: view.authorization.gateStatus }
      : null,
  ].filter((row): row is { label: string; value: string } => row != null);

  const policyRows = [
    view.policy.fitLabel
      ? { label: "Cartera", value: view.policy.fitLabel }
      : null,
    view.policy.mandateLabel
      ? { label: "Mandato", value: view.policy.mandateLabel }
      : null,
  ].filter((row): row is { label: string; value: string } => row != null);

  const traceRows = [
    view.traceability.asOf
      ? { label: "As-of", value: view.traceability.asOf }
      : null,
    view.traceability.source
      ? { label: "Fuente", value: view.traceability.source }
      : null,
    view.traceability.decisionId
      ? { label: "Decisión", value: view.traceability.decisionId }
      : null,
  ].filter((row): row is { label: string; value: string } => row != null);

  const hasContent =
    heroParts.length > 0 ||
    view.thesisDirection.label != null ||
    view.factors.length > 0 ||
    thesisRows.length > 0 ||
    signalItems.length > 0 ||
    conditionRows.length > 0 ||
    whyNotItems.length > 0 ||
    entryRows.length > 0 ||
    expectedValueRows.length > 0 ||
    protectionRows.length > 0 ||
    objectiveRows.length > 0 ||
    view.invalidators.length > 0 ||
    authRows.length > 0 ||
    policyRows.length > 0 ||
    traceRows.length > 0;

  if (!hasContent) {
    return (
      <p
        className={cn("mt-1.5", CABIN_TYPE.meta, className)}
        data-testid="decision-explain-panel"
      >
        Sin explicación disponible.
      </p>
    );
  }

  return (
    <div
      className={cn(
        "mt-1.5 space-y-2 border-t border-border/50 pt-1.5",
        className,
      )}
      data-testid="decision-explain-panel"
      data-cabin-width={cabinWidth(narrow)}
    >
      {heroParts.length > 0 ? (
        <p
          className="text-[11px] font-semibold text-foreground"
          data-testid="decision-explain-score"
        >
          {heroParts.join(" · ")}
        </p>
      ) : null}

      {view.thesisDirection?.label ? (
        <section data-testid="decision-explain-section-decision">
          <SectionLabel>Decisión</SectionLabel>
          <p
            className="text-[11px] font-semibold tracking-wide text-foreground"
            data-testid="decision-explain-direction"
          >
            {view.thesisDirection.label}
          </p>
        </section>
      ) : null}

      {view.factors?.length ? (
        <section data-testid="decision-explain-section-why">
          <SectionLabel>Por qué</SectionLabel>
          <ul className={cn("space-y-0.5", CABIN_TYPE.operativa)}>
            {view.factors.map((item) => (
              <li
                key={item.id}
                className={cn(
                  narrow
                    ? "flex flex-col items-start gap-0.5"
                    : "flex flex-wrap items-baseline justify-between gap-x-2 gap-y-0.5",
                )}
                data-testid={`decision-explain-factor-${item.id}`}
                data-state={item.state}
              >
                <span>
                  <span className="font-medium tabular-nums">
                    {factorMark(item.state)}
                  </span>{" "}
                  {item.label}
                </span>
                <span className="text-muted-foreground">
                  {item.state === "unknown" ? "sin dato" : item.detail}
                </span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {entryRows.length > 0 ? (
        <section data-testid="decision-explain-section-entry">
          <SectionLabel>Entrada</SectionLabel>
          <KeyValueRows rows={entryRows} narrow={narrow} />
        </section>
      ) : null}

      {expectedValueRows.length > 0 ? (
        <section data-testid="decision-explain-section-expected-value">
          <SectionLabel>Economía</SectionLabel>
          <KeyValueRows rows={expectedValueRows} narrow={narrow} />
        </section>
      ) : null}

      {protectionRows.length > 0 ? (
        <section data-testid="decision-explain-section-protection">
          <SectionLabel>Protección</SectionLabel>
          <KeyValueRows rows={protectionRows} narrow={narrow} />
        </section>
      ) : null}

      {objectiveRows.length > 0 ? (
        <section data-testid="decision-explain-section-objectives">
          <SectionLabel>Objetivos</SectionLabel>
          <KeyValueRows rows={objectiveRows} narrow={narrow} />
        </section>
      ) : null}

      {view.invalidators.length > 0 ? (
        <section data-testid="decision-explain-section-invalidators">
          <SectionLabel>Invalidación</SectionLabel>
          <BulletList items={view.invalidators} />
        </section>
      ) : null}

      <section data-testid="decision-explain-section-authorization">
        <SectionLabel>Autorización</SectionLabel>
        <p className={CABIN_TYPE.meta}>{view.authorization.copy}</p>
        <KeyValueRows rows={authRows} narrow={narrow} />
      </section>

      {thesisRows.length > 0 ? (
        <section data-testid="decision-explain-section-thesis">
          <SectionLabel>Tesis</SectionLabel>
          <KeyValueRows rows={thesisRows} narrow={narrow} />
        </section>
      ) : null}

      {signalItems.length > 0 ? (
        <section data-testid="decision-explain-section-signals">
          <SectionLabel>Señales</SectionLabel>
          <BulletList items={signalItems} />
        </section>
      ) : null}

      {conditionRows.length > 0 || whyNotItems.length > 0 ? (
        <section data-testid="decision-explain-section-conditions">
          <SectionLabel>Condiciones</SectionLabel>
          <KeyValueRows rows={conditionRows} narrow={narrow} />
          {whyNotItems.length > 0 ? <BulletList items={whyNotItems} /> : null}
        </section>
      ) : null}

      {policyRows.length > 0 ? (
        <section data-testid="decision-explain-section-policy">
          <SectionLabel>Política</SectionLabel>
          <KeyValueRows rows={policyRows} narrow={narrow} />
        </section>
      ) : null}

      {traceRows.length > 0 ? (
        <section data-testid="decision-explain-section-traceability">
          <SectionLabel>Trazabilidad</SectionLabel>
          <KeyValueRows rows={traceRows} narrow={narrow} />
        </section>
      ) : null}
    </div>
  );
}
