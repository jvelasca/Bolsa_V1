/**
 * Badge nav Asesor: nº de Alarmas (dictamen Estudio) del día.
 */

import { useMemo } from "react";
import { mapOpinionToChannel } from "@bolsa/shared";
import { useInstrumentDailyOpinions } from "@/features/trading/use-instrument-daily-opinions";
import { useEstudioMembershipStore } from "@/stores/estudio-membership-store";

export function useAsesorAlarmaBadge(): number {
  // Selector estable: no devolver .map() desde Zustand (rompe Object.is → loop).
  const entries = useEstudioMembershipStore((s) => s.members);
  const studyIds = useMemo(() => entries.map((e) => e.instrumentId), [entries]);

  const opinionsQuery = useInstrumentDailyOpinions(studyIds, [], {
    enabled: studyIds.length > 0,
  });

  return useMemo(() => {
    let n = 0;
    for (const op of opinionsQuery.data ?? []) {
      if (mapOpinionToChannel(op) === "alarma") n += 1;
    }
    return n;
  }, [opinionsQuery.data]);
}
