import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { useScreenerActivityStore } from '@/stores/screener-activity-store';

const ACTIVE_JOB_STATUSES = new Set(['pending', 'processing']);

/** Jobs en cola + scan sync local → badge en nav Rastreadores. */
export function useScreenerNavBadge(): number {
  const syncScanActive = useScreenerActivityStore((state) => state.syncScanActive);

  const jobsQuery = useQuery({
    queryKey: ['scan-jobs', 'nav-badge'],
    queryFn: async () => {
      const response = await api.getScanJobs();
      return response.data.filter((job) => ACTIVE_JOB_STATUSES.has(job.status)).length;
    },
    refetchInterval: (query) => {
      const count = query.state.data ?? 0;
      return count > 0 || syncScanActive ? 2000 : 12000;
    },
  });

  const queued = jobsQuery.data ?? 0;
  if (queued > 0) return queued;
  return syncScanActive ? 1 : 0;
}
