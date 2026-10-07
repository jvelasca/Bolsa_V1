/**
 * AUTO UI REFACTOR 4.0 (P2) — botón «¿Por qué?» reutilizable.
 *
 * Presenta la explicación de primer nivel (`AutoWhyV1`) tras un botón. Accesible: el botón
 * declara `aria-expanded` y controla una región con `aria-label`. No calcula nada.
 */

import { useId, useState } from "react";
import { AUTO_USER_TEXT } from "@/features/auto/auto-typography";
import type { AutoWhyReasonStatus, AutoWhyV1 } from "@/features/auto/auto-why";
import { cn } from "@/lib/utils";

const STATUS_MARK: Record<AutoWhyReasonStatus, string> = {
  ok: "✓",
  no: "✗",
  unknown: "–",
};

const STATUS_CLASS: Record<AutoWhyReasonStatus, string> = {
  ok: "text-emerald-600 dark:text-emerald-400",
  no: "text-rose-600 dark:text-rose-400",
  unknown: "text-amber-600 dark:text-amber-400",
};

const STATUS_LABEL: Record<AutoWhyReasonStatus, string> = {
  ok: "cumple",
  no: "no cumple",
  unknown: "sin dato",
};

export function AutoWhyButton({
  why,
  testId = "auto-why",
  label = "¿Por qué?",
}: {
  why: AutoWhyV1;
  testId?: string;
  label?: string;
}) {
  const [open, setOpen] = useState(false);
  const regionId = useId();

  return (
    <div>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-controls={regionId}
        data-testid={`${testId}-toggle`}
        className={cn(
          "inline-flex h-8 items-center rounded-md border border-border px-3 font-medium hover:bg-accent hover:text-foreground",
          AUTO_USER_TEXT,
        )}
      >
        {open ? "Ocultar porqué" : label}
      </button>

      {open ? (
        <div
          id={regionId}
          role="region"
          aria-label="Explicación de la decisión de AUTO"
          data-testid={`${testId}-panel`}
          className="mt-2 space-y-2 rounded-lg border border-border bg-card px-4 py-3"
        >
          <p className={cn("font-semibold", AUTO_USER_TEXT)}>{why.title}</p>
          <p className={cn(AUTO_USER_TEXT, "text-muted-foreground")}>
            {why.summary}
          </p>
          <ul className="space-y-1">
            {why.reasons.map((r) => (
              <li
                key={r.label}
                className={cn("flex flex-wrap gap-x-2", AUTO_USER_TEXT)}
              >
                <span
                  className={cn("font-semibold", STATUS_CLASS[r.status])}
                  aria-hidden="true"
                >
                  {STATUS_MARK[r.status]}
                </span>
                <span className="sr-only">{STATUS_LABEL[r.status]}: </span>
                <span>{r.label}</span>
                {r.detail ? (
                  <span className="text-muted-foreground">· {r.detail}</span>
                ) : null}
              </li>
            ))}
          </ul>
          <p className={cn("font-medium", AUTO_USER_TEXT)}>{why.conclusion}</p>
        </div>
      ) : null}
    </div>
  );
}
