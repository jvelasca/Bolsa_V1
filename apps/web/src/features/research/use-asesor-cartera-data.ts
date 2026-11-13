/**
 * S3 · Cartera del Asesor — carga y composición de la lista.
 *
 * Reutiliza las MISMAS `queryKey` que ya usan OPERATIVA y Asesor para no duplicar
 * red: `["portfolio", accountScope]`, `["decision-studies", accountId, "mesa"]`,
 * `["instrument-daily-opinions", …]` y `["ohlcv", id, timeframe]`.
 *
 * Lo único nuevo son las cotizaciones por lote (`["asesor-cartera-quotes", ids]`) y
 * las velas que alimentan S2 (`["asesor-cartera-bars", ids, "1d"]`). No existe
 * endpoint batch de OHLCV y S0 impide tocar contrato, así que se cargan con
 * concurrencia acotada y `staleTime` de 5 min. El cargador está aislado para poder
 * sustituirlo por un endpoint batch cuando S0 lo permita, sin cambiar modelo ni UI.
 *
 * La composición es pura: este hook no decide posturas ni clasifica nada por su
 * cuenta. Todo sale de `buildAsesorCarteraRow`.
 *
 * @see docs/engineering/diseno-asesor-cartera-s3-2026-11-12.md
 */

import { useMemo } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  INSTRUMENT_QUOTES_BATCH_LIMIT,
  buildAsesorCarteraRow,
  chunkIds,
  computeMarketStructure,
  pickPositionStudies,
  studiesByDecisionIdMap,
  studiesByInstrumentMap,
  summarizeAsesorCartera,
  type AsesorCarteraRowV1,
  type AsesorCarteraSummaryV1,
  type InstrumentDailyOpinionV1,
  type InstrumentWithMetaDto,
  type MarketStructureResultV1,
  type OhlcvBarDto,
  type PositionDto,
} from "@bolsa/shared";
import { api } from "@/lib/api";
import { portfolioMeasured } from "@/lib/position-open-hint";
import { useActiveAccount } from "@/features/accounts/use-active-account";
import { useActiveAccountQueryKey } from "@/stores/active-account-store";
import { useEstudioMembershipStore } from "@/stores/estudio-membership-store";
import { useSupervisedF3QueueStore } from "@/stores/supervised-f3-queue-store";
import { usePendingOrders } from "@/features/trading/use-pending-orders";
import { useInstrumentDailyOpinions } from "@/features/trading/use-instrument-daily-opinions";
import {
  resolveInstrumentOperationalFacts,
  type InstrumentOperationalFactsV1,
} from "@/features/trading/instrument-operational-facts";

export const ASESOR_CARTERA_TIMEFRAME = "1d";
export const ASESOR_CARTERA_BARS_LIMIT = 500;
export const ASESOR_CARTERA_BARS_CONCURRENCY = 4;
export const ASESOR_CARTERA_BARS_STALE_MS = 5 * 60_000;
/** Cotizaciones: son cierres diarios de BD, no cotización viva. */
export const ASESOR_CARTERA_QUOTES_STALE_MS = 5 * 60_000;
export const ASESOR_CARTERA_READ_STALE_MS = 60_000;

const OHLCV_STALE_MS = 60_000;

// ─────────────────────────────────────────────────────────────────────────────
// Cargador de velas (puro respecto a React; testeable y sustituible)
// ─────────────────────────────────────────────────────────────────────────────

export type LoadAsesorCarteraBarsInput = {
  instrumentIds: readonly string[];
  /** Caché ya presente (p. ej. la del gráfico). Si devuelve velas, no hay fetch. */
  readCached?: (instrumentId: string) => readonly OhlcvBarDto[] | null | undefined;
  loadBars: (instrumentId: string) => Promise<readonly OhlcvBarDto[]>;
  concurrency?: number;
};

export type LoadAsesorCarteraBarsResult = {
  barsById: Map<string, OhlcvBarDto[]>;
  /** Instrumentos que fallaron. Un fallo NO tumba la lista. */
  failedIds: string[];
  /** Instrumentos servidos desde caché sin fetch. */
  cachedIds: string[];
  /** Máxima concurrencia observada (para evidencia/tests). */
  peakConcurrency: number;
};

/**
 * Carga velas con un pool de `concurrency` trabajadores. Cada instrumento es
 * independiente: un rechazo se declara y los demás continúan.
 */
