/**
 * V2.x — NEXT ACTION hero + Risk Box (operator cabin).
 * Display-only · Ranking ≠ BUY · Confirm = firma.
 */

import type {
  OperatorNextActionToneV1,
  OperatorNextActionV1,
  OperatorRiskBoxV1,
  OperatorFourAnswersV1,
  OperatorMissionStepV1,
} from "@bolsa/shared";
import { cn } from "@/lib/utils";
import { formatPrice } from "@/features/charts/chart-utils";

export function nextActionToneClasses(tone: OperatorNextActionToneV1): string {
  switch (tone) {
    case "wait_trigger":
      return "border-amber-600/45 bg-amber-500/10 text-amber-950 dark:text-amber-50";
    case "entry_ready":
      return "border-emerald-600/45 bg-emerald-500/10 text-emerald-950 dark:text-emerald-50";
    case "maintain":
      return "border-sky-600/45 bg-sky-500/10 text-sky-950 dark:text-sky-50";
    case "protect":
      return "border-orange-600/45 bg-orange-500/10 text-orange-950 dark:text-orange-50";
    case "exit":
      return "border-rose-600/45 bg-rose-500/10 text-rose-950 dark:text-rose-50";
    case "review":
      return "border-amber-700/40 bg-amber-500/10";
    case "watch":
    case "none":
    default:
      return "border-border/70 bg-muted/20";
  }
}

export function NextActionHero({
  action,
  className,
  testId = "next-action-hero",
}: {
  action: OperatorNextActionV1;
  className?: string;
  testId?: string;
}) {
  return (
    <div
      className={cn(
        "rounded-md border px-2 py-1.5",
        nextActionToneClasses(action.tone),
        className,
      )}
      data-testid={testId}
      data-next-action-tone={action.tone}
      data-next-action-title={action.title}
    >
      <p className="text-[9px] font-semibold uppercase tracking-wider opacity-80">
        Próxima acción
      </p>
      <p
        className="text-sm font-bold tracking-tight"
        data-testid="next-action-title"
      >
        {action.title}
      </p>
      {action.subtitle ? (
        <p
          className="mt-0.5 text-[10px] leading-snug opacity-90"
          data-testid="next-action-subtitle"
        >
          {action.subtitle}
        </p>
      ) : null}
      {action.ctaHint ? (
        <p
          className="mt-0.5 text-[10px] font-medium opacity-80"
          data-testid="next-action-cta-hint"
        >
          {action.ctaHint}
        </p>
      ) : null}
    </div>
  );
}

function money(n: number | null | undefined): string {
  if (n == null || !Number.isFinite(n)) return "—";
  return `${Math.round(n)} €`;
}

function level(n: number | null | undefined): string {
  if (n == null || !Number.isFinite(n)) return "—";
  return formatPrice(n);
}

function rr(n: number | null | undefined): string {
  if (n == null || !Number.isFinite(n)) return "—";
  return `1 : ${n.toFixed(2)}`;
}

export function OperatorRiskBox({
  box,
  className,
}: {
  box: OperatorRiskBoxV1;
  className?: string;
}) {
  const hasAny =
    box.entry != null ||
    box.stop != null ||
    box.lossAtStop != null ||
    box.maxLoss != null ||
    box.rrT1 != null;
  if (!hasAny) return null;

  return (
    <div
      className={cn(
        "space-y-1 rounded-md border border-border/60 bg-background/40 px-2 py-1.5",
        className,
      )}
      data-testid="operator-risk-box"
    >
      <p className="text-[9px] font-semibold uppercase tracking-wider text-muted-foreground">
        Riesgo
      </p>
      <dl className="grid grid-cols-2 gap-x-3 gap-y-0.5 text-[10px] text-muted-foreground">
        {box.capital != null ? (
          <div className="flex justify-between gap-2">
            <dt>Capital</dt>
            <dd className="font-medium tabular-nums text-foreground">
              {money(box.capital)}
            </dd>
          </div>
        ) : null}
        {box.riskPct != null ? (
          <div className="flex justify-between gap-2">
            <dt>Riesgo</dt>
            <dd className="font-medium tabular-nums text-foreground">
              {box.riskPct.toFixed(1)}%
            </dd>
          </div>
        ) : null}
        {(box.maxLoss != null || box.lossAtStop != null) && (
          <div className="flex justify-between gap-2">
            <dt>Pérdida máx.</dt>
            <dd
              className="font-medium tabular-nums text-foreground"
              data-testid="risk-box-max-loss"
            >
              {money(box.maxLoss ?? box.lossAtStop)}
            </dd>
          </div>
        )}
        <div className="flex justify-between gap-2">
          <dt>Entrada</dt>
          <dd className="font-medium tabular-nums text-foreground">
            {level(box.entry)}
          </dd>
        </div>
        <div className="flex justify-between gap-2">
          <dt>Stop</dt>
          <dd className="font-medium tabular-nums text-foreground">
            {level(box.stop)}
          </dd>
        </div>
        <div className="flex justify-between gap-2">
          <dt>R/R T1</dt>
          <dd
            className="font-medium tabular-nums text-foreground"
            data-testid="risk-box-rr-t1"
          >
            {rr(box.rrT1)}
          </dd>
        </div>
        <div className="flex justify-between gap-2">
          <dt>R/R T2</dt>
          <dd
            className="font-medium tabular-nums text-foreground"
            data-testid="risk-box-rr-t2"
          >
            {rr(box.rrT2)}
          </dd>
        </div>
      </dl>
    </div>
  );
}

export function OperatorFourAnswersBlock({
  answers,
}: {
  answers: OperatorFourAnswersV1;
}) {
  const rows: Array<{ id: string; label: string; value: string | null }> = [
    { id: "thesis", label: "Tesis", value: answers.thesis },
    { id: "trigger", label: "Trigger", value: answers.trigger },
    { id: "risk", label: "Stop + riesgo", value: answers.risk },
    { id: "plan", label: "Plan", value: answers.plan },
  ];
  if (!rows.some((r) => r.value)) return null;
  return (
    <div className="space-y-0.5" data-testid="operator-four-answers">
      <p className="text-[9px] font-semibold uppercase tracking-wider text-muted-foreground">
        Resumen
      </p>
      <dl className="space-y-0.5 text-[10px] text-muted-foreground">
        {rows.map((r) =>
          r.value ? (
            <div key={r.id} className="flex justify-between gap-2">
              <dt className="shrink-0">{r.label}</dt>
              <dd
                className="text-right font-medium text-foreground"
                data-testid={`four-answers-${r.id}`}
              >
                {r.value}
              </dd>
            </div>
          ) : null,
        )}
      </dl>
    </div>
  );
}

function missionMark(status: OperatorMissionStepV1["status"]): string {
  switch (status) {
    case "done":
      return "✓";
    case "active":
      return "●";
    case "pending":
      return "○";
    default:
      return "—";
  }
}

export function OperatorMissionChecklist({
  steps,
}: {
  steps: OperatorMissionStepV1[];
}) {
  return (
    <ul
      className="space-y-0.5 text-[10px]"
      data-testid="operator-mission-checklist"
    >
      {steps.map((step) => (
        <li
          key={step.id}
          className="flex items-baseline justify-between gap-2 text-muted-foreground"
          data-testid={`mission-step-${step.id}`}
          data-status={step.status}
        >
          <span>
            <span className="mr-1 font-semibold text-foreground">
              {missionMark(step.status)}
            </span>
            {step.label}
          </span>
          <span className="tabular-nums font-medium text-foreground">
            {step.detail ?? "—"}
          </span>
        </li>
      ))}
    </ul>
  );
}
