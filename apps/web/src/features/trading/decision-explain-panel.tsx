/**
 * V1.66 — Panel «¿Por qué?» determinista sobre DecisionExplainViewV1.
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
}: {
  rows: Array<{ label: string; value: string }>;
}) {
  if (rows.length === 0) return null;
  return (
    <dl className="space-y-0.5 text-[10px] text-muted-foreground">
      {rows.map((row) => (
        <div key={row.label} className="flex justify-between gap-2">
          <dt>{row.label}</dt>
          <dd className="text-right font-medium text-foreground">
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
      ? { label: "Entrada", value: view.conditions.entryCondition }
      : null,
  ].filter((row): row is { label: string; value: string } => row != null);

  const whyNotItems = view.conditions.whyNot.map((item) => item.label);

  const policyRows = [
    view.policy.entriesBlocked
      ? { label: "Entradas", value: "Bloqueadas" }
      : null,
    view.policy.gateStatus
      ? { label: "Gate", value: view.policy.gateStatus }
      : null,
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
    thesisRows.length > 0 ||
    signalItems.length > 0 ||
    conditionRows.length > 0 ||
    whyNotItems.length > 0 ||
    view.invalidators.length > 0 ||
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

      {view.invalidators.length > 0 ? (
        <section data-testid="decision-explain-section-invalidators">
          <SectionLabel>Invalidadores</SectionLabel>
          <BulletList items={view.invalidators} />
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
