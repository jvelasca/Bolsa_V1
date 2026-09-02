/**
 * Cliente HTTP del frontend hacia la API FastAPI (VITE_API_URL, default :8000).
 *
 * Punto único de integración web ↔ backend. Transporte openapi-fetch generado
 * desde apps/web/api/openapi.json (contrato F5a). Todas las peticiones envían
 * cookies (credentials:"include") para la sesión HttpOnly. Lanza ApiError en
 * respuestas no OK.
 *
 * @see docs/API_REFERENCE.md — mapa de endpoints
 * @see packages/shared/src/types.ts — DTOs TypeScript (manual, no OpenAPI gen)
 */
import createClient from "openapi-fetch";
import type { paths } from "@/api/schema";
import { getActiveAccountId } from "@/stores/active-account-store";
import { resolveApiBaseUrl } from "@/lib/api-base-url";

const API_URL = resolveApiBaseUrl();

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function formatApiErrorDetail(body: unknown): string | undefined {
  if (!body || typeof body !== "object") {
    return typeof body === "string" ? body : undefined;
  }
  const record = body as Record<string, unknown>;
  if (typeof record.error === "string") return record.error;
  if (typeof record.detail === "string") return record.detail;
  if (Array.isArray(record.detail)) {
    return record.detail
      .map((item) => {
        if (typeof item === "string") return item;
        if (item && typeof item === "object" && "msg" in item) {
          const loc =
            "loc" in item && Array.isArray(item.loc) ? item.loc.join(".") : "";
          const msg = String((item as { msg: unknown }).msg);
          return loc ? `${loc}: ${msg}` : msg;
        }
        return JSON.stringify(item);
      })
      .join("; ");
  }
  if (
    record.data &&
    typeof record.data === "object" &&
    record.data !== null &&
    "error" in record.data &&
    typeof (record.data as { error: unknown }).error === "string"
  ) {
    return (record.data as { error: string }).error;
  }
  return undefined;
}

type ClientResult = {
  data?: unknown;
  error?: unknown;
  response: Response;
};

/**
 * Cliente compartido openapi-fetch. `credentials:"include"` (config global del
 * cliente) hace que todas las peticiones envíen las cookies HttpOnly de sesión
 * (R-8B.2). El middleware onRequest inyecta X-Account-Id y Content-Type; las
 * cabeceras ya presentes en el request (p. ej. X-Account-Id explícito de
 * depositCash/withdrawCash) tienen prioridad y NO se sobreescriben — misma
 * semántica que el request<T> manual. Ya no se inyecta Authorization Bearer: la
 * sesión va en la cookie HttpOnly. onError traduce los errores de red
 * (TypeError) a ApiError con status 0.
 */
const client = createClient<paths>({
  baseUrl: API_URL,
  credentials: "include",
});

client.use({
  onRequest({ request }) {
    if (!request.headers.has("X-Account-Id")) {
      const accountId = getActiveAccountId();
      if (accountId) request.headers.set("X-Account-Id", accountId);
    }
    if (!request.headers.has("Content-Type")) {
      request.headers.set("Content-Type", "application/json");
    }
  },
  onError({ error }) {
    if (error instanceof TypeError) {
      throw new ApiError(
        "No se pudo contactar con la API. Comprueba que el backend esté en marcha (puerto 8000 o lanzador «Bolsa: API Python + Web»).",
        0,
      );
    }
    return error as Error;
  },
});

/**
 * Helper de desenvuelto: ejecuta la llamada openapi-fetch, propaga los errores
 * de red (ya traducidos a ApiError por onError), lanza ApiError en respuestas
 * no-OK (401 con mensaje específico; resto con formatApiErrorDetail) y devuelve
 * `data` (incluidos 204 / body vacío → undefined), replicando request<T>.
 */
async function call<T>(fn: () => Promise<ClientResult>): Promise<T> {
  const { data, error, response } = await fn();
  if (error !== undefined) {
    if (response.status === 401) {
      throw new ApiError("Sesión expirada o no autorizada", 401);
    }
    throw new ApiError(
      formatApiErrorDetail(error) ?? response.statusText,
      response.status,
    );
  }
  return data as T;
}

/**
 * D5 — fidelidad de tipos de valor (request body): el body de entrada (DTO
 * @bolsa/shared, única fuente del call site) puede divergir del requestBody
 * OpenAPI en optionality (p. ej. `localSummary?: string` vs `localSummary:
 * string`) o en index-signature de objetos anidados (p. ej. `StrategyDefinitionV1`
 * vs `{[x: string]: unknown}`). El wire format JSON es idéntico (`JSON.stringify`),
 * así que el cast es benigno; la deuda de fuente de verdad se cierra en P2.6.
 */
function apiBody<T>(body: T): never {
  return body as never;
}

