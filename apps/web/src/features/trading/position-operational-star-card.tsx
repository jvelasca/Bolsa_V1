/**
 * V1.60 — Tarjeta estrella DECISIÓN: PositionOperationalView canónico.
 * V1.61 — Position Decision Surface (3 niveles).
 * V1.63 — Delega presentación en DecisionSurfaceCompact.
 */

import type { PositionDto } from "@bolsa/shared";
import { DecisionSurfaceCompact } from "@/features/trading/decision-surface-compact";

type PositionOperationalStarCardProps = {
  position: PositionDto;
  symbol: string;
  portfolioReconStatus?: string | null;
  onOpenWhy?: () => void;
  className?: string;
};

export function PositionOperationalStarCard(
  props: PositionOperationalStarCardProps,
) {
  return (
    <DecisionSurfaceCompact
      variant="position"
      density="full"
      testId="position-operational-star-card"
      {...props}
    />
  );
}
