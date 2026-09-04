/**
 * V2.04 — AUTO Desk inside Mercado DECISIÓN.
 * V2.13 — shows what AUTO will do for this instrument (ExitPolicy + journey).
 * V2.36 — timeline = OperatorPositionPlan ladder (same as Mercado L3).
 * V2.39 — AUTO arm honesty: misma puerta A3 que Cuentas (tryArmAuto + frase).
 * Arm ≠ execute · Confirm = firma · Ranking ≠ BUY.
 */

import { useState } from "react";
import {
  buildOperatorAutoChecklist,
  buildOperatorAutoPlanPreview,
  buildOperatorPositionPlan,
  resolveOperatorNextAction,
  type PaperBookModeV1,
  type PositionJourneyReadoutV1,
} from "@bolsa/shared";
import { cn } from "@/lib/utils";
import {
  patchDemoBookPrefs,
  type DemoBookMode,
} from "@/features/trading/demo-book-prefs";
import {
  DemoBookAutoArmForm,
  useAutoArmState,
} from "@/features/trading/demo-book-auto-arm-form";
import { resolvePaperAutoPosture } from "@/features/trading/resolve-paper-auto-posture";
import { useDemoBookPrefs } from "@/features/trading/use-demo-book-prefs";
import { useMesaEntriesBlocked } from "@/features/mesa/use-mesa-entries-blocked";
import { CABIN_TOUCH_TARGET } from "@/features/trading/cabin-visual";
import {
  CABIN_KV_GRID,
  CABIN_TYPE,
  cabinNumClass,
  OperatorPositionPlan,
} from "@/features/trading/operator-cabin-ui";

const AUTONOMY_OPTIONS: Array<{
  mode: DemoBookMode;
  label: string;
  hint: string;
}> = [
  {
    mode: "manual",
    label: "Manual",
    hint: "Tú operas desde el gráfico",
  },
  {
    mode: "semi",
    label: "Asistido",
    hint: "La app propone · tú firmas en Confirm",
  },
  {
    mode: "auto",
    label: "Automático",
    hint: "Gestión automática · puedes intervenir",
  },
];

type AutoDeskPanelProps = {
  templateId?: string | null;
  className?: string;
  /** Collapsed by default in density-normal; parent can force open. */
  defaultOpen?: boolean;
  /** V2.13 — instrument journey for «qué hará AUTO». */
  journey?: PositionJourneyReadoutV1 | null;
  /** V2.36 — birth qty for RESTANTE % (same projection as Mercado L3). */
  birthQuantity?: number | null;
};

