/**
 * Badge nav Asesor: nº de Alarmas (dictamen Estudio) del día.
 */

import { useMemo } from 'react';
import { mapOpinionToChannel } from '@bolsa/shared';
import { useInstrumentDailyOpinions } from '@/features/trading/use-instrument-daily-opinions';
import { useVisualizationStore } from '@/stores/visualization-store';

export function useAsesorAlarmaBadge(): number {
  const studyIds = useVisualizationStore((s) =>
    s.entries.map((e) => e.instrumentId),
  );

  const opinionsQuery = useInstrumentDailyOpinions(studyIds, [], {
    enabled: studyIds.length > 0,
  });

  return useMemo(() => {
    let n = 0;
    for (const op of opinionsQuery.data ?? []) {
      if (mapOpinionToChannel(op) === 'alarma') n += 1;
    }
    return n;
  }, [opinionsQuery.data]);
}
