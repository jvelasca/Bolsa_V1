/**
 * V1.60 — Tarjeta estrella DECISIÓN: PositionOperationalView canónico.
 * V1.61 — Position Decision Surface (3 niveles).
 * V1.63 — Delega presentación en DecisionSurfaceCompact.
 * V2.0 — journey HUD opcional (lifecycle + risk).
 */

import type {
  PositionDto,
  PositionJourneyReadoutV1,
  PositionOperationalViewV1,
} from "@bolsa/shared";
import { DecisionSurfaceCompact } from "@/features/trading/decision-surface-compact";

type PositionOperationalStarCardProps = {
  position: PositionDto;
  symbol: string;
  portfolioReconStatus?: string | null;
  view?: PositionOperationalViewV1;
  viewSource?: "canonical" | "blob";
  journey?: PositionJourneyReadoutV1 | null;
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
