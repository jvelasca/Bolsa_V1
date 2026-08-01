/**
 * Carga trackers + detalle + políticas para hub Instrumentos I3.
 */

import { useMemo } from 'react';
import { useQueries, useQuery } from '@tanstack/react-query';
import type { ExecutionMode, TrackerDefinitionDetailDto } from '@bolsa/shared';
import { api } from '@/lib/api';
import type { HubListMembership } from '@/features/instruments/instruments-hub-enrichment';
import {
  invertTrackersByInstrument,
  type HubTrackerChip,
} from '@/features/instruments/instruments-hub-trackers';

export function useInstrumentsHubTrackers(
  membershipsByInstrument: Map<string, HubListMembership[]>,
) {
  const trackersQuery = useQuery({
    queryKey: ['trackers'],
    queryFn: () => api.getTrackers(),
    staleTime: 30_000,
  });

  const summaries = trackersQuery.data?.data ?? [];
  const trackerIds = summaries.map((t) => t.id);

  const detailQueries = useQueries({
    queries: trackerIds.map((id) => ({
      queryKey: ['tracker', id],
      queryFn: () => api.getTracker(id),
      enabled: trackerIds.length > 0,
      staleTime: 30_000,
    })),
  });

  const policiesQuery = useQuery({
    queryKey: ['execution-policies', true],
    queryFn: () => api.getExecutionPolicies(true),
    staleTime: 60_000,
  });

  const policyModeById = useMemo(() => {
    const map = new Map<string, ExecutionMode>();
    for (const p of policiesQuery.data?.data ?? []) {
      map.set(p.id, p.mode);
    }
    return map;
  }, [policiesQuery.data?.data]);

  const details = useMemo(() => {
    return detailQueries
      .map((q) => q.data?.data)
      .filter((d): d is TrackerDefinitionDetailDto => Boolean(d));
  }, [detailQueries]);

  const trackersByInstrument = useMemo(
    () => invertTrackersByInstrument(details, membershipsByInstrument, policyModeById),
    [details, membershipsByInstrument, policyModeById],
  ) as Map<string, HubTrackerChip[]>;

  const detailsReady =
    trackerIds.length === 0 || detailQueries.every((q) => q.isSuccess || q.isError);

  return {
    trackersByInstrument,
    trackersLoading:
      trackersQuery.isLoading ||
      (trackerIds.length > 0 && !detailsReady) ||
      policiesQuery.isLoading,
  };
}