export async function loadAsesorCarteraBars(
  input: LoadAsesorCarteraBarsInput,
): Promise<LoadAsesorCarteraBarsResult> {
  const ids = [...new Set(input.instrumentIds.filter(Boolean))];
  const concurrency = Math.max(
    1,
    Math.min(
      Math.floor(input.concurrency ?? ASESOR_CARTERA_BARS_CONCURRENCY),
      ids.length || 1,
    ),
  );

  const barsById = new Map<string, OhlcvBarDto[]>();
  const failedIds: string[] = [];
  const cachedIds: string[] = [];
  let cursor = 0;
  let active = 0;
  let peakConcurrency = 0;

  async function worker(): Promise<void> {
    while (cursor < ids.length) {
      const id = ids[cursor]!;
      cursor += 1;
      const cached = input.readCached?.(id);
      if (cached && cached.length > 0) {
        barsById.set(id, [...cached]);
        cachedIds.push(id);
        continue;
      }
      active += 1;
      peakConcurrency = Math.max(peakConcurrency, active);
      try {
        const bars = await input.loadBars(id);
        barsById.set(id, [...bars]);
      } catch {
        failedIds.push(id);
      } finally {
        active -= 1;
      }
    }
  }

  await Promise.all(
    Array.from({ length: Math.min(concurrency, ids.length) }, () => worker()),
  );

  return { barsById, failedIds, cachedIds, peakConcurrency };
}

// ─────────────────────────────────────────────────────────────────────────────
// Hook de datos
// ─────────────────────────────────────────────────────────────────────────────

export type AsesorCarteraUniverseEntryV1 = {
  instrumentId: string;
  symbol: string;
  name: string;
};

export type AsesorCarteraDataV1 = {
  rows: AsesorCarteraRowV1[];
  summary: AsesorCarteraSummaryV1;
  universe: AsesorCarteraUniverseEntryV1[];
  /** La clasificación (dictamen + cartera) aún está cargando. */
  loading: boolean;
  /** El contexto (precio, velas, opiniones) aún se está midiendo. */
  enriching: boolean;
  /** Cada fuente de enriquecimiento, por separado: «midiendo» ≠ «no medido». */
  quotesLoading: boolean;
  opinionsLoading: boolean;
  barsLoading: boolean;
  portfolioMeasured: boolean;
  portfolioError: boolean;
  studiesError: boolean;
  /** `decision-studies` vino recortado por `limit`: no se afirma «sin plan». */
  studiesTruncated: boolean;
  quotesError: boolean;
  barsError: boolean;
  barsFailedIds: string[];
  /** Instrumentos sin velas disponibles (fallo o lote aún cargando). */
  barsMissingIds: string[];
  empty: boolean;
};

