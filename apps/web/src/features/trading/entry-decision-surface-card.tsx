/**
 * V1.62 — Entry Decision Surface (simétrica a Position V1.61).
 * V1.63 — Delega presentación en DecisionSurfaceCompact.
 */

import type {
  EntryOperatingTruthV1,
  SubmitIntentListItemV1,
} from "@bolsa/shared";
import { DecisionSurfaceCompact } from "@/features/trading/decision-surface-compact";

type EntryDecisionSurfaceCardProps = {
  truth: EntryOperatingTruthV1;
  symbol: string;
  orderPendingFill?: boolean;
  submitIntent?: SubmitIntentListItemV1 | null;
  onOpenWhy?: () => void;
  className?: string;
};

export function EntryDecisionSurfaceCard(props: EntryDecisionSurfaceCardProps) {
  return (
    <DecisionSurfaceCompact
      variant="entry"
      density="full"
      testId="entry-decision-surface"
      {...props}
    />
  );
}