export const api = {
  getHealth: () =>
    call<{
      status: string;
      service: string;
      timestamp: string;
      database?: { status: string; message: string };
      components?: Record<
        string,
        { status: string; message: string; details?: Record<string, unknown> }
      >;
    }>(() => client.GET("/api/health")),

  getRiskKillSwitch: () =>
    call<{
      effective: boolean;
      env: boolean;
      runtimeMemory: boolean;
      redis: boolean | null;
      paperDExecuteEnv: boolean;
      brokerVenue?: "paper" | "live";
    }>(() => client.GET("/api/risk/kill-switch")),

  setRiskKillSwitch: (enabled: boolean) =>
    call<{
      effective: boolean;
      env: boolean;
      runtimeMemory: boolean;
      redis: boolean | null;
      paperDExecuteEnv: boolean;
      brokerVenue?: "paper" | "live";
      updated?: { enabled: boolean; memory: boolean; redis: boolean };
    }>(() => client.POST("/api/risk/kill-switch", { body: { enabled } })),

  getBrokerVenue: () =>
    call<{
      brokerVenue: "paper" | "live";
      env: "paper" | "live";
      runtimeMemory: "paper" | "live" | null;
      redis: "paper" | "live" | null;
    }>(() => client.GET("/api/risk/broker-venue")),

  setBrokerVenue: (venue: "paper" | "live") =>
    call<{
      brokerVenue: "paper" | "live";
      env: "paper" | "live";
      runtimeMemory: "paper" | "live" | null;
      redis: "paper" | "live" | null;
    }>(() => client.POST("/api/risk/broker-venue", { body: { venue } })),

  /** PA-1 — preferencia Paper|Live por cuenta (settings_json); ≠ override global mesa. */
  getAccountBrokerVenue: (accountId: string) =>
    call<{
      accountId: string;
      preference: "paper" | "live" | null;
      effective: "paper" | "live";
    }>(() =>
      client.GET("/api/accounts/{account_id}/broker-venue", {
        params: { path: { account_id: accountId } },
      }),
    ),

  setAccountBrokerVenue: (accountId: string, venue: "paper" | "live") =>
    call<{
      accountId: string;
      preference: "paper" | "live" | null;
      effective: "paper" | "live";
    }>(() =>
      client.PATCH("/api/accounts/{account_id}/broker-venue", {
        params: { path: { account_id: accountId } },
        body: { venue },
      }),
    ),

  /** OE-1 — scorecard SEMI + AUTO (read-only; measure ≠ Accept). */
  getOpsSelfEval: (accountId?: string, lookbackDays = 120) =>
    call<{
      schemaVersion: string;
      rule: string;
      accountId: string;
      lookbackDays: number;
      lanes: {
        semi: {
          mark: string;
          confirmSeed: number | null;
          journalSeed: number | null;
          buysSeed: number | null;
          tradeLike: number | null;
          pathAvailable?: boolean;
        };
        auto: {
          mark: string;
          paperDExecuteEnv: boolean;
          executeOptIn: boolean;
          strictAcceptReady: boolean;
          p1: { daysWithOpinions: number | null; mark: string; need: number };
          p2: { confirmSeed: number | null; mark: string; need: number };
          p3: {
            buyPrecision5d: number | null;
            alarmaBuyCount: number | null;
            matureBuySample: number | null;
            mark: string;
            need: number;
          };
          p4: { buyRecall5d: number | null; mark: string; need: number };
          p5: {
            tradeLike: number | null;
            cashMaxDdFrac: number | null;
            mark: string;
            note: string | null;
          };
        };
      };
      runtime: {
        killSwitchEffective: boolean;
        brokerVenue: "paper" | "live";
        accountVenuePreference: "paper" | "live" | null;
        paperDExecuteEnv: boolean;
        confirmPathHonesty: string;
      };
      portfolioReconciliation: Record<string, unknown>;
      operationalReadiness?: {
        state:
          | "PAPER_READY"
          | "PAPER_DEGRADED"
          | "LIVE_EXPERIMENTAL"
          | "LIVE_BLOCKED";
        venue: "paper" | "live";
        reasons: string[];
        notes: string[];
        rule: string;
      };
    }>(() =>
      client.GET("/api/risk/ops-self-eval", {
        params: {
          query: {
            accountId: accountId ?? "default-account-seed",
            lookbackDays,
          },
        },
      }),
    ),

  getAiStatus: () =>
    call<{
      data: {
        preferredProvider: string;
        ollamaAvailable: boolean;
        openaiAvailable: boolean;
        callsRecorded: number;
        mode: string;
        auditSink: string;
        producerVersion: string;
      };
    }>(() => client.GET("/api/ai/status")),

  /** Coach profundo de batería (AT + perfil/TF). LLM vía proxy; heuristic si no hay provider.
   * mode=adversary → auditor C (solo findings tipados). */
  analyzeBacktestCoach: (
    body: {
      context: string;
      battery: string;
      localSummary?: string;
      facts?: import("@bolsa/shared").CoachFactsV1Dto | null;
      mode?: "narrate" | "adversary";
    },
    init?: { signal?: AbortSignal },
  ) =>
    call<{
      data: {
        engine: string;
        payload: {
          headline?: string;
          analysis?: string[];
          recommendations?: Array<{
            label?: string;
            strategyType?: string;
            score?: number;
            reasons?: string[];
          }>;
          regimeNarrative?: string;
          outlook?: string[];
          disclaimer?: string;
          audit?: {
            findings?: Array<{
              strategyType?: string;
              action?: string;
              code?: string;
              reason?: string;
            }>;
          };
        } | null;
        provider: string | null;
        model: string | null;
        validationErrors?: string[];
      };
    }>(() =>
      client.POST("/api/ai/backtest-coach/analyze", {
        body: apiBody(body),
        signal: init?.signal,
      }),
    ),

  /** F1b — copiloto FA (Ollama o heurística). Solo interpreta el card; no recalcula. */
  explainInstrumentFundamentals: (instrumentId: string) =>
    call<{ data: import("@bolsa/shared").FundamentalExplainResponseV1 }>(() =>
      client.POST("/api/ai/fundamentals/explain", { body: { instrumentId } }),
    ),

  /** Evidence sesión C DÍA D — interpreta métricas; sin FA/Coach. */
  explainDiaDSessionEvidence: (body: {
    mode: string;
    symbol: string;
    strategyLabel: string;
    diaD: string;
    endDate: string;
    initialCash?: number;
    auto: {
      totalReturnPct: number;
      maxDrawdownPct: number;
      tradeCount: number;
      finalEquity: number;
    };
    gated: {
      totalReturnPct: number;
      maxDrawdownPct: number;
      tradeCount: number;
      finalEquity: number;
    };
    gate: { accepted: number; rejected: number };
  }) =>
    call<{
      data: {
        engine: string;
        payload: {
          paragraphs: string[];
          disclaimer: string;
          band?: string;
          claims?: string[];
          warnings?: string[];
          metrics?: Record<string, number | string>;
          confidence?: string;
          schemaVersion?: string;
        };
        provider: string | null;
        model: string | null;
        evidence: Record<string, unknown>;
      };
    }>(() =>
      client.POST("/api/ai/dia-d/session-evidence", { body: apiBody(body) }),
    ),

  /** Evidence cola CORE-R — interpreta veredictos; sin FA/Coach/overwrite TOP. */
  explainCoreRReviewEvidence: (body: {
    listId: string;
    timeframe?: string;
    rows: Array<{
      instrumentId: string;
      symbol: string;
      verdict: string;
      reason?: string;
    }>;
  }) =>
    call<{
      data: {
        engine: string;
        payload: {
          paragraphs: string[];
          disclaimer: string;
          band?: string;
          claims?: string[];
          warnings?: string[];
          metrics?: Record<string, number | string>;
          confidence?: string;
          schemaVersion?: string;
        };
        provider: string | null;
        model: string | null;
        evidence: Record<string, unknown>;
      };
    }>(() =>
      client.POST("/api/ai/core-r/review-evidence", { body: apiBody(body) }),
    ),

  /** F2b lite — lista filings locales (disco; no Score_FUND). */
  listInstrumentFilings: (instrumentId: string) =>
    call<import("@bolsa/shared").InstrumentFilingListResponseV1>(() =>
      client.GET("/api/instruments/{instrument_id}/filings", {
        params: { path: { instrument_id: instrumentId } },
      }),
    ),

  uploadInstrumentFiling: async (
    instrumentId: string,
    file: File,
    kind: import("@bolsa/shared").InstrumentFilingKindV1 = "10-K",
  ) => {
    const accountId = getActiveAccountId();
    const body = new FormData();
    body.append("file", file);
    body.append("kind", kind);
    const response = await fetch(
      `${API_URL}/api/instruments/${instrumentId}/filings`,
      {
        method: "POST",
        headers: {
          ...(accountId ? { "X-Account-Id": accountId } : {}),
        },
        credentials: "include",
        body,
      },
    );
    if (!response.ok) {
      let detail: unknown;
      try {
        detail = await response.json();
      } catch {
        detail = undefined;
      }
      throw new ApiError(
        formatApiErrorDetail(detail) ?? response.statusText,
        response.status,
      );
    }
    return (await response.json()) as import("@bolsa/shared").InstrumentFilingUploadResponseV1;
  },

  deleteInstrumentFiling: (instrumentId: string, filingId: string) =>
    call<{ ok: boolean }>(() =>
      client.DELETE("/api/instruments/{instrument_id}/filings/{filing_id}", {
        params: {
          path: { instrument_id: instrumentId, filing_id: filingId },
        },
      }),
    ),

  /** F2b+ — último 10-K/10-Q desde SEC EDGAR (solo tickers US). */
  fetchInstrumentFilingFromSec: (
    instrumentId: string,
    kind: "10-K" | "10-Q" = "10-K",
  ) =>
    call<import("@bolsa/shared").InstrumentFilingUploadResponseV1>(() =>
      client.POST("/api/instruments/{instrument_id}/filings/sec-fetch", {
        params: { path: { instrument_id: instrumentId }, query: { kind } },
      }),
    ),

  summarizeInstrumentFiling: (instrumentId: string, filingId: string) =>
    call<{
      data: import("@bolsa/shared").InstrumentFilingSummarizeResponseV1;
    }>(() =>
      client.POST("/api/ai/fundamentals/filings/summarize", {
        body: { instrumentId, filingId },
      }),
    ),

  /** F2b++ — Q&A con retrieval TF-IDF local (sin vectores). */
  askInstrumentFiling: (
    instrumentId: string,
    filingId: string,
    question: string,
  ) =>
    call<{ data: import("@bolsa/shared").InstrumentFilingAskResponseV1 }>(() =>
      client.POST("/api/ai/fundamentals/filings/ask", {
        body: { instrumentId, filingId, question },
      }),
    ),

  /** RFC-008 D7 — resumen Efectividad (demo=true = ilustrativo hasta PG Trials/Memory). */
  getAiEffectiveness: (demo = false) =>
    call<{
      data: import("@bolsa/shared").EffectivenessSummaryV1;
    }>(() =>
      client.GET("/api/ai/effectiveness", {
        params: demo ? { query: { demo: true } } : undefined,
      }),
    ),

  getFeatureCatalog: () =>
    call<{
      data: {
        defs: Array<{
          featureId: string;
          featureKey: string;
          version: string;
          computeKey: string;
          parityRef?: string | null;
          params?: Record<string, unknown>;
        }>;
        sets: Array<{
          featureSetId: string;
          version: string;
          name?: string;
          compositionHash: string;
          memberCount?: number;
        }>;
      };
    }>(() => client.GET("/api/features/catalog")),

  listPredictions: (params?: {
    instrumentId?: string;
    modelId?: string;
    limit?: number;
  }) =>
    call<{ data: import("@bolsa/shared").PredictionV1[] }>(() =>
      client.GET("/api/predictions", { params: { query: params } }),
    ),

  listPredictionModels: () =>
    call<{
      data: {
        models: import("@bolsa/shared").ModelArtifactV1[];
        lightgbmAvailable: boolean;
        defaultModelId: string;
        persistence?: string;
      };
    }>(() => client.GET("/api/predictions/models")),

  predict: (body: {
    instrumentId: string;
    modelId?: string;
    timeframe?: string;
    barLimit?: number;
    horizon?: string;
  }) =>
    call<{ data: import("@bolsa/shared").PredictionV1 }>(() =>
      client.POST("/api/predictions/predict", { body: apiBody(body) }),
    ),

  trainPredictionModel: (body: {
    instrumentId: string;
    timeframe?: string;
    barLimit?: number;
  }) =>
    call<{ data: import("@bolsa/shared").ModelArtifactV1 }>(() =>
      client.POST("/api/predictions/models/train", { body: apiBody(body) }),
    ),

  getInstruments: () =>
    call<{ data: import("@bolsa/shared").InstrumentWithMetaDto[] }>(() =>
      client.GET("/api/instruments"),
    ),

  getInstrumentQuotes: (ids: string[]) =>
    call<{ data: import("@bolsa/shared").InstrumentWithMetaDto[] }>(() =>
      client.POST("/api/instruments/quotes", { body: { ids } }),
    ),

  getInstrumentProfile: (id: string) =>
    call<{ data: import("@bolsa/shared").InstrumentProfileDto | null }>(() =>
      client.GET("/api/instruments/{instrument_id}/profile", {
        params: { path: { instrument_id: id } },
      }),
    ),

  getInstrumentFundamentals: (id: string, opts?: { asOf?: string }) =>
    call<{ data: import("@bolsa/shared").FundamentalCardDto }>(() =>
      client.GET("/api/instruments/{instrument_id}/fundamentals", {
        params: {
          path: { instrument_id: id },
          query: opts?.asOf ? { asOf: opts.asOf } : undefined,
        },
      }),
    ),

  /** F3 — Composite Investment Score (Monitor). */
  getInstrumentComposite: (
    id: string,
    opts?: { horizon?: string; regime?: string; asOf?: string },
  ) =>
    call<{ data: import("@bolsa/shared").CompositeCardDto }>(() =>
      client.GET("/api/instruments/{instrument_id}/composite", {
        params: {
          path: { instrument_id: id },
          query: opts,
        },
      }),
    ),

  /** F4 — Screener FA (universo × gate; sin TA). */
  runFundamentalScreener: (
    body: import("@bolsa/shared").FundamentalScreenerRunRequestV1,
  ) =>
    call<{ data: import("@bolsa/shared").FundamentalScreenerRunResultV1 }>(() =>
      client.POST("/api/instruments/fundamentals/screener", {
        body: apiBody(body),
      }),
    ),

  /** Paper D — propose + execute opcional (Composite × universo). */
  proposePaperD: (body: import("@bolsa/shared").PaperDProposeRequestV1) =>
    call<{ data: import("@bolsa/shared").PaperDProposeResultV1 }>(() =>
      client.POST("/api/paper-d/propose", { body: apiBody(body) }),
    ),

  /** Pipeline semanal FA → whitelist → Paper D. */
  runFaWeeklyPipeline: (
    body: import("@bolsa/shared").FaWeeklyPipelineRequestV1,
  ) =>
    call<{ data: import("@bolsa/shared").FaWeeklyPipelineResultV1 }>(() =>
      client.POST("/api/paper-d/weekly-run", { body: apiBody(body) }),
    ),

  queryInstrumentFundamentals: (body: { instrumentIds: string[] }) =>
    call<{ data: import("@bolsa/shared").FundamentalChipDto[] }>(() =>
      client.POST("/api/instruments/fundamentals/query", {
        body: apiBody(body),
      }),
    ),

  /** Batch Composite chips (hub Instrumentos I2). Cap 40 ids/request. */
  queryInstrumentComposite: (body: {
    instrumentIds: string[];
    horizon?: string;
    regime?: string;
  }) =>
    call<{ data: import("@bolsa/shared").CompositeChipDto[] }>(() =>
      client.POST("/api/instruments/composite/query", { body: apiBody(body) }),
    ),

  getInstrumentDbInventory: (id: string) =>
    call<{ data: import("@bolsa/shared").InstrumentDbInventoryDto }>(() =>
      client.GET("/api/instruments/{instrument_id}/db-inventory", {
        params: { path: { instrument_id: id } },
      }),
    ),

  validateInstrumentXtb: (id: string) =>
    call<{ data: import("@bolsa/shared").InstrumentXtbValidationDto }>(() =>
      client.POST("/api/instruments/{instrument_id}/validate-xtb", {
        params: { path: { instrument_id: id } },
      }),
    ),

  searchInstruments: (q: string) =>
    call<import("@bolsa/shared").InstrumentSearchResponseDto>(() =>
      client.GET("/api/instruments/search", { params: { query: { q } } }),
    ),

  computeIndicators: (
    body: import("@bolsa/shared").ComputeIndicatorsRequestDto,
  ) =>
    call<import("@bolsa/shared").ComputeIndicatorsResponseDto>(() =>
      client.POST("/api/indicators/compute", { body: apiBody(body) }),
    ),

  replayDrawings: (body: import("@bolsa/shared").DrawingReplayRequestDto) =>
    call<import("@bolsa/shared").DrawingReplayResponseDto>(() =>
      client.POST("/api/drawings/replay", { body: apiBody(body) }),
    ),

  evaluateSignals: (body: import("@bolsa/shared").EvaluateSignalsRequestDto) =>
    call<import("@bolsa/shared").EvaluateSignalsResponseDto>(() =>
      client.POST("/api/signals/evaluate", { body: apiBody(body) }),
    ),

  runScan: (body: import("@bolsa/shared").ScanRunRequestDto) =>
    call<import("@bolsa/shared").ScanRunResponseDto>(() =>
      client.POST("/api/scans/run", { body: apiBody(body) }),
    ),

  enqueueScanJob: (body: import("@bolsa/shared").ScanRunRequestDto) =>
    call<import("@bolsa/shared").ScanJobResponseDto>(() =>
      client.POST("/api/scans/jobs", { body: apiBody(body) }),
    ),

  getScanJob: (jobId: string) =>
    call<import("@bolsa/shared").ScanJobResponseDto>(() =>
      client.GET("/api/scans/jobs/{job_id}", {
        params: { path: { job_id: jobId } },
      }),
    ),

  getScanManifest: (scanId: string) =>
    call<import("@bolsa/shared").ScanManifestResponseDto>(() =>
      client.GET("/api/scans/manifests/{scan_id}", {
        params: { path: { scan_id: scanId } },
      }),
    ),

  getScanJobs: () =>
    call<import("@bolsa/shared").ScanJobsListResponseDto>(() =>
      client.GET("/api/scans/jobs"),
    ),

  importInstrument: (body: {
    yahooSymbol: string;
    symbol: string;
    name: string;
    exchange: string;
    currency?: string;
    sync?: boolean;
    yearsBack?: number;
    isin?: string | null;
  }) =>
    call<import("@bolsa/shared").ImportInstrumentResponseDto>(() =>
      client.POST("/api/instruments/import", { body: apiBody(body) }),
    ),

  getInstrument: (id: string) =>
    call<{
      data: import("@bolsa/shared").InstrumentDto;
      meta: {
        lastSync: {
          status: string;
          barsAdded: number;
          syncedAt: string;
          error: string | null;
        } | null;
        priceSummary: import("@bolsa/shared").PriceSummaryDto | null;
      };
    }>(() =>
      client.GET("/api/instruments/{instrument_id}", {
        params: { path: { instrument_id: id } },
      }),
    ),

  getOhlcv: (id: string, limit = 365, timeframe = "1d") =>
    call<{
      data: import("@bolsa/shared").OhlcvBarDto[];
      meta: { timeframe: string; count: number };
    }>(() =>
      client.GET("/api/instruments/{instrument_id}/ohlcv", {
        params: {
          path: { instrument_id: id },
          query: { limit, timeframe },
        },
      }),
    ),

  getIndicators: (id: string, limit = 365, timeframe = "1d") =>
    call<{
      data: import("@bolsa/shared").IndicatorPointDto[];
      meta: {
        signals: {
          rsiZone: "overbought" | "oversold" | "neutral";
          smaCross: "bullish" | "bearish" | null;
        };
      };
    }>(() =>
      client.GET("/api/instruments/{instrument_id}/indicators", {
        params: {
          path: { instrument_id: id },
          query: { limit, timeframe },
        },
      }),
    ),

  getLiveQuote: (id: string) =>
    call<{ data: import("@bolsa/shared").InstrumentLiveQuoteDto }>(() =>
      client.GET("/api/instruments/{instrument_id}/live-quote", {
        params: { path: { instrument_id: id } },
      }),
    ),

  getInstrumentLiveQuotes: (ids: string[]) =>
    call<{ data: import("@bolsa/shared").InstrumentLiveQuoteDto[] }>(() =>
      client.POST("/api/instruments/live-quotes", { body: { ids } }),
    ),

  getDataStatus: (id: string, timeframe = "1d") =>
    call<{ data: import("@bolsa/shared").InstrumentDataStatusDto }>(() =>
      client.GET("/api/instruments/{instrument_id}/data-status", {
        params: {
          path: { instrument_id: id },
          query: { timeframe },
        },
      }),
    ),

  getDatabaseSummary: (instrumentId?: string) =>
    call<{ data: import("@bolsa/shared").DatabaseSummaryDto }>(() =>
      client.GET("/api/database/summary", {
        params: instrumentId ? { query: { instrumentId } } : undefined,
      }),
    ),

  getOrphanInstruments: (limit = 100) =>
    call<{ data: import("@bolsa/shared").OrphanInstrumentsDto }>(() =>
      client.GET("/api/database/orphans", { params: { query: { limit } } }),
    ),

  purgeOrphanInstruments: (limit = 50) =>
    call<{ data: import("@bolsa/shared").PurgeOrphansResultDto }>(() =>
      client.POST("/api/database/orphans/purge", { body: { limit } }),
    ),

  getClosedSimulatedAccounts: (limit = 100) =>
    call<{ data: import("@bolsa/shared").ClosedSimulatedAccountsDto }>(() =>
      client.GET("/api/database/closed-accounts", {
        params: { query: { limit } },
      }),
    ),

  purgeClosedSimulatedAccounts: (limit = 50) =>
    call<{ data: import("@bolsa/shared").PurgeClosedAccountsResultDto }>(() =>
      client.POST("/api/database/closed-accounts/purge", { body: { limit } }),
    ),

  getInstrumentRemovalPreview: (id: string, excludingListId?: string) =>
    call<{
      data: import("@bolsa/shared").InstrumentRemovalPreviewDto;
    }>(() =>
      client.GET("/api/instruments/{instrument_id}/removal-preview", {
        params: {
          path: { instrument_id: id },
          query: excludingListId ? { excludingListId } : undefined,
        },
      }),
    ),

  removeInstrumentFromList: (
    listId: string,
    instrumentId: string,
    body?: { purgeIfOrphan?: boolean },
  ) =>
    call<{
      data: import("@bolsa/shared").RemoveInstrumentFromListResultDto;
    }>(() =>
      client.POST("/api/lists/{list_id}/instruments/{instrument_id}/remove", {
        params: { path: { list_id: listId, instrument_id: instrumentId } },
        body: apiBody(body ?? {}),
      }),
    ),

  deleteInstrument: (id: string, force = false) =>
    call<void>(() =>
      client.DELETE("/api/instruments/{instrument_id}", {
        params: {
          path: { instrument_id: id },
          query: force ? { force: true } : undefined,
        },
      }),
    ),

  getMarketProviders: () =>
    call<{ data: import("@bolsa/shared").MarketProviderStatusDto[] }>(() =>
      client.GET("/api/market/providers"),
    ),

  getFxRate: (from: string, to: string) =>
    call<{ data: import("@bolsa/shared").FxRateDto }>(() =>
      client.GET("/api/market/fx", {
        params: { query: { from, to } },
      }),
    ),

  syncInstrument: async (id: string, yearsBack = 5) => {
    const result = await call<{
      data: {
        barsAdded: number;
        status: string;
        error?: string | null;
        barsInserted?: number;
        barsUpdated?: number;
        barsSkipped?: number;
        consolidationNotes?: string[];
      };
    }>(() =>
      client.POST("/api/instruments/{instrument_id}/sync", {
        params: { path: { instrument_id: id } },
        body: { yearsBack },
      }),
    );

    if (result.data.status === "failed") {
      throw new ApiError(result.data.error ?? "Error de sincronización", 502);
    }

    return result;
  },

  getPortfolio: () =>
    call<{ data: import("@bolsa/shared").PortfolioSummaryDto }>(() =>
      client.GET("/api/portfolio"),
    ),

  /** V1.89 — lifecycle sidecar snapshot (stage FSM). No cash ledger. */
  getLifecycleSnapshot: (positionId: string) =>
    call<{
      data: {
        positionId: string;
        stage: string;
        lineagePath: string;
        events: Array<Record<string, unknown>>;
        accounting: Record<string, unknown> | null;
      };
    }>(async () => {
      const accountId = getActiveAccountId();
      const response = await fetch(
        `${API_URL}/api/lifecycle/positions/${encodeURIComponent(positionId)}/snapshot`,
        {
          credentials: "include",
          headers: {
            Accept: "application/json",
            ...(accountId ? { "X-Account-Id": accountId } : {}),
          },
        },
      );
      const body = (await response.json().catch(() => null)) as unknown;
      if (!response.ok) {
        return { data: undefined, error: body, response };
      }
      return { data: body, error: undefined, response };
    }),

  updateAccount: (
    accountId: string,
    body: import("@bolsa/shared").UpdateInvestmentAccountRequestDto,
  ) =>
    call<{ data: import("@bolsa/shared").InvestmentAccountDto }>(() =>
      client.PATCH("/api/accounts/{account_id}", {
        params: { path: { account_id: accountId } },
        body,
        headers: { "X-Account-Id": accountId },
      }),
    ),

  setDefaultAccount: (accountId: string) =>
    call<{ data: import("@bolsa/shared").InvestmentAccountDto }>(() =>
      client.POST("/api/accounts/{account_id}/make-default", {
        params: { path: { account_id: accountId } },
        headers: { "X-Account-Id": accountId },
      }),
    ),

  closeAccount: (accountId: string) =>
    call<{ data: import("@bolsa/shared").InvestmentAccountDto }>(() =>
      client.POST("/api/accounts/{account_id}/close", {
        params: { path: { account_id: accountId } },
        headers: { "X-Account-Id": accountId },
      }),
    ),

  deleteAccount: (accountId: string) =>
    call<void>(() =>
      client.DELETE("/api/accounts/{account_id}", {
        params: { path: { account_id: accountId } },
        headers: { "X-Account-Id": accountId },
      }),
    ),

  getAccounts: (type?: import("@bolsa/shared").InvestmentAccountType) =>
    call<{ data: import("@bolsa/shared").InvestmentAccountDto[] }>(() =>
      client.GET("/api/accounts", {
        params: type ? { query: { type } } : undefined,
      }),
    ),

  createAccount: (
    body: import("@bolsa/shared").CreateInvestmentAccountRequestDto,
  ) =>
    call<{ data: import("@bolsa/shared").InvestmentAccountDto }>(() =>
      client.POST("/api/accounts", { body: apiBody(body) }),
    ),

  updateAccountSettings: (
    accountId: string,
    settings: import("@bolsa/shared").AccountSettings,
  ) =>
    call<{ data: import("@bolsa/shared").InvestmentAccountDto }>(() =>
      client.PATCH("/api/accounts/{account_id}/settings", {
        params: { path: { account_id: accountId } },
        body: { settings },
      }),
    ),

  listInvestorProfiles: () =>
    call<{ data: import("@bolsa/shared").InvestorProfileV1[] }>(() =>
      client.GET("/api/investor-profiles"),
    ),

  ensureDefaultInvestorProfiles: () =>
    call<{ data: import("@bolsa/shared").InvestorProfileV1[] }>(() =>
      client.POST("/api/investor-profiles/ensure-defaults"),
    ),

  getInvestorProfile: (profileId: string) =>
    call<{ data: import("@bolsa/shared").InvestorProfileV1 }>(() =>
      client.GET("/api/investor-profiles/{profile_id}", {
        params: { path: { profile_id: profileId } },
      }),
    ),

  createInvestorProfile: (body: {
    name: string;
    horizon: string;
    objectives: string[];
    riskTolerance: string;
    experience: string;
    maxAcceptableLossPct?: number | null;
    notes?: string | null;
    suggestedPolicyTemplateId?: string | null;
    selectedPolicyTemplateId?: string | null;
  }) =>
    call<{ data: import("@bolsa/shared").InvestorProfileV1 }>(() =>
      client.POST("/api/investor-profiles", { body: apiBody(body) }),
    ),

  updateInvestorProfile: (profileId: string, body: Record<string, unknown>) =>
    call<{ data: import("@bolsa/shared").InvestorProfileV1 }>(() =>
      client.PATCH("/api/investor-profiles/{profile_id}", {
        params: { path: { profile_id: profileId } },
        body,
      }),
    ),

  deleteInvestorProfile: (profileId: string) =>
    call<{ ok: boolean }>(() =>
      client.DELETE("/api/investor-profiles/{profile_id}", {
        params: { path: { profile_id: profileId } },
      }),
    ),

  getInstrumentStrategyTop: (instrumentId: string, timeframe = "1d") =>
    call<{ data: import("@bolsa/shared").InstrumentStrategyTopV1 | null }>(() =>
      client.GET("/api/instruments/{instrument_id}/strategy-top", {
        params: {
          path: { instrument_id: instrumentId },
          query: { timeframe },
        },
      }),
    ),

  getInstrumentNarrative: (
    instrumentId: string,
    scope: import("@bolsa/shared").InstrumentNarrativeScope = "estudio",
  ) =>
    call<{ data: import("@bolsa/shared").InstrumentNarrativeV1 | null }>(() =>
      client.GET("/api/instruments/{instrument_id}/narrative", {
        params: {
          path: { instrument_id: instrumentId },
          query: { scope },
        },
      }),
    ),

  upsertInstrumentNarrative: (
    instrumentId: string,
    body: import("@bolsa/shared").UpsertInstrumentNarrativeRequestV1,
  ) =>
    call<{ data: import("@bolsa/shared").InstrumentNarrativeV1 }>(() =>
      client.PUT("/api/instruments/{instrument_id}/narrative", {
        params: { path: { instrument_id: instrumentId } },
        body: apiBody(body),
      }),
    ),

  deleteInstrumentNarrative: (
    instrumentId: string,
    scope: import("@bolsa/shared").InstrumentNarrativeScope = "estudio",
  ) =>
    call<{ data: import("@bolsa/shared").InstrumentNarrativeV1 | null }>(() =>
      client.DELETE("/api/instruments/{instrument_id}/narrative", {
        params: {
          path: { instrument_id: instrumentId },
          query: { scope },
        },
      }),
    ),

  queryInstrumentDailyOpinions: (
    body: import("@bolsa/shared").QueryInstrumentDailyOpinionsRequestV1,
  ) =>
    call<{ data: import("@bolsa/shared").InstrumentDailyOpinionV1[] }>(() =>
      client.POST("/api/instrument-daily-opinions/query", {
        body: apiBody(body),
      }),
    ),

  getInstrumentDailyOpinion: (
    instrumentId: string,
    asOfBarDate?: string,
    forceRefresh = false,
  ) =>
    call<{
      data: import("@bolsa/shared").InstrumentDailyOpinionV1[];
    }>(() =>
      client.GET("/api/instruments/{instrument_id}/daily-opinion", {
        params: {
          path: { instrument_id: instrumentId },
          query: {
            ...(asOfBarDate ? { asOfBarDate } : {}),
            ...(forceRefresh ? { forceRefresh: true } : {}),
          },
        },
      }),
    ),

  listInstrumentDailyOpinions: (
    instrumentId: string,
    options?: { days?: number; ensureDays?: number },
  ) =>
    call<{
      data: import("@bolsa/shared").InstrumentDailyOpinionV1[];
    }>(() =>
      client.GET("/api/instruments/{instrument_id}/daily-opinions", {
        params: {
          path: { instrument_id: instrumentId },
          query: options ?? {},
        },
      }),
    ),

  runInstrumentDailyOpinionEodBatch: (body: {
    instrumentIds: string[];
    asOfBarDate?: string | null;
    accountId?: string | null;
    force?: boolean;
    notifyEmail?: string | null;
    notifyEmailEnabled?: boolean | null;
    notifyDigestEnabled?: boolean | null;
    attachPdf?: boolean | null;
  }) =>
    call<{
      enabled: boolean;
      forced: boolean;
      count: number;
      data: import("@bolsa/shared").InstrumentDailyOpinionV1[];
      emailNotify?: {
        emailEnabled: boolean;
        alarmaCount: number;
        sent: boolean;
        skippedReason?: string | null;
      } | null;
      digestNotify?: {
        digestEnabled: boolean;
        sent: boolean;
        skippedReason?: string | null;
        asOf?: string | null;
        pdfAttached?: boolean;
      } | null;
    }>(() =>
      client.POST("/api/instrument-daily-opinions/eod-batch", {
        body: apiBody(body),
      }),
    ),

  /** R3 — envío manual digest HTML (Asesor → Diario). */
  sendDailyOpsDigestEmail: (
    accountId: string,
    body: {
      asOf?: string | null;
      instrumentIds?: string[];
      notifyEmail?: string | null;
      notifyDigestEnabled?: boolean;
      attachPdf?: boolean | null;
    },
  ) =>
    call<{
      data: {
        digestEnabled: boolean;
        sent: boolean;
        skippedReason?: string | null;
        asOf?: string | null;
        pdfAttached?: boolean;
      };
    }>(() =>
      client.POST("/api/accounts/{account_id}/daily-ops-report/email", {
        params: { path: { account_id: accountId } },
        body: apiBody(body),
      }),
    ),

  /** R4 — descarga PDF del resumen operativo. */
  downloadDailyOpsDigestPdf: async (
    accountId: string,
    opts?: { asOf?: string; instrumentIds?: string[] },
  ): Promise<Blob> => {
    const q = new URLSearchParams();
    if (opts?.asOf) q.set("asOf", opts.asOf);
    if (opts?.instrumentIds?.length)
      q.set("instrumentIds", opts.instrumentIds.join(","));
    const qs = q.toString();
    const headers: HeadersInit = {};
    const account = getActiveAccountId();
    if (account) headers["X-Account-Id"] = account;
    const res = await fetch(
      `${API_URL}/api/accounts/${accountId}/daily-ops-report.pdf${qs ? `?${qs}` : ""}`,
      { headers, credentials: "include" },
    );
    if (!res.ok) {
      throw new ApiError(`PDF digest · HTTP ${res.status}`, res.status);
    }
    return res.blob();
  },

  getInstrumentDailyOpinionTelemetry: (opts?: {
    lookbackDays?: number;
    instrumentIds?: string[];
  }) =>
    call<{
      data: {
        schemaVersion: string;
        asOf: string;
        lookbackDays: number;
        daysWithOpinions: number;
        opinionRows: number;
        alarmaCount: number;
        alarmaBuyCount: number;
        matureBuySample: number;
        buyPrecision5d: number | null;
        buyHits: number;
        buyMisses: number;
        buyNeutrals: number;
        buyRecall5d: number | null;
        recallMoveSample: number;
        recallCaught: number;
        criteriaVersion: string;
        forwardBars: number;
        neutralBandPct: number;
        caveats: string[];
      };
    }>(() =>
      client.GET("/api/instrument-daily-opinions/telemetry", {
        params: { query: opts ?? {} },
      }),
    ),

  /**
   * V1.33+ Estudio AUTO propose. Dry-run por defecto (`execute: false`).
   * Execute real exige `PAPER_D_EXECUTE=1` + policy paper_auto — no usar desde Consola.
   */
  proposeEstudioAuto: async (body: {
    instrumentIds: string[];
    accountId?: string | null;
    asOfBarDate?: string | null;
    forceRefresh?: boolean;
    maxCandidates?: number;
    execute?: boolean;
    executionPolicyId?: string | null;
  }) => {
    const account = body.accountId ?? getActiveAccountId();
    const headers: HeadersInit = { "Content-Type": "application/json" };
    if (account) headers["X-Account-Id"] = account;
    const res = await fetch(
      `${API_URL}/api/instrument-daily-opinions/auto-propose`,
      {
        method: "POST",
        headers,
        credentials: "include",
        body: JSON.stringify({
          instrumentIds: body.instrumentIds,
          accountId: account ?? null,
          asOfBarDate: body.asOfBarDate ?? null,
          forceRefresh: body.forceRefresh ?? false,
          maxCandidates: body.maxCandidates ?? 25,
          execute: body.execute ?? false,
          executionPolicyId: body.executionPolicyId ?? null,
        }),
      },
    );
    if (!res.ok) {
      let detail: unknown;
      try {
        detail = await res.json();
      } catch {
        detail = undefined;
      }
      throw new ApiError(
        formatApiErrorDetail(detail) ?? res.statusText,
        res.status,
      );
    }
    return (await res.json()) as {
      data: {
        planId?: string;
        generatedAt?: string;
        candidateCount?: number;
        hitCount?: number;
        executeStatus?: string;
        skippedByReason?: Record<string, number>;
        hitsBySource?: Record<string, number>;
        [key: string]: unknown;
      };
    };
  },

  /** A6 — embudo Estudio AUTO (read-only; ≠ flip execute · ≠ Radar/Hoy). */
  getEstudioAutoTelemetry: async (opts?: {
    lookbackDays?: number;
    accountId?: string;
    instrumentIds?: string[];
  }) => {
    const q = new URLSearchParams();
    q.set("lookbackDays", String(opts?.lookbackDays ?? 120));
    if (opts?.accountId) q.set("accountId", opts.accountId);
    for (const id of opts?.instrumentIds ?? []) {
      if (id.trim()) q.append("instrumentIds", id.trim());
    }
    const account = getActiveAccountId();
    const headers: HeadersInit = {};
    if (account) headers["X-Account-Id"] = account;
    const res = await fetch(
      `${API_URL}/api/instrument-daily-opinions/auto-telemetry?${q.toString()}`,
      { headers, credentials: "include" },
    );
    if (!res.ok) {
      let detail: unknown;
      try {
        detail = await res.json();
      } catch {
        detail = undefined;
      }
      throw new ApiError(
        formatApiErrorDetail(detail) ?? res.statusText,
        res.status,
      );
    }
    return (await res.json()) as {
      data: {
        schemaVersion: string;
        rule: string;
        asOf: string;
        lookbackDays: number;
        funnel: {
          opinionRows: number;
          daysWithOpinions: number;
          candidatesAlarma: number;
          candidatesDictamen: number;
          candidatesTotal: number;
          notCandidate: number;
          allowedSources: string[];
          excludedSources: string[];
        };
        edgeReport: {
          paperAutoRequiresEdgeReport: boolean;
          parityWithSemi: boolean;
          mark: string;
          note: string;
        };
        p1p5: {
          mark: string;
          strictAcceptReady: boolean;
          source: string;
        };
        lastPropose: {
          generatedAt?: string | null;
          planId?: string | null;
          candidateCount: number;
          hitCount: number;
          executeStatus?: string | null;
          skippedByReason: Record<string, number>;
          hitsBySource: Record<string, number>;
          durability: string;
        } | null;
        recentProposes: Array<{
          generatedAt?: string | null;
          planId?: string | null;
          candidateCount: number;
          hitCount: number;
          executeStatus?: string | null;
          skippedByReason: Record<string, number>;
          hitsBySource: Record<string, number>;
          durability: string;
        }>;
        gates: {
          expandSourcesReady: boolean;
          sourcesShouldContract: boolean;
          thawEstrictoReady: boolean;
          paperDExecuteEnv: boolean;
          blockers: string[];
        };
        caveats: string[];
      };
    };
  },

  getAccountMandates: (accountId: string, instrumentId?: string) =>
    call<{ data: import("@bolsa/shared").MandateBundleDto }>(() =>
      client.GET("/api/accounts/{account_id}/mandates", {
        params: {
          path: { account_id: accountId },
          query: instrumentId ? { instrumentId } : undefined,
        },
      }),
    ),

  syncAccountMandates: (
    accountId: string,
    body: import("@bolsa/shared").MandateBundleDto,
  ) =>
    call<{ data: import("@bolsa/shared").MandateBundleDto }>(() =>
      client.PUT("/api/accounts/{account_id}/mandates", {
        params: { path: { account_id: accountId } },
        body: apiBody(body),
      }),
    ),

  getAccountCoreR: (accountId: string) =>
    call<{ data: import("@bolsa/shared").CoreRBundleDto }>(() =>
      client.GET("/api/accounts/{account_id}/core-r", {
        params: { path: { account_id: accountId } },
      }),
    ),

  syncAccountCoreR: (
    accountId: string,
    body: {
      queue: Array<import("@bolsa/shared").CoreRQueueItemDto>;
      reports: import("@bolsa/shared").CoreRReportsMapDto;
      scheduler: import("@bolsa/shared").CoreRSchedulerPrefsDto;
    },
  ) =>
    call<{ data: import("@bolsa/shared").CoreRBundleDto }>(() =>
      client.PUT("/api/accounts/{account_id}/core-r", {
        params: { path: { account_id: accountId } },
        body,
      }),
    ),

  getAccountSupervisedF3: (accountId: string) =>
    call<{ data: import("@bolsa/shared").SupervisedF3BundleDto }>(() =>
      client.GET("/api/accounts/{account_id}/supervised-f3-queue", {
        params: { path: { account_id: accountId } },
      }),
    ),

  syncAccountSupervisedF3: (
    accountId: string,
    body: {
      items: Array<import("@bolsa/shared").SupervisedF3QueueItemDto>;
      activeId?: string | null;
    },
  ) =>
    call<{ data: import("@bolsa/shared").SupervisedF3BundleDto }>(() =>
      client.PUT("/api/accounts/{account_id}/supervised-f3-queue", {
        params: { path: { account_id: accountId } },
        body,
      }),
    ),

  /** Ops: tick CORE-R servidor (informe BD + PnL DEMO). */
  runCoreRCronTick: (force = false, includePnl = true) =>
    call<{
      data: {
        accounts: number;
        ticked: number;
        totalAdded: number;
        results: Array<Record<string, unknown>>;
      };
    }>(() =>
      client.POST("/api/core-r/cron/tick", {
        params: {
          query: {
            ...(force ? { force: true } : {}),
            ...(!includePnl ? { include_pnl: false } : {}),
          },
        },
      }),
    ),

  queryInstrumentStrategyTops: (body: {
    instrumentIds: string[];
    timeframe?: string;
  }) =>
    call<{ data: import("@bolsa/shared").InstrumentStrategyTopV1[] }>(() =>
      client.POST("/api/instrument-strategy-tops/query", {
        body: apiBody(body),
      }),
    ),

  upsertInstrumentStrategyTop: (
    instrumentId: string,
    body: import("@bolsa/shared").UpsertInstrumentStrategyTopRequestV1,
  ) =>
    call<{ data: import("@bolsa/shared").InstrumentStrategyTopV1 }>(() =>
      client.PUT("/api/instruments/{instrument_id}/strategy-top", {
        params: { path: { instrument_id: instrumentId } },
        body: apiBody(body),
      }),
    ),

  deleteInstrumentStrategyTop: (instrumentId: string, timeframe = "1d") =>
    call<{ ok: boolean }>(() =>
      client.DELETE("/api/instruments/{instrument_id}/strategy-top", {
        params: {
          path: { instrument_id: instrumentId },
          query: { timeframe },
        },
      }),
    ),

  assignAccountProfile: (accountId: string, profileId: string | null) =>
    call<{ data: { accountId: string; activeProfileId: string | null } }>(() =>
      client.PUT("/api/accounts/{account_id}/active-profile", {
        params: { path: { account_id: accountId } },
        body: { profileId },
      }),
    ),

  getAccountActiveProfile: (accountId: string) =>
    call<{ data: import("@bolsa/shared").InvestorProfileV1 }>(() =>
      client.GET("/api/accounts/{account_id}/active-profile", {
        params: { path: { account_id: accountId } },
      }),
    ),

  refreshInvestorProfileObserved: (profileId: string, accountId?: string) =>
    call<{ data: import("@bolsa/shared").InvestorProfileV1 }>(() =>
      client.POST("/api/investor-profiles/{profile_id}/refresh-observed", {
        params: {
          path: { profile_id: profileId },
          query: accountId ? { accountId } : undefined,
        },
      }),
    ),

  proposeRecommendation: (body: {
    instrumentId: string;
    symbol?: string;
    accountId?: string;
    suggestedQuantity: number;
    suggestedPrice?: number | null;
    action?: "recommend_long" | "recommend_short" | "wait";
    includeFundamentals?: boolean;
    includeMacro?: boolean;
    includeEvidence?: boolean;
    includeNews?: boolean;
    strategyOrSignalRef?: string;
    horizon?: "intraday" | "swing" | "position" | "long_term";
    macro?: Record<string, unknown>;
  }) =>
    call<{
      data: import("@bolsa/shared").RecommendationV1 & {
        technicalAssessment?: import("@bolsa/shared").TechnicalAssessmentV1;
        fundamentalAssessment?: import("@bolsa/shared").FundamentalAssessmentV1;
        macroAssessment?: import("@bolsa/shared").MacroAssessmentV1;
        evidenceAssessment?: import("@bolsa/shared").EvidenceAssessmentV1;
        newsAssessment?: import("@bolsa/shared").NewsAssessmentV1;
        assessments?: import("@bolsa/shared").AssessmentV1[];
        decisionPackage?: Record<string, unknown>;
        policyGate?: {
          status?: string;
          mode?: string;
          message?: string;
        } | null;
        lastClose?: number | null;
        source?: string;
        decisionSession?: import("@bolsa/shared").DecisionSessionV1;
        weightContext?: import("@bolsa/shared").WeightContextV1;
        combinedScore?: number;
      };
    }>(() =>
      client.POST("/api/ai/recommendations/propose", { body: apiBody(body) }),
    ),

  getDecisionSession: (sessionId: string) =>
    call<{ data: import("@bolsa/shared").DecisionSessionV1 }>(() =>
      client.GET("/api/ai/decision-sessions/{session_id}", {
        params: { path: { session_id: sessionId } },
      }),
    ),

  getDecisionSessionReplay: (sessionId: string) =>
    call<{ data: import("@bolsa/shared").DecisionReplayV1 }>(() =>
      client.GET("/api/ai/decision-sessions/{session_id}/replay", {
        params: { path: { session_id: sessionId } },
      }),
    ),

  listDecisionSessions: (params?: {
    accountId?: string;
    instrumentId?: string;
    limit?: number;
  }) =>
    call<{
      data: import("@bolsa/shared").DecisionSessionSummaryV1[];
    }>(() =>
      client.GET("/api/ai/decision-sessions", { params: { query: params } }),
    ),

  closeDecisionSessionOutcome: (
    sessionId: string,
    body?: {
      mode?: "auto" | "manual";
      verdict?: import("@bolsa/shared").SessionOutcomeVerdict;
      returnPct?: number;
      priceAtEval?: number;
      notes?: string;
      force?: boolean;
    },
  ) =>
    call<{ data: import("@bolsa/shared").DecisionSessionV1 }>(() =>
      client.POST("/api/ai/decision-sessions/{session_id}/outcome", {
        params: { path: { session_id: sessionId } },
        body: apiBody(body ?? { mode: "auto" }),
      }),
    ),

  getDecisionSessionLearningSummary: (params?: {
    accountId?: string;
    instrumentId?: string;
    limit?: number;
  }) =>
    call<{ data: import("@bolsa/shared").SessionLearningSummaryV1 }>(() =>
      client.GET("/api/ai/decision-sessions/learning-summary", {
        params: { query: params },
      }),
    ),

  confirmOrderIntent: (body: {
    recommendation:
      | import("@bolsa/shared").RecommendationV1
      | Record<string, unknown>;
    accountId: string;
    execute?: boolean;
    sessionId?: string;
    riskOverrideReason?: string | null;
    signedStop?: number | null;
  }) =>
    call<{
      data: {
        intent: import("@bolsa/shared").OrderIntentV1;
        trade: {
          status: string;
          reason?: string;
          transactionId?: string | null;
        } | null;
        executionRecord?: import("@bolsa/shared").ExecutionRecordV1;
        paperOrder?: import("@bolsa/shared").PaperOrderV1;
        paperBroker?: import("@bolsa/shared").PaperBrokerReceiptV1;
        brokerAdapter?: import("@bolsa/shared").BrokerAdapterReceiptV1;
        positionPersist?: { status?: string; reason?: string };
        decisionSession?: import("@bolsa/shared").DecisionSessionV1 | null;
      };
    }>(() => client.POST("/api/ai/intents/confirm", { body: apiBody(body) })),

  getAccountSummary: (accountId: string) =>
    call<{ data: import("@bolsa/shared").AccountSummaryDto }>(() =>
      client.GET("/api/accounts/{account_id}/summary", {
        params: { path: { account_id: accountId } },
      }),
    ),

  /** R1 — resumen operativo diario (Asesor → Diario). */
  getDailyOpsReport: (
    accountId: string,
    opts?: { asOf?: string; instrumentIds?: string[] },
  ) =>
    call<import("@bolsa/shared").DailyOpsReportResponseV1>(() =>
      client.GET("/api/accounts/{account_id}/daily-ops-report", {
        params: {
          path: { account_id: accountId },
          // El contrato declara instrumentIds como string (comma-joined), igual
          // al wire format del request<T> manual (join(",")).
          query: {
            ...(opts?.asOf ? { asOf: opts.asOf } : {}),
            ...(opts?.instrumentIds?.length
              ? { instrumentIds: opts.instrumentIds.join(",") }
              : {}),
          },
        },
      }),
    ),

  /**
   * V1.47 / V1.68 — DailyOpsReport + autoDesk (PaperDeskCycle dry-run evaluate).
   * Hoy usa este path para Operating Desk; no muta ledger.
   */
  getPaperDeskDailyReport: (
    accountId: string,
    opts?: { asOf?: string; templateId?: string },
  ) =>
    call<import("@bolsa/shared").DailyOpsReportResponseV1>(async () => {
      const params = new URLSearchParams({ accountId });
      if (opts?.asOf) params.set("asOf", opts.asOf);
      if (opts?.templateId) params.set("templateId", opts.templateId);
      const response = await fetch(
        `${API_URL}/api/paper-desk/daily-report?${params.toString()}`,
        {
          credentials: "include",
          headers: {
            "X-Account-Id": accountId,
            Accept: "application/json",
          },
        },
      );
      const body = (await response.json().catch(() => null)) as unknown;
      if (!response.ok) {
        return { data: undefined, error: body, response };
      }
      return { data: body, error: undefined, response };
    }),

  getAccountSummaries: (type?: string) =>
    call<{ data: import("@bolsa/shared").AccountSummaryDto[] }>(() =>
      client.GET("/api/accounts/summaries", {
        params: type ? { query: { type } } : undefined,
      }),
    ),

  /** F0.6 — Decision Board (solo lectura): oportunidades pendientes + gates. */
  getDecisionBoard: (accountId: string) =>
    call<import("@bolsa/shared").DecisionBoardResponseV1>(() =>
      client.GET("/api/accounts/{account_id}/decision-board", {
        params: { path: { account_id: accountId } },
      }),
    ),

  /** DEX-3 — incidentes operacionales activos (open/in_review/resolved). */
  getActiveOperationalIncidents: (accountId: string) =>
    call<{
      data: {
        accountId: string;
        incidents: import("@bolsa/shared").OperationalIncidentV1[];
        total: number;
      };
    }>(() =>
      client.GET("/api/accounts/{account_id}/operational-incidents/active", {
        params: { path: { account_id: accountId } },
      }),
    ),

  /** F2b — submit intents in-flight (recorded/send_attempted/venue_bound). Solo lectura. */
  getSubmitIntents: (accountId: string) =>
    call<{
      data: {
        accountId: string;
        intents: import("@bolsa/shared").SubmitIntentListItemV1[];
        total: number;
      };
    }>(() =>
      client.GET("/api/accounts/{account_id}/submit-intents", {
        params: { path: { account_id: accountId } },
      }),
    ),

  resolveOperationalIncident: (
    accountId: string,
    incidentId: string,
    body: { resolutionNote: string; resolvedBy?: string },
  ) =>
    call<{ data: import("@bolsa/shared").OperationalIncidentV1 }>(() =>
      client.POST(
        "/api/accounts/{account_id}/operational-incidents/{incident_id}/resolve",
        {
          params: {
            path: { account_id: accountId, incident_id: incidentId },
          },
          body,
        },
      ),
    ),

  clearOperationalIncident: (accountId: string, incidentId: string) =>
    call<{ data: import("@bolsa/shared").OperationalIncidentV1 }>(() =>
      client.POST(
        "/api/accounts/{account_id}/operational-incidents/{incident_id}/clear",
        {
          params: {
            path: { account_id: accountId, incident_id: incidentId },
          },
        },
      ),
    ),

  /** F3 — Decision Journal (solo lectura): audit trail append-only del spine. */
  getDecisionJournal: (
    accountId: string,
    opts?: {
      instrumentId?: string;
      since?: string;
      eventType?: string;
      limit?: number;
      offset?: number;
    },
  ) =>
    call<{
      data: {
        accountId: string;
        entries: import("@bolsa/shared").DecisionJournalEntryV1[];
        limit: number;
        offset: number;
        total: number;
      };
    }>(() =>
      client.GET("/api/accounts/{account_id}/decision-journal", {
        params: {
          path: { account_id: accountId },
          query: opts,
        },
      }),
    ),

  /** ADR-036 — Tesis: última sesión propose por instrumento (solo lectura). */
  getDecisionStudies: (
    accountId: string,
    opts?: {
      listId?: string;
      q?: string;
      period?: string;
      opinion?: string;
      status?: string;
      strengthBand?: string;
      from?: string;
      to?: string;
      limit?: number;
      offset?: number;
    },
  ) =>
    call<import("@bolsa/shared").DecisionJournalStudyListResponseV1>(() =>
      client.GET("/api/accounts/{account_id}/decision-studies", {
        params: {
          path: { account_id: accountId },
          query: opts,
        },
      }),
    ),

  /** ADR-036 Evolución — historial propose por instrumento (solo lectura). */
  getDecisionStudyHistory: (
    accountId: string,
    instrumentId: string,
    opts?: { limit?: number; offset?: number },
  ) =>
    call<import("@bolsa/shared").DecisionJournalStudyHistoryResponseV1>(() =>
      client.GET(
        "/api/accounts/{account_id}/decision-studies/{instrument_id}/history",
        {
          params: {
            path: { account_id: accountId, instrument_id: instrumentId },
            query: opts,
          },
        },
      ),
    ),

  recordSessionVerdict: (
    accountId: string,
    body: { verdict: "no_trade"; note?: string },
  ) =>
    call<{
      data: {
        decisionId: string;
        sessionVerdict: string;
        recordedAt: string;
      };
    }>(() =>
      client.POST("/api/accounts/{account_id}/session-verdict", {
        params: { path: { account_id: accountId } },
        body: apiBody(body),
      }),
    ),

  getAccountLedger: (accountId: string, limit = 50, offset = 0) =>
    call<{ data: import("@bolsa/shared").LedgerEntryDto[] }>(() =>
      client.GET("/api/accounts/{account_id}/ledger", {
        params: {
          path: { account_id: accountId },
          query: { limit, offset },
        },
      }),
    ),

  getTaxReport: (accountId: string, year?: number) =>
    call<{ data: import("@bolsa/shared").TaxReportSummaryDto }>(() =>
      client.GET("/api/accounts/{account_id}/tax-report", {
        params: {
          path: { account_id: accountId },
          query: year != null ? { year } : undefined,
        },
      }),
    ),

  depositCash: (
    accountId: string,
    body: import("@bolsa/shared").DepositCashRequestDto,
  ) =>
    call<{ data: import("@bolsa/shared").CashMovementResultDto }>(() =>
      client.POST("/api/accounts/{account_id}/deposits", {
        params: { path: { account_id: accountId } },
        body,
        headers: { "X-Account-Id": accountId },
      }),
    ),

  withdrawCash: (
    accountId: string,
    body: import("@bolsa/shared").WithdrawCashRequestDto,
  ) =>
    call<{ data: import("@bolsa/shared").CashMovementResultDto }>(() =>
      client.POST("/api/accounts/{account_id}/withdrawals", {
        params: { path: { account_id: accountId } },
        body,
        headers: { "X-Account-Id": accountId },
      }),
    ),

  getTransactions: (limit = 50) =>
    call<{ data: import("@bolsa/shared").TransactionDto[] }>(() =>
      client.GET("/api/portfolio/transactions", {
        params: { query: { limit } },
      }),
    ),

  executeTrade: (body: {
    instrumentId: string;
    type: "buy" | "sell";
    quantity: number;
    price: number;
    idempotencyKey: string;
  }) =>
    call<{
      data: {
        transaction: import("@bolsa/shared").TransactionDto;
        summary: import("@bolsa/shared").PortfolioSummaryDto;
      };
    }>(() => client.POST("/api/portfolio/trade", { body: apiBody(body) })),

  getBacktests: (limit = 20) =>
    call<{ data: import("@bolsa/shared").BacktestRunDto[] }>(() =>
      client.GET("/api/backtests", { params: { query: { limit } } }),
    ),

  pruneBacktests: (keep: number) =>
    call<{ deleted: number; keep: number }>(() =>
      client.POST("/api/backtests/prune", { body: { keep } }),
    ),

  getBacktest: (id: string) =>
    call<{ data: import("@bolsa/shared").BacktestRunDetailDto }>(() =>
      client.GET("/api/backtests/{run_id}", {
        params: { path: { run_id: id } },
      }),
    ),

  runBacktest: (
    body: {
      instrumentId: string;
      strategyType?: import("@bolsa/shared").BacktestStrategyType;
      strategyDefinitionId?: string;
      initialCash?: number;
      limit?: number;
      dateFrom?: string;
      dateTo?: string;
      timeframe?: string;
      commissionBps?: number;
      slippageBps?: number;
      spreadBps?: number;
      /** P9 — lab provenance stamped onto the new research_trial.blocks after adopt. */
      labEvidence?: import("@bolsa/shared").PaperLabEvidenceSnapshot | null;
    },
    init?: { signal?: AbortSignal },
  ) =>
    call<import("@bolsa/shared").BacktestRunResponseDto>(() =>
      client.POST("/api/backtests/run", { body, signal: init?.signal }),
    ),

  getResearchTrials: (
    query: import("@bolsa/shared").ResearchTrialsQuery = {},
  ) =>
    call<import("@bolsa/shared").ResearchTrialsListResponseDto>(() =>
      client.GET("/api/research/trials", { params: { query } }),
    ),

  getResearchTrial: (id: string) =>
    call<import("@bolsa/shared").ResearchTrialDetailResponseDto>(() =>
      client.GET("/api/research/trials/{trial_id}", {
        params: { path: { trial_id: id } },
      }),
    ),

  getInstrumentResearchSummary: (instrumentId: string) =>
    call<{ data: import("@bolsa/shared").InstrumentResearchSummaryDto }>(() =>
      client.GET("/api/research/instruments/{instrument_id}/summary", {
        params: { path: { instrument_id: instrumentId } },
      }),
    ),

  getLaboratoryResearchSummary: () =>
    call<{ data: import("@bolsa/shared").LaboratoryResearchSummaryDto }>(() =>
      client.GET("/api/research/summary"),
    ),

  getLabHealth: () =>
    call<{ data: import("@bolsa/shared").LabHealthDto }>(() =>
      client.GET("/api/research/lab-health"),
    ),

  /** Evidence sesión C DÍA D → Fase 2 research_evidence (source=dia_d_session). */
  persistDiaDSessionEvidence: (body: {
    instrumentId: string;
    symbol: string;
    mode: string;
    strategyLabel: string;
    diaD: string;
    endDate: string;
    engine?: string;
    evidence: import("@bolsa/shared").DiaDSessionEvidenceV1Dto;
  }) =>
    call<{
      data: {
        id: string;
        instrumentId: string;
        level: string;
        source: string;
        evidenceWeight: number;
        summary: Record<string, unknown>;
        createdAt: string;
      };
    }>(() =>
      client.POST("/api/research/dia-d-session-evidence", {
        body: apiBody(body),
      }),
    ),

  optimizeBacktest: (body: import("@bolsa/shared").OptimizeSmaGridRequestDto) =>
    call<import("@bolsa/shared").OptimizeSmaGridResponseDto>(() =>
      client.POST("/api/backtests/optimize", { body: apiBody(body) }),
    ),

  enqueueOptimizeJob: (
    body: import("@bolsa/shared").OptimizeSmaGridRequestDto,
  ) =>
    call<import("@bolsa/shared").OptimizationRunResponseDto>(() =>
      client.POST("/api/backtests/optimize/jobs", { body: apiBody(body) }),
    ),

  getOptimizeRun: (runId: string) =>
    call<import("@bolsa/shared").OptimizationRunResponseDto>(() =>
      client.GET("/api/backtests/optimize/runs/{run_id}", {
        params: { path: { run_id: runId } },
      }),
    ),

  getOptimizeRuns: () =>
    call<import("@bolsa/shared").OptimizationRunsListResponseDto>(() =>
      client.GET("/api/backtests/optimize/runs"),
    ),

  getStrategies: () =>
    call<{ data: import("@bolsa/shared").StrategyDefinitionSummaryDto[] }>(() =>
      client.GET("/api/strategies"),
    ),

  getStrategy: (id: string) =>
    call<{ data: import("@bolsa/shared").StrategyDefinitionDetailDto }>(() =>
      client.GET("/api/strategies/{strategy_id}", {
        params: { path: { strategy_id: id } },
      }),
    ),

  createStrategyFromPreset: (
    body: import("@bolsa/shared").CreateStrategyFromPresetDto,
  ) =>
    call<{ data: import("@bolsa/shared").StrategyDefinitionDetailDto }>(() =>
      client.POST("/api/strategies/from-preset", { body: apiBody(body) }),
    ),

  draftStrategyFromPrompt: (
    body: import("@bolsa/shared").DraftStrategyFromPromptRequestDto,
  ) =>
    call<{ data: import("@bolsa/shared").DraftStrategyFromPromptResultDto }>(
      () =>
        client.POST("/api/strategies/draft-from-prompt", {
          body: apiBody(body),
        }),
    ),

  draftIndicatorFromPrompt: (
    body: import("@bolsa/shared").DraftIndicatorFromPromptRequestDto,
  ) =>
    call<{
      data: import("@bolsa/shared").DraftIndicatorFromPromptResultDto;
    }>(() =>
      client.POST("/api/indicators/draft-from-prompt", { body: apiBody(body) }),
    ),

  createStrategy: (body: import("@bolsa/shared").UpsertStrategyDefinitionDto) =>
    call<{ data: import("@bolsa/shared").StrategyDefinitionDetailDto }>(() =>
      client.POST("/api/strategies", { body: apiBody(body) }),
    ),

  updateStrategy: (
    id: string,
    body: import("@bolsa/shared").UpdateStrategyDefinitionDto,
  ) =>
    call<{ data: import("@bolsa/shared").StrategyDefinitionDetailDto }>(() =>
      client.PATCH("/api/strategies/{strategy_id}", {
        params: { path: { strategy_id: id } },
        body: apiBody(body),
      }),
    ),

  deleteStrategy: (id: string) =>
    call<void>(() =>
      client.DELETE("/api/strategies/{strategy_id}", {
        params: { path: { strategy_id: id } },
      }),
    ),

  getTrackers: (enabledOnly = false) =>
    call<import("@bolsa/shared").TrackerDefinitionsListResponseDto>(() =>
      client.GET("/api/trackers", {
        params: enabledOnly ? { query: { enabled_only: true } } : undefined,
      }),
    ),

  getTracker: (id: string) =>
    call<import("@bolsa/shared").TrackerDefinitionResponseDto>(() =>
      client.GET("/api/trackers/{tracker_id}", {
        params: { path: { tracker_id: id } },
      }),
    ),

  createTracker: (body: import("@bolsa/shared").CreateTrackerDefinitionDto) =>
    call<import("@bolsa/shared").TrackerDefinitionResponseDto>(() =>
      client.POST("/api/trackers", { body: apiBody(body) }),
    ),

  updateTracker: (
    id: string,
    body: import("@bolsa/shared").UpdateTrackerDefinitionDto,
  ) =>
    call<import("@bolsa/shared").TrackerDefinitionResponseDto>(() =>
      client.PATCH("/api/trackers/{tracker_id}", {
        params: { path: { tracker_id: id } },
        body: apiBody(body),
      }),
    ),

  deleteTracker: (id: string) =>
    call<void>(() =>
      client.DELETE("/api/trackers/{tracker_id}", {
        params: { path: { tracker_id: id } },
      }),
    ),

  runTrackerScan: (trackerId: string) =>
    call<import("@bolsa/shared").ScanRunResponseDto>(() =>
      client.POST("/api/trackers/{tracker_id}/scan", {
        params: { path: { tracker_id: trackerId } },
      }),
    ),

  enqueueTrackerScanJob: (trackerId: string) =>
    call<import("@bolsa/shared").ScanJobResponseDto>(() =>
      client.POST("/api/trackers/{tracker_id}/scan-jobs", {
        params: { path: { tracker_id: trackerId } },
      }),
    ),

  evaluateTrackerSchedules: (options?: {
    trackerId?: string;
    force?: boolean;
  }) =>
    call<import("@bolsa/shared").EvaluateTrackerSchedulesResponseDto>(() =>
      client.POST("/api/trackers/schedules/evaluate", {
        params: { query: options },
      }),
    ),

  getExecutionPolicies: (enabledOnly = false) =>
    call<import("@bolsa/shared").ExecutionPoliciesListResponseDto>(() =>
      client.GET("/api/execution-policies", {
        params: enabledOnly ? { query: { enabled_only: true } } : undefined,
      }),
    ),

  getExecutionPolicy: (id: string) =>
    call<import("@bolsa/shared").ExecutionPolicyResponseDto>(() =>
      client.GET("/api/execution-policies/{policy_id}", {
        params: { path: { policy_id: id } },
      }),
    ),

  createExecutionPolicy: (
    body: import("@bolsa/shared").CreateExecutionPolicyDto,
  ) =>
    call<import("@bolsa/shared").ExecutionPolicyResponseDto>(() =>
      client.POST("/api/execution-policies", { body: apiBody(body) }),
    ),

  updateExecutionPolicy: (
    id: string,
    body: import("@bolsa/shared").UpdateExecutionPolicyDto,
  ) =>
    call<import("@bolsa/shared").ExecutionPolicyResponseDto>(() =>
      client.PATCH("/api/execution-policies/{policy_id}", {
        params: { path: { policy_id: id } },
        body,
      }),
    ),

  deleteExecutionPolicy: (id: string) =>
    call<void>(() =>
      client.DELETE("/api/execution-policies/{policy_id}", {
        params: { path: { policy_id: id } },
      }),
    ),

  routeSignalsThroughPolicy: (
    policyId: string,
    body: import("@bolsa/shared").RouteSignalsRequestDto,
  ) =>
    call<import("@bolsa/shared").RouteSignalsResponseDto>(() =>
      client.POST("/api/execution-policies/{policy_id}/route", {
        params: { path: { policy_id: policyId } },
        body: apiBody(body),
      }),
    ),

  executeScanJobHits: (
    jobId: string,
    body: import("@bolsa/shared").ExecuteScanJobRequestDto,
  ) =>
    call<import("@bolsa/shared").RouteSignalsResponseDto>(() =>
      client.POST("/api/scans/jobs/{job_id}/execute", {
        params: { path: { job_id: jobId } },
        body,
      }),
    ),

  getPositionPolicies: (accountId?: string) =>
    call<import("@bolsa/shared").PositionPoliciesListResponseDto>(() =>
      client.GET("/api/position-policies", {
        params: accountId ? { query: { accountId } } : undefined,
      }),
    ),

  lookupPositionPolicy: (accountId: string, instrumentId: string) =>
    call<import("@bolsa/shared").PositionPolicyResponseDto>(() =>
      client.GET("/api/position-policies/lookup", {
        params: { query: { accountId, instrumentId } },
      }),
    ),

  createPositionPolicy: (
    body: import("@bolsa/shared").CreatePositionPolicyDto,
  ) =>
    call<import("@bolsa/shared").PositionPolicyResponseDto>(() =>
      client.POST("/api/position-policies", { body: apiBody(body) }),
    ),

  updatePositionPolicy: (
    id: string,
    body: import("@bolsa/shared").UpdatePositionPolicyDto,
  ) =>
    call<import("@bolsa/shared").PositionPolicyResponseDto>(() =>
      client.PATCH("/api/position-policies/{policy_id}", {
        params: { path: { policy_id: id } },
        body,
      }),
    ),

  deletePositionPolicy: (id: string) =>
    call<void>(() =>
      client.DELETE("/api/position-policies/{policy_id}", {
        params: { path: { policy_id: id } },
      }),
    ),

  evaluatePositionExits: (
    accountId: string,
    options?: { executeTrades?: boolean; timeframe?: "1d" | "1wk" },
  ) =>
    call<import("@bolsa/shared").EvaluatePositionExitsResponseDto>(() =>
      client.POST("/api/position-policies/evaluate-exits", {
        params: { query: { accountId, ...(options ?? {}) } },
      }),
    ),

  getPlatformEvents: (
    options?: import("@bolsa/shared").ListPlatformEventsQuery,
  ) =>
    call<import("@bolsa/shared").PlatformEventsListResponseDto>(() =>
      client.GET("/api/platform-events", { params: { query: options } }),
    ),

  deployStrategyPaperAccount: (
    strategyId: string,
    body: import("@bolsa/shared").DeployPaperAccountRequestDto = {},
  ) =>
    call<import("@bolsa/shared").DeployPaperAccountResponseDto>(() =>
      client.POST("/api/strategies/{strategy_id}/paper-account", {
        params: { path: { strategy_id: strategyId } },
        body,
      }),
    ),

  deployBacktestPaperAccount: (
    runId: string,
    body: import("@bolsa/shared").DeployPaperAccountRequestDto = {},
  ) =>
    call<import("@bolsa/shared").DeployPaperAccountResponseDto>(() =>
      client.POST("/api/backtests/{run_id}/deploy-paper", {
        params: { path: { run_id: runId } },
        body,
      }),
    ),

  searchMarketIndices: (q: string, limit = 12) =>
    call<{ data: import("@bolsa/shared").MarketIndexHitDto[] }>(() =>
      client.GET("/api/market-indices/search", {
        params: { query: { q, limit } },
      }),
    ),

  getMarketIndexCatalog: () =>
    call<{ data: import("@bolsa/shared").CatalogIndexEntryDto[] }>(() =>
      client.GET("/api/market-indices/catalog"),
    ),

  getMarketIndexConstituents: (indexKey: string) =>
    call<{ data: import("@bolsa/shared").IndexConstituentsDto }>(() =>
      client.GET("/api/market-indices/{index_key}/constituents", {
        params: { path: { index_key: indexKey } },
      }),
    ),

  subscribeMarketIndex: (body: {
    indexKey: string;
    syncBars?: boolean;
    yearsBack?: number;
  }) =>
    call<{ data: import("@bolsa/shared").SubscribeMarketIndexResultDto }>(() =>
      client.POST("/api/market-indices/subscribe", { body: apiBody(body) }),
    ),

  enqueueIndexSubscribeJob: (body: {
    indexKey: string;
    syncBars?: boolean;
    yearsBack?: number;
  }) =>
    call<{ data: import("@bolsa/shared").IndexSubscribeJobDto }>(() =>
      client.POST("/api/market-indices/subscribe/jobs", {
        body: apiBody(body),
      }),
    ),

  getIndexSubscribeJob: (jobId: string) =>
    call<{ data: import("@bolsa/shared").IndexSubscribeJobDto }>(() =>
      client.GET("/api/market-indices/subscribe/jobs/{job_id}", {
        params: { path: { job_id: jobId } },
      }),
    ),

  getLists: () =>
    call<{ data: import("@bolsa/shared").InstrumentListSummaryDto[] }>(() =>
      client.GET("/api/lists"),
    ),

  /** Batch listId → instrumentIds (evita N× getList en el shell). */
  getListMemberships: () =>
    call<{ data: Record<string, string[]> }>(() =>
      client.GET("/api/lists/memberships"),
    ),

  getList: (id: string) =>
    call<{ data: import("@bolsa/shared").InstrumentListDetailDto }>(() =>
      client.GET("/api/lists/{list_id}", { params: { path: { list_id: id } } }),
    ),

  getListQuotes: (id: string) =>
    call<{ data: import("@bolsa/shared").InstrumentWithMetaDto[] }>(() =>
      client.GET("/api/lists/{list_id}/quotes", {
        params: { path: { list_id: id } },
      }),
    ),

  getListTrackers: (listId: string) =>
    call<{ data: import("@bolsa/shared").TrackerDefinitionDetailDto[] }>(() =>
      client.GET("/api/lists/{list_id}/trackers", {
        params: { path: { list_id: listId } },
      }),
    ),

  createList: (body: {
    name: string;
    instrumentIds?: string[];
    source?: string;
    kind?: string;
  }) =>
    call<{ data: import("@bolsa/shared").InstrumentListDetailDto }>(() =>
      client.POST("/api/lists", { body: apiBody(body) }),
    ),

  updateList: (id: string, body: { name?: string; instrumentIds?: string[] }) =>
    call<{ data: import("@bolsa/shared").InstrumentListDetailDto }>(() =>
      client.PATCH("/api/lists/{list_id}", {
        params: { path: { list_id: id } },
        body,
      }),
    ),

  deleteList: (id: string) =>
    call<void>(() =>
      client.DELETE("/api/lists/{list_id}", {
        params: { path: { list_id: id } },
      }),
    ),

  getAlerts: (activeOnly = false) =>
    call<{ data: import("@bolsa/shared").PriceAlertDto[] }>(() =>
      client.GET("/api/alerts", {
        params: activeOnly ? { query: { activeOnly: true } } : undefined,
      }),
    ),

  createAlert: (body: {
    instrumentId: string;
    condition: import("@bolsa/shared").AlertCondition;
    priceSource?: import("@bolsa/shared").AlertPriceSource;
    targetPrice: number;
    note?: string;
  }) =>
    call<{ data: import("@bolsa/shared").PriceAlertDto }>(() =>
      client.POST("/api/alerts", { body: apiBody(body) }),
    ),

  deleteAlert: (id: string) =>
    call<void>(() =>
      client.DELETE("/api/alerts/{alert_id}", {
        params: { path: { alert_id: id } },
      }),
    ),

  reactivateAlert: (id: string) =>
    call<{ data: import("@bolsa/shared").PriceAlertDto }>(() =>
      client.POST("/api/alerts/{alert_id}/reactivate", {
        params: { path: { alert_id: id } },
      }),
    ),

  evaluateAlerts: () =>
    call<{ data: import("@bolsa/shared").PriceAlertDto[] }>(() =>
      client.POST("/api/alerts/evaluate"),
    ),

  getSignalAlerts: (activeOnly = false) =>
    call<import("@bolsa/shared").SignalAlertSubscriptionsResponseDto>(() =>
      client.GET("/api/signal-alerts", {
        params: activeOnly ? { query: { activeOnly: true } } : undefined,
      }),
    ),

  createSignalAlert: (
    body: import("@bolsa/shared").CreateSignalAlertSubscriptionRequestDto,
  ) =>
    call<import("@bolsa/shared").SignalAlertSubscriptionResponseDto>(() =>
      client.POST("/api/signal-alerts", { body: apiBody(body) }),
    ),

  deleteSignalAlert: (id: string) =>
    call<void>(() =>
      client.DELETE("/api/signal-alerts/{subscription_id}", {
        params: { path: { subscription_id: id } },
      }),
    ),

  resetSignalAlertDedupe: (id: string) =>
    call<import("@bolsa/shared").SignalAlertSubscriptionResponseDto>(() =>
      client.POST("/api/signal-alerts/{subscription_id}/reset-dedupe", {
        params: { path: { subscription_id: id } },
      }),
    ),

  evaluateSignalAlerts: () =>
    call<import("@bolsa/shared").EvaluateSignalAlertsResponseDto>(() =>
      client.POST("/api/signal-alerts/evaluate"),
    ),

  getWorkspaces: () =>
    call<{ data: import("@bolsa/shared").WorkspaceSummaryDto[] }>(() =>
      client.GET("/api/workspaces"),
    ),

  getDefaultWorkspace: () =>
    call<{ data: WorkspaceDetailApi }>(() =>
      client.GET("/api/workspaces/default"),
    ),

  getWorkspace: (id: string) =>
    call<{ data: WorkspaceDetailApi }>(() =>
      client.GET("/api/workspaces/{workspace_id}", {
        params: { path: { workspace_id: id } },
      }),
    ),

  createWorkspace: (body: {
    name: string;
    document?: import("@bolsa/shared").WorkspaceDocument;
    dockLayout?: import("@bolsa/shared").TradingDockLayoutPrefs;
    isDefault?: boolean;
  }) =>
    call<{ data: WorkspaceDetailApi }>(() =>
      client.POST("/api/workspaces", { body: apiBody(body) }),
    ),

  updateWorkspace: (
    id: string,
    body: {
      name?: string;
      document?: import("@bolsa/shared").WorkspaceDocument;
      dockLayout?: import("@bolsa/shared").TradingDockLayoutPrefs;
      isDefault?: boolean;
    },
  ) =>
    call<{ data: WorkspaceDetailApi }>(() =>
      client.PUT("/api/workspaces/{workspace_id}", {
        params: { path: { workspace_id: id } },
        body: apiBody(body),
      }),
    ),

  deleteWorkspace: (id: string) =>
    call<void>(() =>
      client.DELETE("/api/workspaces/{workspace_id}", {
        params: { path: { workspace_id: id } },
      }),
    ),

  /** PUT con keepalive para guardar al cerrar pestaña / apagar PC. */
  updateWorkspaceKeepalive: (
    id: string,
    body: {
      name?: string;
      document?: import("@bolsa/shared").WorkspaceDocument;
      dockLayout?: import("@bolsa/shared").TradingDockLayoutPrefs;
      isDefault?: boolean;
    },
  ) => {
    void fetch(`${API_URL}/api/workspaces/${id}`, {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
      },
      credentials: "include",
      body: JSON.stringify(body),
      keepalive: true,
    });
  },

  getSyncSettings: () =>
    call<{ data: import("@bolsa/shared").SyncSettingsDto }>(() =>
      client.GET("/api/sync/settings"),
    ),

  updateSyncSettings: (
    body: Partial<import("@bolsa/shared").SyncSettingsDto>,
  ) =>
    call<{ data: import("@bolsa/shared").SyncSettingsDto }>(() =>
      client.PATCH("/api/sync/settings", { body: apiBody(body) }),
    ),

  getSyncQueue: () =>
    call<{ data: import("@bolsa/shared").SyncQueueItemDto[] }>(() =>
      client.GET("/api/sync/queue"),
    ),

  enqueueStaleInstruments: () =>
    call<{ data: { scanned: number; enqueued: number } }>(() =>
      client.POST("/api/sync/queue/enqueue-stale"),
    ),

  getPendingOrders: () =>
    call<{ data: import("@bolsa/shared").PendingOrderDto[] }>(() =>
      client.GET("/api/pending-orders"),
    ),

  createPendingOrder: (body: {
    instrumentId: string;
    symbol: string;
    side: "buy" | "sell";
    orderType?: string;
    quantity: number;
    limitPrice: number;
    expiryAt?: string | null;
  }) =>
    call<{ data: import("@bolsa/shared").PendingOrderDto[] }>(() =>
      client.POST("/api/pending-orders", { body: apiBody(body) }),
    ),

  deletePendingOrder: (id: string) =>
    call<void>(() =>
      client.DELETE("/api/pending-orders/{order_id}", {
        params: { path: { order_id: id } },
      }),
    ),

  fillPendingOrder: async (
    orderId: string,
    body: { idempotencyKey: string },
  ) => {
    const accountId = getActiveAccountId();
    const response = await fetch(
      `${API_URL}/api/pending-orders/${orderId}/fill`,
      {
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
          ...(accountId ? { "X-Account-Id": accountId } : {}),
        },
        body: JSON.stringify(body),
      },
    );
    if (!response.ok) {
      let detail: unknown;
      try {
        detail = await response.json();
      } catch {
        detail = undefined;
      }
      throw new ApiError(
        formatApiErrorDetail(detail) ?? response.statusText,
        response.status,
      );
    }
    return (await response.json()) as {
      status: string;
      reason: string | null;
      transactionId: string | null;
    };
  },
};

type WorkspaceDetailApi = {
  id: string;
  name: string;
  isDefault: boolean;
  document: import("@bolsa/shared").WorkspaceDocument;
  dockLayout: import("@bolsa/shared").TradingDockLayoutPrefs | null;
  createdAt: string;
  updatedAt: string;
};
