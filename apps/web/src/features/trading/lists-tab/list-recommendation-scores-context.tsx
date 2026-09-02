/**
 * Scores de recomendación (IO/TA/FA + dictamen) para columnas opcionales de lista.
 * Solo fetch cuando alguna columna de recomendación está visible.
 */

import { createContext, useContext, useMemo, type ReactNode } from "react";
import {
  INSTRUMENT_DAILY_OPINION_STANCE_LABELS,
  RECOMMENDATION_OPTIONAL_LIST_COLUMNS,
  type InstrumentDailyOpinionStance,
  type ListColumnId,
} from "@bolsa/shared";

import { useInstrumentsHubScores } from "@/features/instruments/use-instruments-hub-scores";
import {
  opinionByInstrumentId,
  useInstrumentDailyOpinions,
} from "@/features/trading/use-instrument-daily-opinions";
import { resolveIndiceOperativo } from "@/features/trading/operativa-index";
import { useOptionalListColumnLayoutContext } from "@/features/trading/lists-tab/list-column-layout-context";

export type ListRecommendationRow = {
  io: number | null;
  ta: number | null;
  fa: number | null;
  dictamenStars: number | null;
  stance: InstrumentDailyOpinionStance | null;
  stanceLabel: string | null;
};

type Ctx = {
  byInstrument: Map<string, ListRecommendationRow>;
  loading: boolean;
};

const ListRecommendationScoresContext = createContext<Ctx>({
  byInstrument: new Map(),
  loading: false,
});

function needsScoreColumns(visibleIds: ReadonlySet<ListColumnId>): boolean {
  return (
    visibleIds.has("ioScore") ||
    visibleIds.has("taScore") ||
    visibleIds.has("faScore")
  );
}

function needsOpinionColumns(visibleIds: ReadonlySet<ListColumnId>): boolean {
  return visibleIds.has("dictamenStars") || visibleIds.has("recStance");
}

export function isRecommendationListColumn(columnId: ListColumnId): boolean {
  return (RECOMMENDATION_OPTIONAL_LIST_COLUMNS as readonly string[]).includes(
    columnId,
  );
}

export function ListRecommendationScoresProvider({
  instrumentIds,
  children,
}: {
  instrumentIds: ReadonlyArray<string>;
  children: ReactNode;
}) {
  const layoutContext = useOptionalListColumnLayoutContext();
  const visibleColumns = layoutContext?.visibleColumns ?? [];
  const visibleIds = useMemo(
    () => new Set(visibleColumns.map((c) => c.id)),
    [visibleColumns],
  );
  const wantScores = needsScoreColumns(visibleIds);
  const wantOpinions = needsOpinionColumns(visibleIds);
  const ids = useMemo(
    () =>
      wantScores || wantOpinions
        ? [...new Set(instrumentIds.filter(Boolean))]
        : [],
    [instrumentIds, wantScores, wantOpinions],
  );

  const { faByInstrument, taByInstrument, scoresLoading } =
    useInstrumentsHubScores(wantScores ? ids : []);
  const opinionsQuery = useInstrumentDailyOpinions(
    wantOpinions ? ids : [],
    [],
    {
      enabled: wantOpinions && ids.length > 0,
    },
  );
  const opinionsById = useMemo(
    () => opinionByInstrumentId(opinionsQuery.data),
    [opinionsQuery.data],
  );

  const byInstrument = useMemo(() => {
    const map = new Map<string, ListRecommendationRow>();
    for (const id of ids) {
      const fa = faByInstrument.get(id);
      const ta = taByInstrument.get(id);
      const opinion = opinionsById.get(id);
      const io = resolveIndiceOperativo({
        indiceOperativo: ta?.indiceOperativo,
        compositeDisplay100: ta?.compositeDisplay100,
        distress: fa?.distress,
      });
      const stance = opinion?.stance ?? null;
      map.set(id, {
        io,
        ta: ta?.technicalDisplay100 ?? ta?.compositeDisplay100 ?? null,
        fa: fa?.scoreDisplay100 ?? null,
        dictamenStars: opinion?.dictamenStars ?? null,
        stance,
        stanceLabel: stance
          ? INSTRUMENT_DAILY_OPINION_STANCE_LABELS[stance]
          : null,
      });
    }
    return map;
  }, [ids, faByInstrument, taByInstrument, opinionsById]);

  const value = useMemo(
    () => ({
      byInstrument,
      loading:
        (wantScores && scoresLoading) ||
        (wantOpinions && opinionsQuery.isLoading && ids.length > 0),
    }),
    [
      byInstrument,
      wantScores,
      scoresLoading,
      wantOpinions,
      opinionsQuery.isLoading,
      ids.length,
    ],
  );

  return (
    <ListRecommendationScoresContext.Provider value={value}>
      {children}
    </ListRecommendationScoresContext.Provider>
  );
}

export function useListRecommendationRow(
  instrumentId: string,
): ListRecommendationRow | undefined {
  return useContext(ListRecommendationScoresContext).byInstrument.get(
    instrumentId,
  );
}

export function useListRecommendationScoresMap(): ReadonlyMap<
  string,
  ListRecommendationRow
> {
  return useContext(ListRecommendationScoresContext).byInstrument;
}

export function useListRecommendationScoresLoading(): boolean {
  return useContext(ListRecommendationScoresContext).loading;
}