function quotePrice(quote: InstrumentWithMetaDto | undefined): number | null {
  const meta = quote?.meta;
  const value = meta?.lastClose;
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function quoteChange(quote: InstrumentWithMetaDto | undefined): number | null {
  const value = quote?.meta?.changePct;
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function structureForBars(
  bars: readonly OhlcvBarDto[] | undefined,
): MarketStructureResultV1 | null {
  if (!bars || bars.length === 0) return null;
  return computeMarketStructure({ bars, timeframe: ASESOR_CARTERA_TIMEFRAME });
}

/**
 * Memo de estructura por IDENTIDAD del array de velas.
 *
 * `loadAsesorCarteraBars` guarda copias (`[...bars]`), así que la identidad solo cambia
 * cuando llegan velas nuevas. Un refresco de cotización o de dictamen —que no toca las
 * velas— no vuelve a calcular ATR ni pivotes de toda la lista.
 *
 * Exportado para test y para poder vaciarlo si algún día las velas pasan a mutarse.
 */
const structureCache = new WeakMap<
  readonly OhlcvBarDto[],
  MarketStructureResultV1
>();

export function memoizedStructureForBars(
  bars: readonly OhlcvBarDto[] | undefined,
): MarketStructureResultV1 | null {
  if (!bars || bars.length === 0) return null;
  const cached = structureCache.get(bars);
  if (cached) return cached;
  const computed = structureForBars(bars);
  if (computed) structureCache.set(bars, computed);
  return computed;
}

export function useAsesorCarteraData(): AsesorCarteraDataV1 {
  const queryClient = useQueryClient();
  const { effectiveAccountId } = useActiveAccount();
  const accountScope = useActiveAccountQueryKey();
  const members = useEstudioMembershipStore((s) => s.members);
  const queueItems = useSupervisedF3QueueStore((s) => s.items);
  const { pendingOrders } = usePendingOrders();

  const portfolioQuery = useQuery({
    queryKey: ["portfolio", accountScope],
    queryFn: () => api.getPortfolio(),
    staleTime: ASESOR_CARTERA_READ_STALE_MS,
  });

  const studiesQuery = useQuery({
    queryKey: ["decision-studies", effectiveAccountId, "mesa"],
    queryFn: () => api.getDecisionStudies(effectiveAccountId!, { limit: 200 }),
    enabled: Boolean(effectiveAccountId),
    staleTime: ASESOR_CARTERA_READ_STALE_MS,
  });

  const isPortfolioMeasured = portfolioMeasured(portfolioQuery);
  const positions = useMemo(
    () => portfolioQuery.data?.data.positions ?? [],
    [portfolioQuery.data],
  );
  const openPositions = useMemo(
    () =>
      positions.filter(
        (position) => Math.abs(Number(position.quantity ?? 0)) > 0,
      ),
    [positions],
  );

  // Universo = membresía Estudio + posiciones abiertas de la cuenta activa.
  const universe = useMemo<AsesorCarteraUniverseEntryV1[]>(() => {
    const byId = new Map<string, AsesorCarteraUniverseEntryV1>();
    for (const member of members) {
      byId.set(member.instrumentId, {
        instrumentId: member.instrumentId,
        symbol: member.symbol,
        name: member.name,
      });
    }
    if (isPortfolioMeasured) {
      for (const position of openPositions) {
        if (byId.has(position.instrumentId)) continue;
        byId.set(position.instrumentId, {
          instrumentId: position.instrumentId,
          symbol: position.symbol,
          name: position.name,
        });
      }
    }
    return [...byId.values()];
  }, [members, openPositions, isPortfolioMeasured]);

  const universeIds = useMemo(
    () => universe.map((entry) => entry.instrumentId),
    [universe],
  );
  const idsKey = useMemo(() => [...universeIds].sort().join(","), [universeIds]);

  const quotesQuery = useQuery({
    queryKey: ["asesor-cartera-quotes", idsKey],
    enabled: universeIds.length > 0,
    staleTime: ASESOR_CARTERA_QUOTES_STALE_MS,
    refetchOnWindowFocus: false,
    queryFn: async (): Promise<InstrumentWithMetaDto[]> => {
      const chunks = chunkIds(universeIds, INSTRUMENT_QUOTES_BATCH_LIMIT);
      const parts = await Promise.all(
        chunks.map((ids) => api.getInstrumentQuotes(ids)),
      );
      return parts.flatMap((part) => part.data ?? []);
    },
  });

  const quotesById = useMemo(() => {
    const map = new Map<string, InstrumentWithMetaDto>();
    for (const quote of quotesQuery.data ?? []) map.set(quote.id, quote);
    return map;
  }, [quotesQuery.data]);

  const opinionsQuery = useInstrumentDailyOpinions(universeIds, {
    enabled: universeIds.length > 0,
  });
  const opinionsById = useMemo(() => {
    const map = new Map<string, InstrumentDailyOpinionV1>();
    for (const opinion of opinionsQuery.data ?? []) {
      map.set(opinion.instrumentId, opinion);
    }
    return map;
  }, [opinionsQuery.data]);

  const barsQuery = useQuery({
    queryKey: ["asesor-cartera-bars", idsKey, ASESOR_CARTERA_TIMEFRAME],
    enabled: universeIds.length > 0,
    staleTime: ASESOR_CARTERA_BARS_STALE_MS,
    refetchOnWindowFocus: false,
    queryFn: () =>
      loadAsesorCarteraBars({
        instrumentIds: universeIds,
        readCached: (instrumentId) =>
          queryClient.getQueryData<{ data: OhlcvBarDto[] }>([
            "ohlcv",
            instrumentId,
            ASESOR_CARTERA_TIMEFRAME,
          ])?.data ?? null,
        loadBars: async (instrumentId) => {
          const response = await queryClient.fetchQuery({
            queryKey: [
              "ohlcv",
              instrumentId,
              ASESOR_CARTERA_TIMEFRAME,
            ],
            queryFn: () =>
              api.getOhlcv(
                instrumentId,
                ASESOR_CARTERA_BARS_LIMIT,
                ASESOR_CARTERA_TIMEFRAME,
              ),
            staleTime: OHLCV_STALE_MS,
          });
          return response.data ?? [];
        },
      }),
  });

  const studies = useMemo(
    () => studiesQuery.data?.data?.studies ?? [],
    [studiesQuery.data],
  );
  const studiesTotal = studiesQuery.data?.data?.total;
  const studiesTruncated =
    typeof studiesTotal === "number" && studiesTotal > studies.length;

  const studiesByInstrument = useMemo(
    () => studiesByInstrumentMap(studies),
    [studies],
  );
  const studiesByDecision = useMemo(
    () => studiesByDecisionIdMap(studies),
    [studies],
  );

  const operationsByInstrument = useMemo(() => {
    const queueIds = new Set(
      queueItems.map((item) => item.payload.instrumentId),
    );
    const pendingIds = new Set(
      pendingOrders.map((order) => order.instrumentId),
    );
    return { queueIds, pendingIds };
  }, [queueItems, pendingOrders]);

  const barsById = barsQuery.data?.barsById ?? null;
  const barsFailedIds = barsQuery.data?.failedIds ?? [];

  const rows = useMemo<AsesorCarteraRowV1[]>(() => {
    return universe.map((entry) => {
      const position: PositionDto | null = isPortfolioMeasured
        ? (openPositions.find(
            (candidate) => candidate.instrumentId === entry.instrumentId,
          ) ?? null)
        : null;

      const pair = position
        ? pickPositionStudies(position, studiesByDecision, studiesByInstrument)
        : {
            originStudy:
              studiesByInstrument.get(entry.instrumentId) ?? null,
            evolutionStudy:
              studiesByInstrument.get(entry.instrumentId) ?? null,
          };

      const facts: InstrumentOperationalFactsV1 =
        resolveInstrumentOperationalFacts({
          instrumentId: entry.instrumentId,
          inEstudio: members.some(
            (member) => member.instrumentId === entry.instrumentId,
          ),
          position,
          study: pair.evolutionStudy,
          originStudy: pair.originStudy,
          inConfirmQueue: operationsByInstrument.queueIds.has(
            entry.instrumentId,
          ),
          orderPendingFill: operationsByInstrument.pendingIds.has(
            entry.instrumentId,
          ),
        });

      const quote = quotesById.get(entry.instrumentId);
      const bars = barsById?.get(entry.instrumentId);
      const marketPrice = quotePrice(quote);
      const positionPrice = position?.lastPrice ?? null;
      const price = marketPrice ?? positionPrice ?? null;
      // R-04: la fuente del precio viaja en la fila para que la celda no presente
      // un mark de cartera como si fuera el cierre del lote de cotizaciones.
      const priceSource =
        marketPrice != null
          ? ("mercado" as const)
          : positionPrice != null
            ? ("cartera" as const)
            : null;

      return buildAsesorCarteraRow({
        instrumentId: entry.instrumentId,
        symbol: quote?.symbol ?? entry.symbol,
        name: quote?.name ?? entry.name,
        quote: {
          price,
          changePct: quoteChange(quote),
          source: priceSource,
          lastBarDate: quote?.meta?.lastBarDate ?? null,
          expectedLastBarDate: quote?.meta?.expectedLastBarDate ?? null,
          freshness: quote?.meta?.freshnessStatus ?? null,
        },
        opinion: opinionsById.get(entry.instrumentId) ?? null,
        study: pair.evolutionStudy,
        structure: memoizedStructureForBars(bars),
        phase: facts.phase,
        plan: facts.plan,
        position,
        portfolioMeasured: isPortfolioMeasured,
        markPrice: price,
      });
    });
  }, [
    universe,
    isPortfolioMeasured,
    openPositions,
    studiesByDecision,
    studiesByInstrument,
    members,
    operationsByInstrument,
    quotesById,
    barsById,
    opinionsById,
  ]);

  const summary = useMemo(() => summarizeAsesorCartera(rows), [rows]);

  const barsMissingIds = useMemo(() => {
    if (!barsQuery.data) return universeIds;
    return universeIds.filter((id) => !barsQuery.data.barsById.has(id));
  }, [barsQuery.data, universeIds]);

  return {
    rows,
    summary,
    universe,
    loading: portfolioQuery.isLoading || studiesQuery.isLoading,
    enriching:
      quotesQuery.isLoading ||
      opinionsQuery.isLoading ||
      barsQuery.isLoading,
    quotesLoading: quotesQuery.isLoading,
    opinionsLoading: opinionsQuery.isLoading,
    barsLoading: barsQuery.isLoading,
    portfolioMeasured: isPortfolioMeasured,
    portfolioError: Boolean(portfolioQuery.isError),
    studiesError: Boolean(studiesQuery.isError),
    studiesTruncated,
    quotesError: Boolean(quotesQuery.isError),
    barsError: Boolean(barsQuery.isError),
    barsFailedIds,
    barsMissingIds,
    empty: universe.length === 0,
  };
}
