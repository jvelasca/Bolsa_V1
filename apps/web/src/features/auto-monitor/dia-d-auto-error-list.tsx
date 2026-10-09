/**
 * DÍA-D AUTO · FEEDBACK — catálogo de errores (SOFTWARE / OPERATIONAL / DATA).
 *
 * Agrupa por familia y código (con conteo) y lista las incidencias concretas (día · valor ·
 * familia · código). Las familias salen del vocabulario del backend: un código no catalogado
 * no inventa una familia nueva.
 */

import type { components } from "@/api/schema";
import { absentDataLabel } from "@/components/absent-data";
import { cn } from "@/lib/utils";

type DiaDFeedbackErrorDto = components["schemas"]["DiaDFeedbackErrorDto"];
type DiaDFeedbackErrorCountsDto =
  components["schemas"]["DiaDFeedbackErrorCountsDto"];

const KIND_STYLE: Record<string, string> = {
  SOFTWARE: "bg-destructive/15 text-destructive",
  OPERATIONAL: "bg-amber-500/15 text-amber-600 dark:text-amber-400",
  DATA: "bg-sky-500/15 text-sky-600 dark:text-sky-400",
};

const KIND_LABEL: Record<string, string> = {
  SOFTWARE: "Software",
  OPERATIONAL: "Operativa",
  DATA: "Datos",
};

export function groupErrorsByKind(
  errors: DiaDFeedbackErrorDto[],
): Array<{ kind: string; code: string; count: number }> {
  const counts = new Map<
    string,
    { kind: string; code: string; count: number }
  >();
  for (const error of errors) {
    const key = `${error.kind}::${error.code}`;
    const current = counts.get(key);
    if (current) {
      current.count += 1;
    } else {
      counts.set(key, { kind: error.kind, code: error.code, count: 1 });
    }
  }
  return [...counts.values()].sort((a, b) => {
    if (a.kind !== b.kind) return a.kind < b.kind ? -1 : 1;
    if (b.count !== a.count) return b.count - a.count;
    return a.code < b.code ? -1 : 1;
  });
}

function KindBadge({ kind }: { kind: string }) {
  return (
    <span
      data-testid="dia-d-auto-error-kind"
      data-kind={kind}
      className={cn(
        "rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
        KIND_STYLE[kind] ?? "bg-muted text-muted-foreground",
      )}
    >
      {KIND_LABEL[kind] ?? kind}
    </span>
  );
}

export function DiaDAutoErrorList({
  errors,
  counts,
  limit = 100,
  className,
}: {
  errors: DiaDFeedbackErrorDto[];
  counts?: DiaDFeedbackErrorCountsDto;
  limit?: number;
  className?: string;
}) {
  if (errors.length === 0) {
    return (
      <p
        className="text-[11px] text-muted-foreground"
        data-testid="dia-d-auto-error-list-empty"
      >
        Sin incidencias registradas en esta ventana.
      </p>
    );
  }
  const groups = groupErrorsByKind(errors);
  const shown = errors.slice(0, limit);

  return (
    <div
      className={cn("space-y-2", className)}
      data-testid="dia-d-auto-error-list"
    >
      <div className="flex flex-wrap gap-1.5">
        {(["SOFTWARE", "OPERATIONAL", "DATA"] as const).map((kind) => (
          <span key={kind} className="inline-flex items-center gap-1.5">
            <KindBadge kind={kind} />
            <span className="text-[10px] tabular-nums text-muted-foreground">
              {counts
                ? counts[kind]
                : errors.filter((error) => error.kind === kind).length}
            </span>
          </span>
        ))}
      </div>

      <div
        className="flex flex-wrap gap-1.5"
        data-testid="dia-d-auto-error-groups"
      >
        {groups.map((group) => (
          <span
            key={`${group.kind}-${group.code}`}
            data-testid="dia-d-auto-error-group"
            className="rounded border border-border/60 bg-muted/30 px-1.5 py-0.5 text-[10px] tabular-nums text-muted-foreground"
          >
            <span className="font-mono text-foreground/80">{group.code}</span> ·{" "}
            {group.count}
          </span>
        ))}
      </div>

      <div className="max-h-56 overflow-auto rounded-md border border-border/50">
        <table className="w-full">
          <thead className="sticky top-0 bg-card">
            <tr className="text-left text-[10px] uppercase tracking-wide text-muted-foreground">
              <th className="px-2 py-1 font-semibold">Día</th>
              <th className="px-2 py-1 font-semibold">Valor</th>
              <th className="px-2 py-1 font-semibold">Familia</th>
              <th className="px-2 py-1 font-semibold">Código</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((error, index) => (
              <tr
                key={`${error.day}-${error.symbol}-${error.kind}-${error.code}-${index}`}
                data-testid="dia-d-auto-error-row"
                className="border-t border-border/40"
              >
                <td className="px-2 py-1 font-mono text-[10px] tabular-nums">
                  {error.day || absentDataLabel()}
                </td>
                <td className="px-2 py-1 font-mono text-[10px]">
                  {error.symbol || absentDataLabel()}
                </td>
                <td className="px-2 py-1">
                  <KindBadge kind={error.kind} />
                </td>
                <td className="px-2 py-1 font-mono text-[10px] text-foreground/80">
                  {error.code}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {errors.length > limit ? (
        <p className="text-[10px] text-muted-foreground">
          Se muestran {limit} de {errors.length} incidencias.
        </p>
      ) : null}
    </div>
  );
}
