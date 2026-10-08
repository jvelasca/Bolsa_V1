/**
 * UI Contract 5.0 (`UI5-10`/`UI5-17`) — insignia de modo de operación.
 *
 * Chip **no interactivo** (Información, no Acción) que declara el modo (`AUTO`/`SEMI`/`MANUAL`) y
 * el canal de dinero (`SIMULADO`/`LIVE`). Sin evidencia de modo, se rotula «Sin dato todavía»
 * (`UNKNOWN ≠ 0`); nunca se deduce del ticker.
 *
 * @see docs/engineering/spec-ui-contract-5-0-2026-10-08.md §UI5-10 §UI5-17
 */

import {
  operationModeLabel,
  type OperationModeBadgeV1,
} from "@/features/operations/operation-mode";
import { cn } from "@/lib/utils";

export function ModeBadge({
  badge,
  className,
  testId,
}: {
  badge: OperationModeBadgeV1;
  className?: string;
  testId?: string;
}) {
  const known = badge.mode != null;
  return (
    <span
      data-testid={testId}
      data-mode={badge.mode ?? "unknown"}
      data-channel={badge.channel}
      className={cn(
        "inline-flex items-center rounded border px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
        known
          ? "border-border text-muted-foreground"
          : "border-dashed border-amber-500/50 text-amber-600 dark:text-amber-400",
        className,
      )}
    >
      {operationModeLabel(badge)}
    </span>
  );
}
