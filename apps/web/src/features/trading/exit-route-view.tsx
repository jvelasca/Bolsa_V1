/**
 * V1.40 — Ruta visual Entrada → Stop / T1 / T2 (Exit Management UX).
 * Proyección read-only; Confirm = firma.
 */

import type {
  DecisionJournalStudyViewV1,
  ExitRouteViewV1,
  OperationalTruthV1,
  PositionDto,
} from "@bolsa/shared";
import { buildExitRouteView } from "@bolsa/shared";
import { formatPrice } from "@/features/charts/chart-utils";
import { cn } from "@/lib/utils";

function nodeDotClass(kind: ExitRouteViewV1["nodes"][number]["kind"]): string {
  switch (kind) {
    case "stop":
      return "border-rose-500 bg-rose-500/30";
    case "entry":
      return "border-sky-500 bg-sky-500/30";
    case "price":
      return "border-amber-500 bg-amber-500/30";
    case "target1":
    case "target2":
      return "border-emerald-500 bg-emerald-500/30";
    default:
      return "border-border bg-muted/40";
  }
}

export function ExitRouteView({
  route: routeProp,
  truth,
  position,
  study,
  originStudy,
  className,
  testId,
}: {
  route?: ExitRouteViewV1 | null;
  truth?: OperationalTruthV1 | null;
  position?: PositionDto;
  study?: DecisionJournalStudyViewV1 | null;
  originStudy?: DecisionJournalStudyViewV1 | null;
  className?: string;
  testId?: string;
}) {
  const route =
    routeProp ??
    (truth && position
      ? buildExitRouteView({ truth, position, study, originStudy })
      : null);
  if (!route?.hasRoute) return null;

  const id =
    testId ?? `exit-route-${route.symbol.replace(/[^a-zA-Z0-9_-]/g, "_")}`;

  return (
    <div
      className={cn("relative ml-2 border-l border-border/60 pl-3", className)}
      data-testid={id}
      data-trailing={route.trailingActive ? "true" : "false"}
    >
      <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
        Ruta de salida
      </p>
      {route.nodes.map((node) => (
        <div
          key={`${node.kind}-${node.value}`}
          className="relative py-1 text-xs"
          data-testid={`${id}-node-${node.kind}`}
          data-role={node.roleLabel}
        >
          <span
            className={cn(
              "absolute -left-[13px] top-2 h-2 w-2 rounded-full border",
              nodeDotClass(node.kind),
            )}
          />
          <span className="font-medium">{node.label}</span>
          <span className="text-muted-foreground"> · {node.roleLabel}</span>
          {" · "}
          <span className="tabular-nums">{formatPrice(node.value)}</span>
          {node.distanceR != null ? (
            <span className="ml-1 text-muted-foreground tabular-nums">
              {node.distanceR >= 0 ? "+" : ""}
              {node.distanceR.toFixed(1)}R
            </span>
          ) : null}
          {node.progressHint ? (
            <span className="ml-1 text-[10px] text-muted-foreground">
              {node.progressHint}
            </span>
          ) : node.kind === "entry" && node.reached ? (
            <span className="ml-1 text-emerald-600">✓</span>
          ) : null}
        </div>
      ))}
      <p className="mt-1 text-[9px] text-muted-foreground">
        Stop operativo ≠ orden broker · T2 trailing = propuesta thin.
      </p>
    </div>
  );
}
