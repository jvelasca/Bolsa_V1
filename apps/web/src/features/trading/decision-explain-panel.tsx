/**
 * V1.66 / V1.72 — Panel «¿Por qué?» determinista sobre DecisionExplainViewV1.
 * Layout TOP: score · LONG · factors · geometría · invalidación · autorización.
 */

import type { DecisionExplainViewV1 } from "@bolsa/shared";
import { cn } from "@/lib/utils";

type DecisionExplainPanelProps = {
  view: DecisionExplainViewV1 | null;
  loading?: boolean;
  className?: string;
};

function SectionLabel({ children }: { children: string }) {
  return (
    <p className="text-[9px] font-semibold uppercase tracking-wider text-muted-foreground/90">
      {children}
    </p>
  );
}

function KeyValueRows({
  rows,
  testId,
}: {
  rows: Array<{ label: string; value: string; testId?: string }>;
  testId?: string;
}) {
  if (rows.length === 0) return null;
  return (
    <dl
      className="space-y-0.5 text-[10px] text-muted-foreground"
      data-testid={testId}
    >
      {rows.map((row) => (
        <div key={row.label} className="flex justify-between gap-2">
          <dt>{row.label}</dt>
          <dd
            className="text-right font-medium text-foreground"
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
    <ul className="list-disc space-y-0.5 pl-4 text-[10px] text-foreground">
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

export function DecisionExplainPanel({
  view,
  loading = false,
  className,
}: DecisionExplainPanelProps) {
  if (loading) {
    return (
      <p
        className={cn("mt-1.5 text-[10px] text-muted-foreground", className)}
        data-testid="decision-explain-panel"
      >
        Cargando explicación…
      </p>
    );
  }
  if (!view) {
    return (
      <p
        className={cn("mt-1.5 text-[10px] text-muted-foreground", className)}
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
    protectionRows.length > 0 ||
    objectiveRows.length > 0 ||
    view.invalidators.length > 0 ||
    authRows.length > 0 ||
    policyRows.length > 0 ||
    traceRows.length > 0;

  if (!hasContent) {
    return (
      <p
        className={cn("mt-1.5 text-[10px] text-muted-foreground", className)}
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
          <ul className="space-y-0.5 text-[10px] text-foreground">
            {view.factors.map((item) => (
              <li
                key={item.id}
                className="flex justify-between gap-2"
                data-testid={`decision-explain-factor-${item.id}`}
                data-state={item.state}
              >
                <span>
                  <span className="font-medium tabular-nums">
                    {factorMark(item.state)}
                  </span>{" "}
                  {item.label}
                </span>
                <span className="text-right text-muted-foreground">
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
          <KeyValueRows rows={entryRows} />
        </section>
      ) : null}

      {protectionRows.length > 0 ? (
        <section data-testid="decision-explain-section-protection">
          <SectionLabel>Protección</SectionLabel>
          <KeyValueRows rows={protectionRows} />
        </section>
      ) : null}

      {objectiveRows.length > 0 ? (
        <section data-testid="decision-explain-section-objectives">
          <SectionLabel>Objetivos</SectionLabel>
          <KeyValueRows rows={objectiveRows} />
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
        <p className="text-[10px] text-muted-foreground">
          {view.authorization.copy}
        </p>
        <KeyValueRows rows={authRows} />
      </section>

      {thesisRows.length > 0 ? (
        <section data-testid="decision-explain-section-thesis">
          <SectionLabel>Tesis</SectionLabel>
          <KeyValueRows rows={thesisRows} />
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
          <KeyValueRows rows={conditionRows} />
          {whyNotItems.length > 0 ? <BulletList items={whyNotItems} /> : null}
        </section>
      ) : null}

      {policyRows.length > 0 ? (
        <section data-testid="decision-explain-section-policy">
          <SectionLabel>Política</SectionLabel>
          <KeyValueRows rows={policyRows} />
        </section>
      ) : null}

      {traceRows.length > 0 ? (
        <section data-testid="decision-explain-section-traceability">
          <SectionLabel>Trazabilidad</SectionLabel>
          <KeyValueRows rows={traceRows} />
        </section>
      ) : null}
    </div>
  );
}
