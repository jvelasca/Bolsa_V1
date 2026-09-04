/** V2.x — NEXT ACTION hero + Risk Box (operator cabin).
 * V2.24 — composición 4 niveles (auditor §6).
 * V2.25 — densidad · tipografía · color semántico · vacíos/loading · a11y.
 * V2.28 — PLAN DE LA POSICIÓN (Mission + Exit Route fused).
 * V2.31 — Premium Visual System (3 tamaños · números tabulares · menos cards).
 * Display-only · Ranking ≠ BUY · Confirm = firma.
 */

import type { ReactNode } from "react";
import { useId } from "react";
import type {
  OperatorNextActionToneV1,
  OperatorNextActionV1,
  OperatorRiskBoxV1,
  OperatorFourAnswersV1,
  OperatorMissionStepV1,
  OperatorProtectionStateV1,
  OperatorExitLadderV1,
  OperatorExitLadderRungV1,
  OperatorPositionPlanV1,
  OperatorPositionPlanStepV1,
} from "@bolsa/shared";
import { cn } from "@/lib/utils";
import { formatPrice } from "@/features/charts/chart-utils";
import {
  CABIN_KV_GRID,
  CABIN_NUM,
  CABIN_TYPE,
  CABIN_VISUAL_VERSION,
  cabinNumClass,
} from "@/features/trading/cabin-visual";

export {
  CABIN_KV_GRID,
  CABIN_NUM,
  CABIN_TYPE,
  CABIN_VISUAL_VERSION,
  cabinNumClass,
  cabinNumTone,
} from "@/features/trading/cabin-visual";

/** V2.24 / V2.28 — jerarquía definitiva de la cabina DECISIÓN. */
export const CABIN_LEVEL_QUESTIONS = {
  1: "¿Qué hago ahora?",
  2: "¿Con qué riesgo?",
  3: "¿Cuál es el plan?",
  4: "¿Por qué?",
} as const;

export type OperatorCabinLevelId = 1 | 2 | 3 | 4;

export function CabinSectionLabel({ children }: { children: string }) {
  return <p className={CABIN_TYPE.eyebrow}>{children}</p>;
}

/** V2.25 — foco teclado en controles de cabina. */
export const CABIN_FOCUS_RING =
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-600/45 focus-visible:ring-offset-1 focus-visible:ring-offset-background";

export const CABIN_INTERACTIVE = cn(
  CABIN_TYPE.meta,
  "font-medium text-foreground/90 underline-offset-2 hover:underline",
  CABIN_FOCUS_RING,
);

const LEVEL_STACK: Record<OperatorCabinLevelId, string> = {
  1: "space-y-1.5",
  2: "space-y-1",
  3: "space-y-1",
  4: "space-y-0.5",
};

export function OperatorCabinLevel({
  level,
  children,
  className,
  showQuestion = true,
}: {
  level: OperatorCabinLevelId;
  children: ReactNode;
  className?: string;
  /** L1 often omits — NextActionHero already labels «Próxima acción». */
  showQuestion?: boolean;
}) {
  const question = CABIN_LEVEL_QUESTIONS[level];
  return (
    <div
      className={cn(LEVEL_STACK[level], "min-w-0", className)}
      data-testid={`cabin-level-${level}`}
      data-cabin-level={level}
      data-cabin-density="v2.25"
      data-cabin-visual={CABIN_VISUAL_VERSION}
      aria-label={question}
    >
      {showQuestion ? (
        <p
          className={CABIN_TYPE.eyebrow}
          data-testid={`cabin-level-${level}-label`}
        >
          {question}
        </p>
      ) : null}
      {children}
    </div>
  );
}

export type OperatorCabinStatusKind = "loading" | "empty" | "error";