export function AutoDeskPanel({
  templateId,
  className,
  defaultOpen = false,
  journey = null,
  birthQuantity = null,
}: AutoDeskPanelProps) {
  const bookPrefs = useDemoBookPrefs();
  const { paperDExecuteEnv, killOn } = useMesaEntriesBlocked();
  const arm = useAutoArmState();
  const [armOpen, setArmOpen] = useState(false);
  const posture = resolvePaperAutoPosture({
    bookMode: bookPrefs.mode,
    autoArmed: arm.armed,
    paperDExecuteEnv,
  });
  const checklist = buildOperatorAutoChecklist({
    posture,
    templateId,
    killOn,
  });
  const nextAction = resolveOperatorNextAction(
    journey
      ? {
          kind: "position",
          primaryAction: journey.primaryAction,
          journey,
        }
      : { kind: "cockpit_phase", phase: "posicion" },
  );
  const planPreview = buildOperatorAutoPlanPreview({
    journey,
    templateId,
    nextAction,
    posture,
    killOn,
    birthQuantity,
  });
  const positionPlan =
    journey != null
      ? buildOperatorPositionPlan(journey, { birthQuantity })
      : null;

  function requestAutoMode() {
    if (arm.armed) {
      patchDemoBookPrefs({ mode: "auto" });
      setArmOpen(false);
      return;
    }
    setArmOpen(true);
  }

  function setAutonomy(mode: DemoBookMode) {
    if (mode === "auto") {
      requestAutoMode();
      return;
    }
    setArmOpen(false);
    // D3: patchDemoBookPrefs desarma al salir de auto.
    patchDemoBookPrefs({ mode });
  }

  return (
    <details
      className={cn(
        "rounded-md border border-border/60 bg-background/30",
        className,
      )}
      data-testid="auto-desk-panel"
      open={defaultOpen || undefined}
    >
      <summary
        className={cn(
          CABIN_TYPE.eyebrow,
          "cursor-pointer list-none px-2 py-1.5 marker:content-none [&::-webkit-details-marker]:hidden",
        )}
        data-testid="auto-desk-summary"
      >
        <span className="sr-only">Panel de </span>
        Gestión automática · {checklist.autonomyLabel}
      </summary>
      <div className="space-y-2 border-t border-border/40 px-2 py-1.5">
        <fieldset data-testid="auto-desk-autonomy">
          <legend className="sr-only">Autonomía</legend>
          <div className="flex flex-wrap gap-1">
            {AUTONOMY_OPTIONS.map((opt) => {
              const active =
                opt.mode === "auto"
                  ? posture.autoActive
                  : bookPrefs.mode === opt.mode && !posture.autoActive;
              return (
                <button
                  key={opt.mode}
                  type="button"
                  className={cn(
                    CABIN_TOUCH_TARGET,
                    CABIN_TYPE.meta,
                    "rounded-md border px-3 font-medium text-foreground",
                    active
                      ? "border-sky-600/50 bg-sky-500/15"
                      : "border-border/60 bg-muted/10 text-muted-foreground hover:bg-accent",
                  )}
                  aria-pressed={active}
                  data-testid={`auto-desk-mode-${opt.mode}`}
                  title={opt.hint}
                  onClick={() => setAutonomy(opt.mode)}
                >
                  {active ? "● " : "○ "}
                  {opt.label}
                </button>
              );
            })}
          </div>
        </fieldset>

        {armOpen ? (
          <DemoBookAutoArmForm
            onArmed={() => {
              patchDemoBookPrefs({ mode: "auto" });
              setArmOpen(false);
            }}
            onCancel={() => setArmOpen(false)}
          />
        ) : null}

        <div data-testid="auto-desk-plan-preview">
          <p
            className={cn(CABIN_TYPE.eyebrow, "text-foreground")}
            data-testid="auto-desk-headline"
          >
            {planPreview.headline}
          </p>
          <p className={cn(CABIN_TYPE.operativa, "font-semibold")}>
            AUTO · {planPreview.profileLabel}
          </p>
          <p className={CABIN_TYPE.meta} data-testid="auto-desk-next-action">
            Próxima acción:{" "}
            <span className={cn(CABIN_TYPE.operativa, "font-semibold")}>
              {planPreview.nextActionTitle}
            </span>
          </p>
          <dl
            className={cn(CABIN_KV_GRID, "mt-1")}
            data-testid="auto-desk-plan-amounts"
          >
            {planPreview.entry != null ? (
              <div className="flex justify-between gap-2">
                <dt>Entrada</dt>
                <dd className={cabinNumClass()}>
                  {planPreview.entry.toFixed(2)} €
                </dd>
              </div>
            ) : null}
            {planPreview.quantity != null ? (
              <div className="flex justify-between gap-2">
                <dt>Cantidad</dt>
                <dd className={cabinNumClass()}>{planPreview.quantity}</dd>
              </div>
            ) : null}
            {planPreview.stop != null ? (
              <div className="flex justify-between gap-2">
                <dt>Stop</dt>
                <dd className={cabinNumClass()}>
                  {planPreview.stop.toFixed(2)} €
                </dd>
              </div>
            ) : null}
            {planPreview.riskAmount != null ? (
              <div className="flex justify-between gap-2">
                <dt>Riesgo</dt>
                <dd className={cabinNumClass()}>
                  {Math.round(planPreview.riskAmount)} €
                </dd>
              </div>
            ) : null}
            {planPreview.t1Price != null ? (
              <div className="flex justify-between gap-2 col-span-2">
                <dt>T1</dt>
                <dd className={cabinNumClass()}>
                  {planPreview.t1Price.toFixed(2)} € · vende {planPreview.t1Pct}
                  %
                </dd>
              </div>
            ) : null}
            {planPreview.t2Price != null ? (
              <div className="flex justify-between gap-2 col-span-2">
                <dt>T2</dt>
                <dd className={cabinNumClass()}>
                  {planPreview.t2Price.toFixed(2)} € · vende {planPreview.t2Pct}
                  %
                </dd>
              </div>
            ) : null}
            {planPreview.remainingPct != null ? (
              <div className="flex justify-between gap-2 col-span-2">
                <dt>RESTANTE</dt>
                <dd
                  className={cabinNumClass()}
                  data-testid="auto-desk-remaining"
                >
                  {planPreview.remainingPct}%
                </dd>
              </div>
            ) : null}
            <div className="flex justify-between gap-2 col-span-2">
              <dt>Trailing</dt>
              <dd
                className={cn(
                  CABIN_TYPE.operativa,
                  "font-medium text-foreground",
                )}
              >
                {planPreview.trailingAutomatic ? "Automático ✓" : "—"}
              </dd>
            </div>
          </dl>
          {positionPlan != null ? (
            <div className="mt-1.5" data-testid="auto-desk-position-plan">
              <OperatorPositionPlan plan={positionPlan} />
            </div>
          ) : null}
          {planPreview.ifReachesLines.length > 0 ? (
            <div
              className="mt-1 space-y-0.5"
              data-testid="auto-desk-if-reaches"
            >
              <p className={CABIN_TYPE.eyebrow}>Si alcanza</p>
              {planPreview.ifReachesLines.map((line) => (
                <p
                  key={line}
                  className={cn(CABIN_TYPE.operativa, "text-foreground")}
                >
                  {line}
                </p>
              ))}
            </div>
          ) : null}
          {planPreview.trailingLine ? (
            <p className={cn(CABIN_TYPE.meta, "mt-1")}>
              Trailing: {planPreview.trailingLine}
            </p>
          ) : null}
        </div>

        <p className={CABIN_TYPE.meta}>{checklist.interveneHint}</p>
        <p
          className={cn(CABIN_TYPE.meta, "leading-snug")}
          data-testid="auto-desk-honesty"
        >
          {planPreview.honestyLine}
        </p>
      </div>
    </details>
  );
}

/** Type re-export for callers that want PaperBookMode without shared import. */
export type AutoDeskBookMode = PaperBookModeV1;
