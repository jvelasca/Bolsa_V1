/**
 * AUTO UI REFACTOR 4.0 (P1) — insignia del estado humano + frase-resumen.
 *
 * Presenta el resultado de `buildAutoHumanState` en el primer nivel: un punto de color,
 * la etiqueta (`FUNCIONANDO` … `DETENIDO`) y la frase que explica qué está pasando.
 * No calcula nada: sólo pinta el view-model.
 *
 * @see docs/engineering/spec-auto-ui-refactor-3-0-2026-10-06.md §1.8
 */

import { AUTO_USER_TEXT } from "@/features/auto/auto-typography";
import type {
  AutoHumanTone,
  AutoHumanStateV1,
} from "@/features/auto/auto-human-state";
import { cn } from "@/lib/utils";

const TONE_DOT_CLASS: Record<AutoHumanTone, string> = {
  ok: "bg-emerald-500",
  info: "bg-sky-500",
  wait: "bg-amber-500",
  attention: "bg-orange-500",
  stop: "bg-rose-500",
};

const TONE_CONTAINER_CLASS: Record<AutoHumanTone, string> = {
  ok: "border-emerald-500/40 bg-emerald-500/10",
  info: "border-sky-500/40 bg-sky-500/10",
  wait: "border-amber-500/50 bg-amber-500/10",
  attention: "border-orange-500/50 bg-orange-500/10",
  stop: "border-rose-500/50 bg-rose-500/10",
};

export function AutoHumanStateBadge({
  state,
  testId = "auto-human-state",
}: {
  state: AutoHumanStateV1;
  testId?: string;
}) {
  return (
    <section
      aria-label="Estado de AUTO"
      data-testid={testId}
      data-tone={state.tone}
      data-state-id={state.id ?? "unknown"}
      className={cn(
        "flex flex-wrap items-start gap-x-3 gap-y-1 rounded-lg border px-4 py-3",
        TONE_CONTAINER_CLASS[state.tone],
      )}
    >
      <span className="inline-flex items-center gap-1.5">
        <span
          aria-hidden="true"
          className={cn(
            "inline-block size-2.5 rounded-full",
            TONE_DOT_CLASS[state.tone],
          )}
        />
        <span
          className="text-base font-semibold tracking-tight"
          data-testid={`${testId}-label`}
        >
          {state.label}
        </span>
      </span>
      <p
        className={cn("basis-full", AUTO_USER_TEXT, "text-muted-foreground")}
        data-testid={`${testId}-sentence`}
      >
        {state.sentence}
      </p>
    </section>
  );
}
