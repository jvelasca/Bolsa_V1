import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export function MesaLevelSection({
  level,
  title,
  description,
  children,
  testId,
}: {
  level: 1 | 2 | 3;
  title: string;
  description: string;
  children: ReactNode;
  testId: string;
}) {
  return (
    <section
      className="space-y-3"
      data-testid={testId}
      aria-labelledby={`${testId}-title`}
    >
      <header>
        <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
          Nivel {level}
        </p>
        <h2 id={`${testId}-title`} className="text-sm font-semibold">
          {title}
        </h2>
        <p className={cn("mt-0.5 text-xs text-muted-foreground")}>
          {description}
        </p>
      </header>
      <div className="space-y-3">{children}</div>
    </section>
  );
}
