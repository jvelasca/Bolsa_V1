/**
 * V2.0.2 — Position journey readout for Mercado (lifecycle snapshot + POV).
 */

import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import type {
  PaperAutoPostureV1,
  PositionDto,
  PositionJourneyReadoutV1,
  PositionOperationalViewV1,
} from "@bolsa/shared";
import { buildPositionJourneyReadout } from "@bolsa/shared";
import { api } from "@/lib/api";

export function usePositionJourneyReadout(input: {
  position: PositionDto | null | undefined;
  view: PositionOperationalViewV1 | null | undefined;
  autoPosture?: PaperAutoPostureV1 | null;
  killOn?: boolean | null;
  enabled?: boolean;
}): PositionJourneyReadoutV1 | null {
  const positionId = input.position?.id ?? null;
  const enabled =
    (input.enabled ?? true) && Boolean(positionId) && Boolean(input.view);

  const snapshotQuery = useQuery({
    queryKey: ["lifecycle-snapshot", positionId],
    queryFn: () => api.getLifecycleSnapshot(positionId!),
    enabled,
    staleTime: 15_000,
    refetchInterval: 60_000,
    retry: false,
  });

  return useMemo(() => {
    if (!input.view || !input.position) return null;
    const op = input.position.operational;
    const opExt = (op ?? null) as Record<string, unknown> | null;
    const snap = snapshotQuery.data?.data;
    return buildPositionJourneyReadout({
      view: input.view,
      initialRisk:
        typeof opExt?.initialRisk === "number" ? opExt.initialRisk : null,
      initialStop: op?.initialStop ?? null,
      realizedR: typeof opExt?.realizedR === "number" ? opExt.realizedR : null,
      direction: op?.direction === "short" ? "short" : "long",
      templateId: input.view.templateId ?? null,
      lifecycle: snap
        ? {
            positionId: snap.positionId,
            stage: snap.stage,
            lineagePath: snap.lineagePath,
            events: snap.events,
          }
        : null,
      autoPosture: input.autoPosture ?? null,
      killOn: input.killOn ?? null,
    });
  }, [
    input.view,
    input.position,
    input.autoPosture,
    input.killOn,
    snapshotQuery.data,
  ]);
}