/** V2.25 — estados vacíos / loading / error (display-only). */
export function OperatorCabinStatus({
  kind,
  children,
  className,
  testId,
}: {
  kind: OperatorCabinStatusKind;
  children: ReactNode;
  className?: string;
  testId?: string;
}) {
  return (
    <p
      className={cn(
        "rounded-md border px-2 py-1.5",
        CABIN_TYPE.operativa,
        kind === "loading" &&
          "border-border/50 bg-muted/15 text-muted-foreground",
        kind === "empty" &&
          "border-border/60 bg-muted/10 text-muted-foreground",
        kind === "error" &&
          "border-rose-600/40 bg-rose-500/10 text-rose-950 dark:text-rose-50",
        className,
      )}
      role={kind === "error" ? "alert" : "status"}
      aria-live={kind === "loading" ? "polite" : undefined}
      data-testid={testId ?? `cabin-status-${kind}`}
      data-cabin-status={kind}
    >
      {children}
    </p>
  );
}

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
  const statusLabel = action.subtitle
    ? `${action.title}. ${action.subtitle}`
    : action.title;
  const levels = action.levels;
  const levelBits = [
    levels?.entry != null ? `Entrada ${formatPrice(levels.entry)}` : null,
    levels?.trigger != null && levels.trigger !== levels.entry
      ? `Trigger ${formatPrice(levels.trigger)}`
      : null,
    levels?.stop != null ? `Stop ${formatPrice(levels.stop)}` : null,
  ].filter(Boolean);
  return (
    <div
      className={cn(
        "min-w-0 rounded-md border px-2.5 py-2",
        nextActionToneClasses(action.tone),
        className,
      )}
      role="status"
      aria-live="polite"
      aria-label={`Próxima acción: ${statusLabel}`}
      data-testid={testId}
      data-next-action-tone={action.tone}
      data-next-action-title={action.title}
      data-cabin-density="v2.25"
      data-cabin-visual={CABIN_VISUAL_VERSION}
    >
      <p className={cn(CABIN_TYPE.eyebrow, "opacity-80")}>Próxima acción</p>
      <p className={CABIN_TYPE.hero} data-testid="next-action-title">
        {action.title}
      </p>
      {action.subtitle ? (
        <p
          className={cn("mt-0.5 opacity-90", CABIN_TYPE.operativa)}
          data-testid="next-action-subtitle"
        >
          {action.subtitle}
        </p>
      ) : null}
      {action.reasons && action.reasons.length > 0 ? (
        <ul
          className={cn("mt-1 space-y-0.5 opacity-90", CABIN_TYPE.meta)}
          data-testid="next-action-reasons"
        >
          <li className="font-semibold">Porque:</li>
          {action.reasons.map((r) => (
            <li
              key={r.id}
              data-reason-id={r.id}
              data-reason-ok={r.ok ? "1" : "0"}
            >
              {r.ok ? "✓" : "○"} {r.label}
            </li>
          ))}
        </ul>
      ) : null}
      {action.nextChange ? (
        <p
          className={cn("mt-0.5 opacity-90", CABIN_TYPE.meta)}
          data-testid="next-action-next-change"
        >
          <span className="font-semibold">Próximo cambio:</span>{" "}
          {action.nextChange}
        </p>
      ) : null}
      {levelBits.length > 0 ? (
        <p
          className={cn("mt-0.5 opacity-85", cabinNumClass())}
          data-testid="next-action-levels"
        >
          {levelBits.join(" · ")}
        </p>
      ) : null}
      {action.condition ? (
        <p
          className={cn("mt-0.5 opacity-75", CABIN_TYPE.meta)}
          data-testid="next-action-condition"
        >
          <span className="font-semibold">Condición:</span> {action.condition}
        </p>
      ) : null}
      {action.expires ? (
        <p
          className={cn("mt-0.5 opacity-70", CABIN_TYPE.meta)}
          data-testid="next-action-expires"
        >
          <span className="font-semibold">Caduca:</span> {action.expires}
        </p>
      ) : null}
      {action.ctaHint ? (
        <p
          className={cn("mt-1 font-medium opacity-80", CABIN_TYPE.meta)}
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
  const labelId = useId();
  const hasAny =
    box.entry != null ||
    box.stop != null ||
    box.lossAtStop != null ||
    box.maxLoss != null ||
    box.rrT1 != null ||
    box.quantity != null;
  if (!hasAny) return null;

  return (
    <div
      className={cn("min-w-0 space-y-1", className)}
      data-testid="operator-risk-box"
      data-cabin-density="v2.25"
      data-cabin-visual={CABIN_VISUAL_VERSION}
      aria-labelledby={labelId}
    >
      <p id={labelId} className={CABIN_TYPE.eyebrow}>
        Riesgo · tamaño
      </p>
      <dl className={CABIN_KV_GRID}>
        {box.capital != null ? (
          <div className="flex justify-between gap-2">
            <dt>Capital</dt>
            <dd className={CABIN_TYPE.value}>{money(box.capital)}</dd>
          </div>
        ) : null}
        {box.riskPct != null ? (
          <div className="flex justify-between gap-2">
            <dt>Riesgo %</dt>
            <dd className={CABIN_TYPE.value}>{box.riskPct.toFixed(1)}%</dd>
          </div>
        ) : null}
        {(box.maxLoss != null || box.lossAtStop != null) && (
          <div className="flex justify-between gap-2">
            <dt>Pérdida máx.</dt>
            <dd className={CABIN_TYPE.value} data-testid="risk-box-max-loss">
              {money(box.maxLoss ?? box.lossAtStop)}
            </dd>
          </div>
        )}
        <div className="flex justify-between gap-2">
          <dt>Entrada</dt>
          <dd className={CABIN_TYPE.value}>{level(box.entry)}</dd>
        </div>
        <div className="flex justify-between gap-2">
          <dt>Stop</dt>
          <dd className={CABIN_TYPE.value}>{level(box.stop)}</dd>
        </div>
        {box.stopDistancePct != null ? (
          <div className="flex justify-between gap-2">
            <dt>Distancia</dt>
            <dd className={CABIN_TYPE.value} data-testid="risk-box-distance">
              {box.stopDistancePct.toFixed(1)}%
            </dd>
          </div>
        ) : null}
        {box.quantity != null ? (
          <div className="flex justify-between gap-2">
            <dt>Cantidad</dt>
            <dd className={CABIN_TYPE.value} data-testid="risk-box-quantity">
              {box.quantity}
            </dd>
          </div>
        ) : null}
        {box.positionValue != null ? (
          <div className="flex justify-between gap-2">
            <dt>Valor</dt>
            <dd
              className={CABIN_TYPE.value}
              data-testid="risk-box-position-value"
            >
              {money(box.positionValue)}
            </dd>
          </div>
        ) : null}
        {box.portfolioPct != null ? (
          <div className="flex justify-between gap-2">
            <dt>% cartera</dt>
            <dd
              className={CABIN_TYPE.value}
              data-testid="risk-box-portfolio-pct"
            >
              {box.portfolioPct.toFixed(1)}%
            </dd>
          </div>
        ) : null}
        <div className="flex justify-between gap-2">
          <dt>R/R T1</dt>
          <dd className={CABIN_TYPE.value} data-testid="risk-box-rr-t1">
            {rr(box.rrT1)}
          </dd>
        </div>
        <div className="flex justify-between gap-2">
          <dt>R/R T2</dt>
          <dd className={CABIN_TYPE.value} data-testid="risk-box-rr-t2">
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
  const labelId = useId();
  const rows: Array<{ id: string; label: string; value: string | null }> = [
    { id: "thesis", label: "Tesis", value: answers.thesis },
    { id: "trigger", label: "Trigger", value: answers.trigger },
    { id: "risk", label: "Stop + riesgo", value: answers.risk },
    { id: "plan", label: "Plan", value: answers.plan },
  ];
  if (!rows.some((r) => r.value)) return null;
  return (
    <div className="min-w-0 space-y-0.5" data-testid="operator-four-answers">
      <p id={labelId} className={CABIN_TYPE.eyebrow}>
        Resumen
      </p>
      <dl
        className={cn("space-y-0.5", CABIN_TYPE.meta)}
        aria-labelledby={labelId}
      >
        {rows.map((r) =>
          r.value ? (
            <div key={r.id} className="flex justify-between gap-2">
              <dt className="shrink-0">{r.label}</dt>
              <dd
                className={cn(CABIN_TYPE.operativa, "text-right font-medium")}
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

function missionMark(status: OperatorMissionStepV1["status"]): {
  symbol: string;
  sr: string;
} {
  switch (status) {
    case "done":
      return { symbol: "✓", sr: "hecho" };
    case "active":
      return { symbol: "●", sr: "en curso" };
    case "pending":
      return { symbol: "○", sr: "pendiente" };
    default:
      return { symbol: "—", sr: "sin estado" };
  }
}

function missionStepClasses(status: OperatorMissionStepV1["status"]): string {
  switch (status) {
    case "active":
      return "border-l-2 border-sky-600/70 pl-1.5 font-semibold text-sky-950 dark:text-sky-50";
    case "done":
      return "opacity-80";
    case "pending":
    default:
      return "text-muted-foreground";
  }
}

export function OperatorMissionChecklist({
  steps,
}: {
  steps: OperatorMissionStepV1[];
}) {
  return (
    <ul
      className={cn("space-y-0.5", CABIN_TYPE.operativa)}
      data-testid="operator-mission-checklist"
      aria-label="Misión de la posición"
    >
      {steps.map((step) => {
        const mark = missionMark(step.status);
        return (
          <li
            key={step.id}
            className={cn(
              "flex items-baseline justify-between gap-2",
              missionStepClasses(step.status),
            )}
            data-testid={`mission-step-${step.id}`}
            data-status={step.status}
          >
            <span>
              <span className="sr-only">{mark.sr}. </span>
              <span
                className="mr-1 font-semibold text-foreground"
                aria-hidden="true"
              >
                {mark.symbol}
              </span>
              {step.label}
            </span>
            <span className={cn(CABIN_NUM.base, CABIN_NUM.neu)}>
              {step.detail ?? "—"}
            </span>
          </li>
        );
      })}
    </ul>
  );
}

function ladderRungTone(status: OperatorExitLadderRungV1["status"]): string {
  switch (status) {
    case "done":
      return "text-emerald-800 dark:text-emerald-200";
    case "active":
      return "border-l-2 border-sky-600/70 pl-1.5 font-semibold text-sky-950 dark:text-sky-50";
    case "pending":
    default:
      return "text-muted-foreground";
  }
}

/**
 * V2.28 — single PLAN DE LA POSICIÓN (Mission + Exit Route).
 * Exposes mission-step-* + exit-ladder-* testids for contractual surfaces.
 */
export function OperatorPositionPlan({
  plan,
  className,
}: {
  plan: OperatorPositionPlanV1;
  className?: string;
}) {
  if (plan.steps.length === 0) return null;
  return (
    <div
      className={cn("min-w-0 space-y-0", className)}
      data-testid="operator-position-plan"
      data-cabin-density="v2.25"
      data-cabin-visual={CABIN_VISUAL_VERSION}
      aria-label="Plan de la posición"
    >
      <p className={CABIN_TYPE.eyebrow}>Plan de la posición</p>
      <ol
        className="mt-1 space-y-0"
        data-testid="operator-mission-checklist"
        aria-label="Plan de la posición"
      >
        {plan.steps.map((step, idx) => {
          const mark = missionMark(step.status);
          const isLast = idx === plan.steps.length - 1;
          const ladderId =
            step.id === "protection"
              ? "stop"
              : step.id === "exit"
                ? null
                : step.id;
          return (
            <li
              key={step.id}
              className="relative"
              data-testid={
                ladderId != null
                  ? `exit-ladder-rung-${ladderId}`
                  : `position-plan-step-${step.id}`
              }
              data-status={step.status}
              data-reduce-pct={
                step.reducePct != null ? String(step.reducePct) : undefined
              }
            >
              <div
                className={cn(
                  "flex items-baseline justify-between gap-2 py-0.5",
                  CABIN_TYPE.operativa,
                  ladderRungTone(step.status),
                )}
                data-testid={`mission-step-${step.missionId}`}
                data-status={step.status}
              >
                <span>
                  <span className="sr-only">{mark.sr}. </span>
                  <span className="mr-1 font-semibold" aria-hidden="true">
                    {mark.symbol}
                  </span>
                  <span className="font-semibold text-foreground">
                    {step.label}
                  </span>
                  {step.reducePct != null ? (
                    <span
                      className={cn("ml-1 opacity-90", CABIN_NUM.base)}
                      data-testid={`exit-ladder-pct-${ladderId ?? step.id}`}
                    >
                      · {step.reducePct}%
                    </span>
                  ) : null}
                </span>
                <span className={cn(CABIN_NUM.base, CABIN_NUM.neu)}>
                  {step.detail ?? "—"}
                </span>
              </div>
              {!isLast ? (
                <div
                  className="mx-3 h-2 w-px bg-border/70"
                  aria-hidden="true"
                  data-testid="exit-ladder-connector"
                />
              ) : null}
            </li>
          );
        })}
      </ol>
      {plan.remainingDetail != null || plan.remainingPct != null ? (
        <p
          className={cn("mt-1", CABIN_TYPE.meta)}
          data-testid="exit-ladder-remaining"
        >
          RESTANTE{" "}
          <span className={cn(CABIN_NUM.base, CABIN_NUM.neu)}>
            {plan.remainingDetail ??
              (plan.remainingPct != null ? `${plan.remainingPct}%` : "—")}
          </span>
        </p>
      ) : null}
    </div>
  );
}

/** @deprecated V2.28 — use OperatorPositionPlan. Thin adapter for ladder-shaped props. */
export function OperatorExitLadder({
  ladder,
}: {
  ladder: OperatorExitLadderV1;
}) {
  const steps: OperatorPositionPlanStepV1[] = ladder.rungs.map(
    (rung): OperatorPositionPlanStepV1 => ({
      id: rung.id === "stop" ? "protection" : rung.id,
      missionId:
        rung.id === "stop"
          ? "stop"
          : rung.id === "entry"
            ? "entry"
            : rung.id === "t1"
              ? "t1"
              : rung.id === "t2"
                ? "t2"
                : "trail",
      label:
        rung.id === "stop"
          ? "Protección"
          : rung.id === "trail"
            ? "Gestión / trailing"
            : rung.label,
      detail: rung.detail,
      status: rung.status,
      reducePct: rung.reducePct,
    }),
  );
  if (ladder.remainingPct != null || ladder.remainingDetail != null) {
    steps.push({
      id: "exit",
      missionId: "remaining",
      label: "Salida final",
      detail:
        ladder.remainingDetail != null
          ? `RESTANTE ${ladder.remainingDetail}`
          : ladder.remainingPct != null
            ? `RESTANTE ${ladder.remainingPct}%`
            : null,
      status: "active",
      reducePct: null,
    });
  }
  const plan: OperatorPositionPlanV1 = {
    profileLabel: ladder.profileLabel,
    remainingPct: ladder.remainingPct,
    remainingDetail: ladder.remainingDetail,
    steps,
  };
  return (
    <div data-testid="operator-exit-ladder">
      <OperatorPositionPlan plan={plan} />
    </div>
  );
}

function protectionToneClasses(protection: OperatorProtectionStateV1): string {
  if (protection.kind === "emergency") {
    return "border-orange-600/45 bg-orange-500/10 text-orange-950 dark:text-orange-50";
  }
  if (protection.phase === "protected" || protection.kind === "technical") {
    return "border-emerald-600/40 bg-emerald-500/10 text-emerald-950 dark:text-emerald-50";
  }
  if (protection.phase === "sent" || protection.phase === "confirmed") {
    return "border-amber-600/45 bg-amber-500/10 text-amber-950 dark:text-amber-50";
  }
  if (protection.phase === "planned") {
    return "border-sky-600/40 bg-sky-500/10 text-sky-950 dark:text-sky-50";
  }
  return "border-rose-600/45 bg-rose-500/10 text-rose-950 dark:text-rose-50";
}

/** V2.29 — Protection State: Planificado / Confirmado / Enviado / Protegido. */
export function OperatorProtectionLine({
  protection,
}: {
  protection: OperatorProtectionStateV1;
}) {
  const executed =
    protection.stop != null && Number.isFinite(protection.stop)
      ? formatPrice(protection.stop)
      : null;
  const planned =
    protection.plannedStop != null && Number.isFinite(protection.plannedStop)
      ? formatPrice(protection.plannedStop)
      : null;
  const showPlanVsExec =
    planned != null &&
    (executed == null ||
      (protection.stop != null &&
        protection.plannedStop != null &&
        Math.abs(protection.stop - protection.plannedStop) > 0.0001));

  const mark =
    protection.phase === "protected"
      ? protection.kind === "emergency"
        ? "▲"
        : "●"
      : protection.phase === "sent" || protection.phase === "confirmed"
        ? "◐"
        : protection.phase === "planned"
          ? "○"
          : "■";

  const detailBits: string[] = [];
  if (protection.kind === "emergency" && protection.phase === "protected") {
    detailBits.push("emergencia");
  } else if (protection.isTechnical) {
    detailBits.push("técnico");
  }
  if (executed) {
    detailBits.unshift(executed);
  } else if (planned && protection.phase === "planned") {
    detailBits.unshift(`Plan ${planned}`);
  }

  return (
    <div
      className={cn(
        "flex min-w-0 flex-col gap-0.5 rounded-md border px-2 py-1",
        CABIN_TYPE.operativa,
        protectionToneClasses(protection),
      )}
      role="status"
      aria-live="polite"
      aria-label={`Protección: ${protection.phaseLabel}${executed ? ` ${executed}` : planned ? ` plan ${planned}` : ""}`}
      data-testid="operator-protection-line"
      data-protection-kind={protection.kind}
      data-protection-honesty={protection.honesty}
      data-protection-phase={protection.phase}
      data-protection-technical={protection.isTechnical ? "1" : "0"}
      data-cabin-density="v2.25"
      data-cabin-visual={CABIN_VISUAL_VERSION}
    >
      <div className="flex min-w-0 items-baseline justify-between gap-2">
        <span className="font-semibold uppercase tracking-wide opacity-80">
          Protección
        </span>
        <span className="font-medium" data-testid="operator-protection-label">
          <span aria-hidden="true">{mark} </span>
          {protection.phaseLabel}
          {detailBits.length > 0 ? ` · ${detailBits.join(" · ")}` : ""}
        </span>
      </div>
      {showPlanVsExec ? (
        <p
          className={cn("leading-snug opacity-85", CABIN_TYPE.meta)}
          data-testid="operator-protection-plan-vs-exec"
        >
          Plan {planned}
          {" · "}
          {executed ? `Ejecución ${executed}` : "Ejecución pendiente"}
        </p>
      ) : null}
    </div>
  );
}
