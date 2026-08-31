/**
 * Bloques reutilizables Ayuda — mesa operativa (básico → experto).
 */

import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import {
  OPERATING_DESK_EXPERT,
  OPERATING_DESK_NAV,
  OPERATING_DESK_READ_RULES,
  OPERATING_DESK_SUMMARY,
  OPERATING_DESK_SYNC,
  OPERATING_DESK_YOU_ARE_HERE,
} from "@/features/help/operating-desk-help";

function RouteLink({ to, children }: { to: string; children: ReactNode }) {
  return (
    <Link to={to} className="font-medium text-primary hover:underline">
      {children}
    </Link>
  );
}

/** Resumen + cómo probar + lectura diaria (usuario básico). */
export function OperatingDeskBasicBlocks({
  showNav = false,
}: {
  showNav?: boolean;
}) {
  return (
    <div className="space-y-4 text-sm">
      <section
        className="rounded-md border border-border bg-muted/25 px-3 py-2.5"
        data-testid="operating-desk-summary"
      >
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h3 className="text-sm font-semibold text-foreground">
            {OPERATING_DESK_SUMMARY.title}
          </h3>
          <p className="text-[11px] text-muted-foreground">
            Fase {OPERATING_DESK_SYNC.phase} · tip{" "}
            {OPERATING_DESK_SYNC.tipLabel} · sync {OPERATING_DESK_SYNC.asOf}
          </p>
        </div>
        <p className="mt-1.5 text-muted-foreground">
          {OPERATING_DESK_SUMMARY.body}
        </p>
        <ul className="mt-2 list-disc space-y-1 pl-5 text-muted-foreground">
          {OPERATING_DESK_SUMMARY.bullets.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </section>

      <section>
        <h3 className="mb-1.5 font-semibold text-foreground">
          {OPERATING_DESK_YOU_ARE_HERE.title}
        </h3>
        <p className="text-muted-foreground">
          {OPERATING_DESK_YOU_ARE_HERE.body}
        </p>
        <ol className="mt-2 list-decimal space-y-1.5 pl-5 text-muted-foreground">
          {OPERATING_DESK_YOU_ARE_HERE.steps.map((step) => (
            <li key={step}>{step}</li>
          ))}
        </ol>
        <p className="mt-2 text-xs text-muted-foreground">
          {OPERATING_DESK_YOU_ARE_HERE.pause}
        </p>
      </section>

      <section>
        <h3 className="mb-1.5 font-semibold text-foreground">
          {OPERATING_DESK_READ_RULES.title}
        </h3>
        <ul className="space-y-1.5 text-muted-foreground">
          {OPERATING_DESK_READ_RULES.items.map((row) => (
            <li key={row.plain}>
              <strong className="text-foreground">{row.plain}</strong> —{" "}
              {row.meaning}
            </li>
          ))}
        </ul>
      </section>

      {showNav ? (
        <section>
          <h3 className="mb-1.5 font-semibold text-foreground">
            {OPERATING_DESK_NAV.title}
          </h3>
          <ul className="space-y-1.5 text-muted-foreground">
            {OPERATING_DESK_NAV.items.map((item) => (
              <li key={item.label}>
                <RouteLink to={item.route}>{item.label}</RouteLink> —{" "}
                {item.plain}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}

/** Detalle colapsable para experto / tester. */
export function OperatingDeskExpertDetails({
  defaultOpen = false,
}: {
  defaultOpen?: boolean;
}) {
  return (
    <details
      className="rounded-md border border-border/80 bg-muted/15 px-3 py-2"
      open={defaultOpen || undefined}
      data-testid="operating-desk-expert"
    >
      <summary className="cursor-pointer text-sm font-semibold text-foreground">
        {OPERATING_DESK_EXPERT.title}
      </summary>
      <div className="mt-2 space-y-2 text-sm text-muted-foreground">
        <p>{OPERATING_DESK_EXPERT.intro}</p>
        <ul className="list-disc space-y-1.5 pl-5">
          {OPERATING_DESK_EXPERT.bullets.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
        <h4 className="pt-1 text-xs font-semibold uppercase tracking-wide text-foreground">
          {OPERATING_DESK_EXPERT.checkListTitle}
        </h4>
        <ul className="list-disc space-y-1 pl-5 text-xs">
          {OPERATING_DESK_EXPERT.checkList.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </div>
    </details>
  );
}
