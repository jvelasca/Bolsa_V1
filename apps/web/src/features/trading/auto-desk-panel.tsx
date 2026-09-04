/**
 * V2.04 — AUTO Desk inside Mercado DECISIÓN.
 * Explains autonomy (Manual / Asistido / Automático) without engineer jargon.
 * Arm ≠ execute · Confirm = firma · Ranking ≠ BUY.
 */

import {
  buildOperatorAutoChecklist,
  type PaperBookModeV1,
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
};

export function AutoDeskPanel({
  templateId,
  className,
  defaultOpen = false,
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

        <ul
          className="space-y-0.5 text-[10px]"
          data-testid="auto-desk-checklist"
        >
          {checklist.items.map((item) => (
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

        <p className="text-[10px] text-muted-foreground">
          {checklist.interveneHint}
        </p>
        <p
          className="text-[10px] leading-snug text-muted-foreground"
          data-testid="auto-desk-honesty"
        >
          {checklist.honestyLine}
        </p>
        {checklist.profilePreview ? (
          <p
            className="text-[10px] text-muted-foreground"
            data-testid="auto-desk-profile"
          >
            Perfil: {checklist.profilePreview}
          </p>
        ) : null}
      </div>
    </details>
  );
}

/** Type re-export for callers that want PaperBookMode without shared import. */
export type AutoDeskBookMode = PaperBookModeV1;
