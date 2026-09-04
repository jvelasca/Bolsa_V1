/**
 * V2.04 — AUTO Desk inside Mercado DECISIÓN.
 * V2.13 — shows what AUTO will do for this instrument (ExitPolicy + journey).
 * Arm ≠ execute · Confirm = firma · Ranking ≠ BUY.
 */

import {
  buildOperatorAutoChecklist,
  buildOperatorAutoPlanPreview,
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
  loadAutoArm,
  saveAutoArm,
} from "@/features/trading/demo-book-auto-arm";
import { resolvePaperAutoPosture } from "@/features/trading/resolve-paper-auto-posture";
import { useDemoBookPrefs } from "@/features/trading/use-demo-book-prefs";
import { useMesaEntriesBlocked } from "@/features/mesa/use-mesa-entries-blocked";

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
};

export function AutoDeskPanel({
  templateId,
  className,
  defaultOpen = false,
  journey = null,
}: AutoDeskPanelProps) {
  const bookPrefs = useDemoBookPrefs();
  const { paperDExecuteEnv, killOn } = useMesaEntriesBlocked();
  const autoArmed = loadAutoArm().armed;
  const posture = resolvePaperAutoPosture({
    bookMode: bookPrefs.mode,
    autoArmed,
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
  });

  function setAutonomy(mode: DemoBookMode) {
    if (mode === "auto") {
      saveAutoArm({
        armed: true,
        armedAt: new Date().toISOString(),
        confirmPhrase: "ACTIVAR AUTO",
      });
      patchDemoBookPrefs({ mode: "auto" });
    } else {
      if (bookPrefs.mode === "auto") {
        saveAutoArm({ armed: false, armedAt: null, confirmPhrase: null });
      }
      patchDemoBookPrefs({ mode });
    }
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
        className="cursor-pointer list-none px-2 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground marker:content-none [&::-webkit-details-marker]:hidden"
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
                    "rounded-md border px-2 py-1 text-[10px] font-medium",
                    active
                      ? "border-sky-600/50 bg-sky-500/15 text-foreground"
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

        <div data-testid="auto-desk-plan-preview">
          <p
            className="text-[10px] font-semibold uppercase tracking-wider text-foreground"
            data-testid="auto-desk-headline"
          >
            {planPreview.headline}
          </p>
          <p className="text-[10px] font-semibold text-foreground">
            AUTO · {planPreview.profileLabel}
          </p>
          <p
            className="text-[10px] text-muted-foreground"
            data-testid="auto-desk-next-action"
          >
            Próxima acción: {planPreview.nextActionTitle}
          </p>
          <dl
            className="mt-1 grid grid-cols-2 gap-x-3 gap-y-0.5 text-[10px] text-muted-foreground"
            data-testid="auto-desk-plan-amounts"
          >
            {planPreview.entry != null ? (
              <div className="flex justify-between gap-2">
                <dt>Entrada</dt>
                <dd className="tabular-nums font-medium text-foreground">
                  {planPreview.entry.toFixed(2)} €
                </dd>
              </div>
            ) : null}
            {planPreview.quantity != null ? (
              <div className="flex justify-between gap-2">
                <dt>Cantidad</dt>
                <dd className="tabular-nums font-medium text-foreground">
                  {planPreview.quantity}
                </dd>
              </div>
            ) : null}
            {planPreview.stop != null ? (
              <div className="flex justify-between gap-2">
                <dt>Stop</dt>
                <dd className="tabular-nums font-medium text-foreground">
                  {planPreview.stop.toFixed(2)} €
                </dd>
              </div>
            ) : null}
            {planPreview.riskAmount != null ? (
              <div className="flex justify-between gap-2">
                <dt>Riesgo</dt>
                <dd className="tabular-nums font-medium text-foreground">
                  {Math.round(planPreview.riskAmount)} €
                </dd>
              </div>
            ) : null}
            {planPreview.t1Price != null ? (
              <div className="flex justify-between gap-2 col-span-2">
                <dt>T1</dt>
                <dd className="tabular-nums font-medium text-foreground">
                  {planPreview.t1Price.toFixed(2)} € · vende {planPreview.t1Pct}
                  %
                </dd>
              </div>
            ) : null}
            {planPreview.t2Price != null ? (
              <div className="flex justify-between gap-2 col-span-2">
                <dt>T2</dt>
                <dd className="tabular-nums font-medium text-foreground">
                  {planPreview.t2Price.toFixed(2)} € · vende {planPreview.t2Pct}
                  %
                </dd>
              </div>
            ) : null}
            {planPreview.remainingPct != null ? (
              <div className="flex justify-between gap-2 col-span-2">
                <dt>RESTANTE</dt>
                <dd
                  className="tabular-nums font-medium text-foreground"
                  data-testid="auto-desk-remaining"
                >
                  {planPreview.remainingPct}%
                </dd>
              </div>
            ) : null}
            <div className="flex justify-between gap-2 col-span-2">
              <dt>Trailing</dt>
              <dd className="font-medium text-foreground">
                {planPreview.trailingAutomatic ? "Automático ✓" : "—"}
              </dd>
            </div>
          </dl>
          <ul className="mt-1 space-y-0.5 text-[10px]">
            {planPreview.items.map((item) => (
              <li
                key={item.id}
                className="flex items-center gap-1.5 text-muted-foreground"
                data-done={item.done ? "1" : "0"}
              >
                <span className="font-semibold text-foreground">
                  {item.done ? "✓" : "○"}
                </span>
                {item.label}
              </li>
            ))}
          </ul>
          {planPreview.ifReachesLines.length > 0 ? (
            <div
              className="mt-1 space-y-0.5"
              data-testid="auto-desk-if-reaches"
            >
              <p className="text-[9px] font-semibold uppercase tracking-wider text-muted-foreground">
                Si alcanza
              </p>
              {planPreview.ifReachesLines.map((line) => (
                <p key={line} className="text-[10px] text-foreground">
                  {line}
                </p>
              ))}
            </div>
          ) : null}
          {planPreview.trailingLine ? (
            <p className="mt-1 text-[10px] text-muted-foreground">
              Trailing: {planPreview.trailingLine}
            </p>
          ) : null}
        </div>

        <p className="text-[10px] text-muted-foreground">
          {checklist.interveneHint}
        </p>
        <p
          className="text-[10px] leading-snug text-muted-foreground"
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
