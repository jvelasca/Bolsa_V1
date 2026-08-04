/**
 * Cliente HTTP del frontend hacia la API FastAPI (VITE_API_URL, default :8000).
 *
 * Punto único de integración web ↔ backend. Añade Authorization Bearer si hay
 * token en auth-store. Lanza ApiError en respuestas no OK.
 *
 * @see docs/API_REFERENCE.md — mapa de endpoints
 * @see packages/shared/src/types.ts — DTOs TypeScript (manual, no OpenAPI gen)
 */
import { getAuthToken } from '@/stores/auth-store';
import { getActiveAccountId } from '@/stores/active-account-store';
import { resolveApiBaseUrl } from '@/lib/api-base-url';

const API_URL = resolveApiBaseUrl();

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

function formatApiErrorDetail(body: unknown): string | undefined {
  if (!body || typeof body !== 'object') {
    return typeof body === 'string' ? body : undefined;
  }
  const record = body as Record<string, unknown>;
  if (typeof record.error === 'string') return record.error;
  if (typeof record.detail === 'string') return record.detail;
  if (Array.isArray(record.detail)) {
    return record.detail
      .map((item) => {
        if (typeof item === 'string') return item;
        if (item && typeof item === 'object' && 'msg' in item) {
          const loc = 'loc' in item && Array.isArray(item.loc) ? item.loc.join('.') : '';
          const msg = String((item as { msg: unknown }).msg);
          return loc ? `${loc}: ${msg}` : msg;
        }
        return JSON.stringify(item);
      })
      .join('; ');
  }
  if (
    record.data &&
    typeof record.data === 'object' &&
    record.data !== null &&
    'error' in record.data &&
    typeof (record.data as { error: unknown }).error === 'string'
  ) {
    return (record.data as { error: string }).error;
  }
  return undefined;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getAuthToken();
  const accountId = getActiveAccountId();
  const { headers: initHeaders, ...restInit } = init ?? {};
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      ...restInit,
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(accountId ? { 'X-Account-Id': accountId } : {}),
        ...initHeaders,
      },
    });
  } catch (error) {
    if (error instanceof TypeError) {
      throw new ApiError(
        'No se pudo contactar con la API. Comprueba que el backend esté en marcha (puerto 8000 o lanzador «Bolsa: API Python + Web»).',
        0,
      );
    }
    throw error;
  }

  if (response.status === 401) {
    throw new ApiError('Sesión expirada o no autorizada', 401);
  }

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new ApiError(
      formatApiErrorDetail(body) ?? response.statusText,
      response.status,
    );
  }

  if (response.status === 204) {
    return undefined as T;
  }

  const text = await response.text();
  if (!text) {
    return undefined as T;
  }

  return JSON.parse(text) as T;
}

export const api = {
  getHealth: () =>
    request<{
      status: string;
      service: string;
      timestamp: string;
      database?: { status: string; message: string };
      components?: Record<
        string,
        { status: string; message: string; details?: Record<string, unknown> }
      >;
    }>('/api/health'),

  getRiskKillSwitch: () =>
    request<{
      effective: boolean;
      env: boolean;
      runtimeMemory: boolean;
      redis: boolean | null;
      paperDExecuteEnv: boolean;
    }>('/api/risk/kill-switch'),

  setRiskKillSwitch: (enabled: boolean) =>
    request<{
      effective: boolean;
      env: boolean;
      runtimeMemory: boolean;
      redis: boolean | null;
      paperDExecuteEnv: boolean;
      updated?: { enabled: boolean; memory: boolean; redis: boolean };
    }>('/api/risk/kill-switch', {
      method: 'POST',
      body: JSON.stringify({ enabled }),
    }),

  getAiStatus: () =>
    request<{
      data: {
        preferredProvider: string;
        ollamaAvailable: boolean;
        openaiAvailable: boolean;
        callsRecorded: number;
        mode: string;
        auditSink: string;
        producerVersion: string;
      };
    }>('/api/ai/status'),

  /** Coach profundo de batería (AT + perfil/TF). LLM vía proxy; heuristic si no hay provider.
   * mode=adversary → auditor C (solo findings tipados). */
  analyzeBacktestCoach: (
    body: {
      context: string;
      battery: string;
      localSummary?: string;
      facts?: Record<string, unknown> | null;
      mode?: 'narrate' | 'adversary';
    },
    init?: { signal?: AbortSignal },
  ) =>
    request<{
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
    }>('/api/ai/backtest-coach/analyze', {
      method: 'POST',
      body: JSON.stringify(body),
      signal: init?.signal,
    }),

  /** F1b — copiloto FA (Ollama o heurística). Solo interpreta el card; no recalcula. */
  explainInstrumentFundamentals: (instrumentId: string) =>
    request<{ data: import('@bolsa/shared').FundamentalExplainResponseV1 }>(
      '/api/ai/fundamentals/explain',
      {
        method: 'POST',
        body: JSON.stringify({ instrumentId }),
      },
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
    request<{
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
    }>('/api/ai/dia-d/session-evidence', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

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
    request<{
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
    }>('/api/ai/core-r/review-evidence', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  /** F2b lite — lista filings locales (disco; no Score_FUND). */
  listInstrumentFilings: (instrumentId: string) =>
    request<import('@bolsa/shared').InstrumentFilingListResponseV1>(
      `/api/instruments/${instrumentId}/filings`,
    ),

  uploadInstrumentFiling: async (
    instrumentId: string,
    file: File,
    kind: import('@bolsa/shared').InstrumentFilingKindV1 = '10-K',
  ) => {
    const token = getAuthToken();
    const accountId = getActiveAccountId();
    const body = new FormData();
    body.append('file', file);
    body.append('kind', kind);
    const response = await fetch(`${API_URL}/api/instruments/${instrumentId}/filings`, {
      method: 'POST',
      headers: {
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(accountId ? { 'X-Account-Id': accountId } : {}),
      },
      body,
    });
    if (!response.ok) {
      let detail: unknown;
      try {
        detail = await response.json();
      } catch {
        detail = undefined;
      }
      throw new ApiError(formatApiErrorDetail(detail) ?? response.statusText, response.status);
    }
    return (await response.json()) as import('@bolsa/shared').InstrumentFilingUploadResponseV1;
  },

  deleteInstrumentFiling: (instrumentId: string, filingId: string) =>
    request<{ ok: boolean }>(`/api/instruments/${instrumentId}/filings/${filingId}`, {
      method: 'DELETE',
    }),

  /** F2b+ — último 10-K/10-Q desde SEC EDGAR (solo tickers US). */
  fetchInstrumentFilingFromSec: (
    instrumentId: string,
    kind: '10-K' | '10-Q' = '10-K',
  ) =>
    request<import('@bolsa/shared').InstrumentFilingUploadResponseV1>(
      `/api/instruments/${instrumentId}/filings/sec-fetch?kind=${encodeURIComponent(kind)}`,
      { method: 'POST' },
    ),

  summarizeInstrumentFiling: (instrumentId: string, filingId: string) =>
    request<{ data: import('@bolsa/shared').InstrumentFilingSummarizeResponseV1 }>(
      '/api/ai/fundamentals/filings/summarize',
      {
        method: 'POST',
        body: JSON.stringify({ instrumentId, filingId }),
      },
    ),

  /** F2b++ — Q&A con retrieval TF-IDF local (sin vectores). */
  askInstrumentFiling: (instrumentId: string, filingId: string, question: string) =>
    request<{ data: import('@bolsa/shared').InstrumentFilingAskResponseV1 }>(
      '/api/ai/fundamentals/filings/ask',
      {
        method: 'POST',
        body: JSON.stringify({ instrumentId, filingId, question }),
      },
    ),

  /** RFC-008 D7 — resumen Efectividad (demo=true = ilustrativo hasta PG Trials/Memory). */
  getAiEffectiveness: (demo = false) =>
    request<{
      data: import('@bolsa/shared').EffectivenessSummaryV1;
    }>(`/api/ai/effectiveness${demo ? '?demo=true' : ''}`),

  getFeatureCatalog: () =>
    request<{
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
    }>('/api/features/catalog'),

  listPredictions: (params?: {
    instrumentId?: string;
    modelId?: string;
    limit?: number;
  }) => {
    const q = new URLSearchParams();
    if (params?.instrumentId) q.set('instrumentId', params.instrumentId);
    if (params?.modelId) q.set('modelId', params.modelId);
    if (params?.limit != null) q.set('limit', String(params.limit));
    const qs = q.toString();
    return request<{ data: import('@bolsa/shared').PredictionV1[] }>(
      `/api/predictions${qs ? `?${qs}` : ''}`,
    );
  },

  listPredictionModels: () =>
    request<{
      data: {
        models: import('@bolsa/shared').ModelArtifactV1[];
        lightgbmAvailable: boolean;
        defaultModelId: string;
        persistence?: string;
      };
    }>('/api/predictions/models'),

  predict: (body: {
    instrumentId: string;
    modelId?: string;
    timeframe?: string;
    barLimit?: number;
    horizon?: string;
  }) =>
    request<{ data: import('@bolsa/shared').PredictionV1 }>('/api/predictions/predict', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  trainPredictionModel: (body: {
    instrumentId: string;
    timeframe?: string;
    barLimit?: number;
  }) =>
    request<{ data: import('@bolsa/shared').ModelArtifactV1 }>('/api/predictions/models/train', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  getInstruments: () =>
    request<{ data: import('@bolsa/shared').InstrumentWithMetaDto[] }>('/api/instruments'),

  getInstrumentQuotes: (ids: string[]) =>
    request<{ data: import('@bolsa/shared').InstrumentWithMetaDto[] }>('/api/instruments/quotes', {
      method: 'POST',
      body: JSON.stringify({ ids }),
    }),

  getInstrumentProfile: (id: string) =>
    request<{ data: import('@bolsa/shared').InstrumentProfileDto | null }>(
      `/api/instruments/${id}/profile`,
    ),

  getInstrumentFundamentals: (id: string, opts?: { asOf?: string }) => {
    const qs = new URLSearchParams();
    if (opts?.asOf) qs.set('asOf', opts.asOf);
    const suffix = qs.toString() ? `?${qs}` : '';
    return request<{ data: import('@bolsa/shared').FundamentalCardDto }>(
      `/api/instruments/${id}/fundamentals${suffix}`,
    );
  },

  /** F3 — Composite Investment Score (Monitor). */
  getInstrumentComposite: (
    id: string,
    opts?: { horizon?: string; regime?: string; asOf?: string },
  ) => {
    const qs = new URLSearchParams();
    if (opts?.horizon) qs.set('horizon', opts.horizon);
    if (opts?.regime) qs.set('regime', opts.regime);
    if (opts?.asOf) qs.set('asOf', opts.asOf);
    const suffix = qs.toString() ? `?${qs}` : '';
    return request<{ data: import('@bolsa/shared').CompositeCardDto }>(
      `/api/instruments/${id}/composite${suffix}`,
    );
  },

  /** F4 — Screener FA (universo × gate; sin TA). */
  runFundamentalScreener: (body: import('@bolsa/shared').FundamentalScreenerRunRequestV1) =>
    request<{ data: import('@bolsa/shared').FundamentalScreenerRunResultV1 }>(
      '/api/instruments/fundamentals/screener',
      {
        method: 'POST',
        body: JSON.stringify(body),
      },
    ),

  /** Paper D — propose + execute opcional (Composite × universo). */
  proposePaperD: (body: import('@bolsa/shared').PaperDProposeRequestV1) =>
    request<{ data: import('@bolsa/shared').PaperDProposeResultV1 }>('/api/paper-d/propose', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  /** Pipeline semanal FA → whitelist → Paper D. */
  runFaWeeklyPipeline: (body: import('@bolsa/shared').FaWeeklyPipelineRequestV1) =>
    request<{ data: import('@bolsa/shared').FaWeeklyPipelineResultV1 }>(
      '/api/paper-d/weekly-run',
      {
        method: 'POST',
        body: JSON.stringify(body),
      },
    ),

  queryInstrumentFundamentals: (body: { instrumentIds: string[] }) =>
    request<{ data: import('@bolsa/shared').FundamentalChipDto[] }>(
      '/api/instruments/fundamentals/query',
      {
        method: 'POST',
        body: JSON.stringify(body),
      },
    ),

  /** Batch Composite chips (hub Instrumentos I2). Cap 40 ids/request. */
  queryInstrumentComposite: (body: {
    instrumentIds: string[];
    horizon?: string;
    regime?: string;
  }) =>
    request<{ data: import('@bolsa/shared').CompositeChipDto[] }>(
      '/api/instruments/composite/query',
      {
        method: 'POST',
        body: JSON.stringify(body),
      },
    ),

  getInstrumentDbInventory: (id: string) =>
    request<{ data: import('@bolsa/shared').InstrumentDbInventoryDto }>(
      `/api/instruments/${id}/db-inventory`,
    ),

  validateInstrumentXtb: (id: string) =>
    request<{ data: import('@bolsa/shared').InstrumentXtbValidationDto }>(
      `/api/instruments/${id}/validate-xtb`,
      { method: 'POST' },
    ),

  searchInstruments: (q: string) =>
    request<import('@bolsa/shared').InstrumentSearchResponseDto>(
      `/api/instruments/search?q=${encodeURIComponent(q)}`,
    ),

  computeIndicators: (body: import('@bolsa/shared').ComputeIndicatorsRequestDto) =>
    request<import('@bolsa/shared').ComputeIndicatorsResponseDto>('/api/indicators/compute', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  replayDrawings: (body: import('@bolsa/shared').DrawingReplayRequestDto) =>
    request<import('@bolsa/shared').DrawingReplayResponseDto>('/api/drawings/replay', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  evaluateSignals: (body: import('@bolsa/shared').EvaluateSignalsRequestDto) =>
    request<import('@bolsa/shared').EvaluateSignalsResponseDto>('/api/signals/evaluate', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  runScan: (body: import('@bolsa/shared').ScanRunRequestDto) =>
    request<import('@bolsa/shared').ScanRunResponseDto>('/api/scans/run', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  enqueueScanJob: (body: import('@bolsa/shared').ScanRunRequestDto) =>
    request<import('@bolsa/shared').ScanJobResponseDto>('/api/scans/jobs', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  getScanJob: (jobId: string) =>
    request<import('@bolsa/shared').ScanJobResponseDto>(`/api/scans/jobs/${jobId}`),

  getScanManifest: (scanId: string) =>
    request<import('@bolsa/shared').ScanManifestResponseDto>(`/api/scans/manifests/${scanId}`),

  getScanJobs: () =>
    request<import('@bolsa/shared').ScanJobsListResponseDto>('/api/scans/jobs'),

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
    request<import('@bolsa/shared').ImportInstrumentResponseDto>('/api/instruments/import', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  getInstrument: (id: string) =>
    request<{
      data: import('@bolsa/shared').InstrumentDto;
      meta: {
        lastSync: {
          status: string;
          barsAdded: number;
          syncedAt: string;
          error: string | null;
        } | null;
        priceSummary: import('@bolsa/shared').PriceSummaryDto | null;
      };
    }>(`/api/instruments/${id}`),

  getOhlcv: (id: string, limit = 365, timeframe = '1d') =>
    request<{
      data: import('@bolsa/shared').OhlcvBarDto[];
      meta: { timeframe: string; count: number };
    }>(`/api/instruments/${id}/ohlcv?limit=${limit}&timeframe=${encodeURIComponent(timeframe)}`),

  getIndicators: (id: string, limit = 365, timeframe = '1d') =>
    request<{
      data: import('@bolsa/shared').IndicatorPointDto[];
      meta: {
        signals: {
          rsiZone: 'overbought' | 'oversold' | 'neutral';
          smaCross: 'bullish' | 'bearish' | null;
        };
      };
    }>(`/api/instruments/${id}/indicators?limit=${limit}&timeframe=${encodeURIComponent(timeframe)}`),

  getLiveQuote: (id: string) =>
    request<{ data: import('@bolsa/shared').InstrumentLiveQuoteDto }>(
      `/api/instruments/${id}/live-quote`,
    ),

  getInstrumentLiveQuotes: (ids: string[]) =>
    request<{ data: import('@bolsa/shared').InstrumentLiveQuoteDto[] }>(
      '/api/instruments/live-quotes',
      { method: 'POST', body: JSON.stringify({ ids }) },
    ),

  getDataStatus: (id: string, timeframe = '1d') =>
    request<{ data: import('@bolsa/shared').InstrumentDataStatusDto }>(
      `/api/instruments/${id}/data-status?timeframe=${encodeURIComponent(timeframe)}`,
    ),

  getDatabaseSummary: (instrumentId?: string) => {
    const query = instrumentId
      ? `?instrumentId=${encodeURIComponent(instrumentId)}`
      : '';
    return request<{ data: import('@bolsa/shared').DatabaseSummaryDto }>(
      `/api/database/summary${query}`,
    );
  },

  getOrphanInstruments: (limit = 100) =>
    request<{ data: import('@bolsa/shared').OrphanInstrumentsDto }>(
      `/api/database/orphans?limit=${limit}`,
    ),

  purgeOrphanInstruments: (limit = 50) =>
    request<{ data: import('@bolsa/shared').PurgeOrphansResultDto }>(
      '/api/database/orphans/purge',
      { method: 'POST', body: JSON.stringify({ limit }) },
    ),

  getClosedSimulatedAccounts: (limit = 100) =>
    request<{ data: import('@bolsa/shared').ClosedSimulatedAccountsDto }>(
      `/api/database/closed-accounts?limit=${limit}`,
    ),

  purgeClosedSimulatedAccounts: (limit = 50) =>
    request<{ data: import('@bolsa/shared').PurgeClosedAccountsResultDto }>(
      '/api/database/closed-accounts/purge',
      { method: 'POST', body: JSON.stringify({ limit }) },
    ),

  getInstrumentRemovalPreview: (id: string, excludingListId?: string) => {
    const query = excludingListId
      ? `?excludingListId=${encodeURIComponent(excludingListId)}`
      : '';
    return request<{ data: import('@bolsa/shared').InstrumentRemovalPreviewDto }>(
      `/api/instruments/${id}/removal-preview${query}`,
    );
  },

  removeInstrumentFromList: (
    listId: string,
    instrumentId: string,
    body?: { purgeIfOrphan?: boolean },
  ) =>
    request<{ data: import('@bolsa/shared').RemoveInstrumentFromListResultDto }>(
      `/api/lists/${listId}/instruments/${instrumentId}/remove`,
      { method: 'POST', body: JSON.stringify(body ?? {}) },
    ),

  deleteInstrument: (id: string, force = false) =>
    request<void>(
      `/api/instruments/${id}${force ? '?force=true' : ''}`,
      { method: 'DELETE' },
    ),

  getMarketProviders: () =>
    request<{ data: import('@bolsa/shared').MarketProviderStatusDto[] }>(
      '/api/market/providers',
    ),

  getFxRate: (from: string, to: string) =>
    request<{ data: import('@bolsa/shared').FxRateDto }>(
      `/api/market/fx?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`,
    ),

  syncInstrument: async (id: string, yearsBack = 5) => {
    const result = await request<{
      data: {
        barsAdded: number;
        status: string;
        error?: string | null;
        barsInserted?: number;
        barsUpdated?: number;
        barsSkipped?: number;
        consolidationNotes?: string[];
      };
    }>(`/api/instruments/${id}/sync`, {
      method: 'POST',
      body: JSON.stringify({ yearsBack }),
    });

    if (result.data.status === 'failed') {
      throw new ApiError(result.data.error ?? 'Error de sincronización', 502);
    }

    return result;
  },

  getPortfolio: () =>
    request<{ data: import('@bolsa/shared').PortfolioSummaryDto }>('/api/portfolio'),

  updateAccount: (accountId: string, body: import('@bolsa/shared').UpdateInvestmentAccountRequestDto) =>
    request<{ data: import('@bolsa/shared').InvestmentAccountDto }>(`/api/accounts/${accountId}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
      headers: { 'X-Account-Id': accountId },
    }),

  setDefaultAccount: (accountId: string) =>
    request<{ data: import('@bolsa/shared').InvestmentAccountDto }>(
      `/api/accounts/${accountId}/make-default`,
      { method: 'POST', headers: { 'X-Account-Id': accountId } },
    ),

  closeAccount: (accountId: string) =>
    request<{ data: import('@bolsa/shared').InvestmentAccountDto }>(
      `/api/accounts/${accountId}/close`,
      { method: 'POST', headers: { 'X-Account-Id': accountId } },
    ),

  deleteAccount: (accountId: string) =>
    request<void>(`/api/accounts/${accountId}`, {
      method: 'DELETE',
      headers: { 'X-Account-Id': accountId },
    }),

  getAccounts: (type?: import('@bolsa/shared').InvestmentAccountType) =>
    request<{ data: import('@bolsa/shared').InvestmentAccountDto[] }>(
      type ? `/api/accounts?type=${encodeURIComponent(type)}` : '/api/accounts',
    ),

  createAccount: (body: import('@bolsa/shared').CreateInvestmentAccountRequestDto) =>
    request<{ data: import('@bolsa/shared').InvestmentAccountDto }>('/api/accounts', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  updateAccountSettings: (accountId: string, settings: import('@bolsa/shared').AccountSettings) =>
    request<{ data: import('@bolsa/shared').InvestmentAccountDto }>(
      `/api/accounts/${accountId}/settings`,
      {
        method: 'PATCH',
        body: JSON.stringify({ settings }),
      },
    ),

  listInvestorProfiles: () =>
    request<{ data: import('@bolsa/shared').InvestorProfileV1[] }>('/api/investor-profiles'),

  ensureDefaultInvestorProfiles: () =>
    request<{ data: import('@bolsa/shared').InvestorProfileV1[] }>(
      '/api/investor-profiles/ensure-defaults',
      { method: 'POST' },
    ),

  getInvestorProfile: (profileId: string) =>
    request<{ data: import('@bolsa/shared').InvestorProfileV1 }>(
      `/api/investor-profiles/${profileId}`,
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
    request<{ data: import('@bolsa/shared').InvestorProfileV1 }>('/api/investor-profiles', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  updateInvestorProfile: (
    profileId: string,
    body: Record<string, unknown>,
  ) =>
    request<{ data: import('@bolsa/shared').InvestorProfileV1 }>(
      `/api/investor-profiles/${profileId}`,
      {
        method: 'PATCH',
        body: JSON.stringify(body),
      },
    ),

  deleteInvestorProfile: (profileId: string) =>
    request<{ ok: boolean }>(`/api/investor-profiles/${profileId}`, { method: 'DELETE' }),

  getInstrumentStrategyTop: (instrumentId: string, timeframe = '1d') =>
    request<{ data: import('@bolsa/shared').InstrumentStrategyTopV1 | null }>(
      `/api/instruments/${encodeURIComponent(instrumentId)}/strategy-top?timeframe=${encodeURIComponent(timeframe)}`,
    ),

  getInstrumentNarrative: (
    instrumentId: string,
    scope: import('@bolsa/shared').InstrumentNarrativeScope = 'estudio',
  ) =>
    request<{ data: import('@bolsa/shared').InstrumentNarrativeV1 | null }>(
      `/api/instruments/${encodeURIComponent(instrumentId)}/narrative?scope=${encodeURIComponent(scope)}`,
    ),

  upsertInstrumentNarrative: (
    instrumentId: string,
    body: import('@bolsa/shared').UpsertInstrumentNarrativeRequestV1,
  ) =>
    request<{ data: import('@bolsa/shared').InstrumentNarrativeV1 }>(
      `/api/instruments/${encodeURIComponent(instrumentId)}/narrative`,
      { method: 'PUT', body: JSON.stringify(body) },
    ),

  deleteInstrumentNarrative: (
    instrumentId: string,
    scope: import('@bolsa/shared').InstrumentNarrativeScope = 'estudio',
  ) =>
    request<{ data: import('@bolsa/shared').InstrumentNarrativeV1 | null }>(
      `/api/instruments/${encodeURIComponent(instrumentId)}/narrative?scope=${encodeURIComponent(scope)}`,
      { method: 'DELETE' },
    ),

  queryInstrumentDailyOpinions: (
    body: import('@bolsa/shared').QueryInstrumentDailyOpinionsRequestV1,
  ) =>
    request<{ data: import('@bolsa/shared').InstrumentDailyOpinionV1[] }>(
      '/api/instrument-daily-opinions/query',
      { method: 'POST', body: JSON.stringify(body) },
    ),

  getInstrumentDailyOpinion: (instrumentId: string, asOfBarDate?: string, forceRefresh = false) => {
    const params = new URLSearchParams();
    if (asOfBarDate) params.set('asOfBarDate', asOfBarDate);
    if (forceRefresh) params.set('forceRefresh', 'true');
    const q = params.toString();
    return request<{ data: import('@bolsa/shared').InstrumentDailyOpinionV1[] }>(
      `/api/instruments/${encodeURIComponent(instrumentId)}/daily-opinion${q ? `?${q}` : ''}`,
    );
  },

  listInstrumentDailyOpinions: (
    instrumentId: string,
    options?: { days?: number; ensureDays?: number },
  ) => {
    const params = new URLSearchParams();
    if (options?.days != null) params.set('days', String(options.days));
    if (options?.ensureDays != null) params.set('ensureDays', String(options.ensureDays));
    const q = params.toString();
    return request<{ data: import('@bolsa/shared').InstrumentDailyOpinionV1[] }>(
      `/api/instruments/${encodeURIComponent(instrumentId)}/daily-opinions${q ? `?${q}` : ''}`,
    );
  },

  runInstrumentDailyOpinionEodBatch: (body: {
    instrumentIds: string[];
    asOfBarDate?: string | null;
    accountId?: string | null;
    force?: boolean;
    notifyEmail?: string | null;
    notifyEmailEnabled?: boolean | null;
  }) =>
    request<{
      enabled: boolean;
      forced: boolean;
      count: number;
      data: import('@bolsa/shared').InstrumentDailyOpinionV1[];
      emailNotify?: {
        emailEnabled: boolean;
        alarmaCount: number;
        sent: boolean;
        skippedReason?: string | null;
      } | null;
    }>('/api/instrument-daily-opinions/eod-batch', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  getInstrumentDailyOpinionTelemetry: (opts?: {
    lookbackDays?: number;
    instrumentIds?: string[];
  }) => {
    const params = new URLSearchParams();
    if (opts?.lookbackDays != null) params.set('lookbackDays', String(opts.lookbackDays));
    for (const id of opts?.instrumentIds ?? []) {
      if (id) params.append('instrumentIds', id);
    }
    const q = params.toString();
    return request<{
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
    }>(`/api/instrument-daily-opinions/telemetry${q ? `?${q}` : ''}`);
  },

  getAccountMandates: (accountId: string, instrumentId?: string) => {
    const q = instrumentId
      ? `?instrumentId=${encodeURIComponent(instrumentId)}`
      : '';
    return request<{ data: import('@bolsa/shared').MandateBundleDto }>(
      `/api/accounts/${encodeURIComponent(accountId)}/mandates${q}`,
    );
  },

  syncAccountMandates: (
    accountId: string,
    body: import('@bolsa/shared').MandateBundleDto,
  ) =>
    request<{ data: import('@bolsa/shared').MandateBundleDto }>(
      `/api/accounts/${encodeURIComponent(accountId)}/mandates`,
      { method: 'PUT', body: JSON.stringify(body) },
    ),

  getAccountCoreR: (accountId: string) =>
    request<{ data: import('@bolsa/shared').CoreRBundleDto }>(
      `/api/accounts/${encodeURIComponent(accountId)}/core-r`,
    ),

  syncAccountCoreR: (
    accountId: string,
    body: {
      queue: Array<Record<string, unknown>>;
      reports: Record<string, unknown>;
      scheduler: Record<string, unknown>;
    },
  ) =>
    request<{ data: import('@bolsa/shared').CoreRBundleDto }>(
      `/api/accounts/${encodeURIComponent(accountId)}/core-r`,
      { method: 'PUT', body: JSON.stringify(body) },
    ),

  getAccountSupervisedF3: (accountId: string) =>
    request<{ data: import('@bolsa/shared').SupervisedF3BundleDto }>(
      `/api/accounts/${encodeURIComponent(accountId)}/supervised-f3-queue`,
    ),

  syncAccountSupervisedF3: (
    accountId: string,
    body: {
      items: Array<Record<string, unknown>>;
      activeId?: string | null;
    },
  ) =>
    request<{ data: import('@bolsa/shared').SupervisedF3BundleDto }>(
      `/api/accounts/${encodeURIComponent(accountId)}/supervised-f3-queue`,
      { method: 'PUT', body: JSON.stringify(body) },
    ),

  /** Ops: tick CORE-R servidor (informe BD + PnL DEMO). */
  runCoreRCronTick: (force = false, includePnl = true) => {
    const q = new URLSearchParams();
    if (force) q.set('force', 'true');
    if (!includePnl) q.set('include_pnl', 'false');
    const qs = q.toString();
    return request<{
      data: {
        accounts: number;
        ticked: number;
        totalAdded: number;
        results: Array<Record<string, unknown>>;
      };
    }>(`/api/core-r/cron/tick${qs ? `?${qs}` : ''}`, { method: 'POST' });
  },

  queryInstrumentStrategyTops: (body: {
    instrumentIds: string[];
    timeframe?: string;
  }) =>
    request<{ data: import('@bolsa/shared').InstrumentStrategyTopV1[] }>(
      '/api/instrument-strategy-tops/query',
      {
        method: 'POST',
        body: JSON.stringify(body),
      },
    ),

  upsertInstrumentStrategyTop: (
    instrumentId: string,
    body: import('@bolsa/shared').UpsertInstrumentStrategyTopRequestV1,
  ) =>
    request<{ data: import('@bolsa/shared').InstrumentStrategyTopV1 }>(
      `/api/instruments/${encodeURIComponent(instrumentId)}/strategy-top`,
      {
        method: 'PUT',
        body: JSON.stringify(body),
      },
    ),

  deleteInstrumentStrategyTop: (instrumentId: string, timeframe = '1d') =>
    request<{ ok: boolean }>(
      `/api/instruments/${encodeURIComponent(instrumentId)}/strategy-top?timeframe=${encodeURIComponent(timeframe)}`,
      { method: 'DELETE' },
    ),

  assignAccountProfile: (accountId: string, profileId: string | null) =>
    request<{ data: { accountId: string; activeProfileId: string | null } }>(
      `/api/accounts/${accountId}/active-profile`,
      {
        method: 'PUT',
        body: JSON.stringify({ profileId }),
      },
    ),

  getAccountActiveProfile: (accountId: string) =>
    request<{ data: import('@bolsa/shared').InvestorProfileV1 }>(
      `/api/accounts/${accountId}/active-profile`,
    ),

  refreshInvestorProfileObserved: (profileId: string, accountId?: string) =>
    request<{ data: import('@bolsa/shared').InvestorProfileV1 }>(
      `/api/investor-profiles/${profileId}/refresh-observed${
        accountId ? `?accountId=${encodeURIComponent(accountId)}` : ''
      }`,
      { method: 'POST' },
    ),

  proposeRecommendation: (body: {
    instrumentId: string;
    symbol?: string;
    accountId?: string;
    suggestedQuantity: number;
    suggestedPrice?: number | null;
    action?: 'recommend_long' | 'recommend_short' | 'wait';
    includeFundamentals?: boolean;
    includeMacro?: boolean;
    includeEvidence?: boolean;
    includeNews?: boolean;
    strategyOrSignalRef?: string;
    horizon?: 'intraday' | 'swing' | 'position' | 'long_term';
    macro?: Record<string, unknown>;
  }) =>
    request<{
      data: import('@bolsa/shared').RecommendationV1 & {
        technicalAssessment?: import('@bolsa/shared').TechnicalAssessmentV1;
        fundamentalAssessment?: import('@bolsa/shared').FundamentalAssessmentV1;
        macroAssessment?: import('@bolsa/shared').MacroAssessmentV1;
        evidenceAssessment?: import('@bolsa/shared').EvidenceAssessmentV1;
        newsAssessment?: import('@bolsa/shared').NewsAssessmentV1;
        assessments?: import('@bolsa/shared').AssessmentV1[];
        decisionPackage?: Record<string, unknown>;
        policyGate?: { status?: string; mode?: string; message?: string } | null;
        lastClose?: number | null;
        source?: string;
        decisionSession?: import('@bolsa/shared').DecisionSessionV1;
        weightContext?: import('@bolsa/shared').WeightContextV1;
        combinedScore?: number;
      };
    }>('/api/ai/recommendations/propose', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  getDecisionSession: (sessionId: string) =>
    request<{ data: import('@bolsa/shared').DecisionSessionV1 }>(
      `/api/ai/decision-sessions/${encodeURIComponent(sessionId)}`,
    ),

  getDecisionSessionReplay: (sessionId: string) =>
    request<{ data: import('@bolsa/shared').DecisionReplayV1 }>(
      `/api/ai/decision-sessions/${encodeURIComponent(sessionId)}/replay`,
    ),

  listDecisionSessions: (params?: {
    accountId?: string;
    instrumentId?: string;
    limit?: number;
  }) => {
    const q = new URLSearchParams();
    if (params?.accountId) q.set('accountId', params.accountId);
    if (params?.instrumentId) q.set('instrumentId', params.instrumentId);
    if (params?.limit != null) q.set('limit', String(params.limit));
    const qs = q.toString();
    return request<{ data: import('@bolsa/shared').DecisionSessionSummaryV1[] }>(
      `/api/ai/decision-sessions${qs ? `?${qs}` : ''}`,
    );
  },

  closeDecisionSessionOutcome: (
    sessionId: string,
    body?: {
      mode?: 'auto' | 'manual';
      verdict?: import('@bolsa/shared').SessionOutcomeVerdict;
      returnPct?: number;
      priceAtEval?: number;
      notes?: string;
      force?: boolean;
    },
  ) =>
    request<{ data: import('@bolsa/shared').DecisionSessionV1 }>(
      `/api/ai/decision-sessions/${encodeURIComponent(sessionId)}/outcome`,
      {
        method: 'POST',
        body: JSON.stringify(body ?? { mode: 'auto' }),
      },
    ),

  getDecisionSessionLearningSummary: (params?: {
    accountId?: string;
    instrumentId?: string;
    limit?: number;
  }) => {
    const q = new URLSearchParams();
    if (params?.accountId) q.set('accountId', params.accountId);
    if (params?.instrumentId) q.set('instrumentId', params.instrumentId);
    if (params?.limit != null) q.set('limit', String(params.limit));
    const qs = q.toString();
    return request<{ data: import('@bolsa/shared').SessionLearningSummaryV1 }>(
      `/api/ai/decision-sessions/learning-summary${qs ? `?${qs}` : ''}`,
    );
  },

  confirmOrderIntent: (body: {
    recommendation: import('@bolsa/shared').RecommendationV1 | Record<string, unknown>;
    accountId: string;
    execute?: boolean;
    sessionId?: string;
  }) =>
    request<{
      data: {
        intent: import('@bolsa/shared').OrderIntentV1;
        trade: { status: string; reason?: string; transactionId?: string | null } | null;
        decisionSession?: import('@bolsa/shared').DecisionSessionV1 | null;
      };
    }>('/api/ai/intents/confirm', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  getAccountSummary: (accountId: string) =>
    request<{ data: import('@bolsa/shared').AccountSummaryDto }>(
      `/api/accounts/${accountId}/summary`,
    ),

  getAccountSummaries: (type?: string) =>
    request<{ data: import('@bolsa/shared').AccountSummaryDto[] }>(
      type
        ? `/api/accounts/summaries?type=${encodeURIComponent(type)}`
        : '/api/accounts/summaries',
    ),

  getAccountLedger: (accountId: string, limit = 50, offset = 0) =>
    request<{ data: import('@bolsa/shared').LedgerEntryDto[] }>(
      `/api/accounts/${accountId}/ledger?limit=${limit}&offset=${offset}`,
    ),

  getTaxReport: (accountId: string, year?: number) =>
    request<{ data: import('@bolsa/shared').TaxReportSummaryDto }>(
      `/api/accounts/${accountId}/tax-report${year != null ? `?year=${year}` : ''}`,
    ),

  depositCash: (accountId: string, body: import('@bolsa/shared').DepositCashRequestDto) =>
    request<{ data: import('@bolsa/shared').CashMovementResultDto }>(
      `/api/accounts/${accountId}/deposits`,
      { method: 'POST', body: JSON.stringify(body), headers: { 'X-Account-Id': accountId } },
    ),

  withdrawCash: (accountId: string, body: import('@bolsa/shared').WithdrawCashRequestDto) =>
    request<{ data: import('@bolsa/shared').CashMovementResultDto }>(
      `/api/accounts/${accountId}/withdrawals`,
      { method: 'POST', body: JSON.stringify(body), headers: { 'X-Account-Id': accountId } },
    ),

  getTransactions: (limit = 50) =>
    request<{ data: import('@bolsa/shared').TransactionDto[] }>(
      `/api/portfolio/transactions?limit=${limit}`,
    ),

  executeTrade: (body: {
    instrumentId: string;
    type: 'buy' | 'sell';
    quantity: number;
    price: number;
  }) =>
    request<{
      data: {
        transaction: import('@bolsa/shared').TransactionDto;
        summary: import('@bolsa/shared').PortfolioSummaryDto;
      };
    }>('/api/portfolio/trade', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  getBacktests: (limit = 20) =>
    request<{ data: import('@bolsa/shared').BacktestRunDto[] }>(
      `/api/backtests?limit=${encodeURIComponent(String(limit))}`,
    ),

  pruneBacktests: (keep: number) =>
    request<{ deleted: number; keep: number }>('/api/backtests/prune', {
      method: 'POST',
      body: JSON.stringify({ keep }),
    }),

  getBacktest: (id: string) =>
    request<{ data: import('@bolsa/shared').BacktestRunDetailDto }>(`/api/backtests/${id}`),

  runBacktest: (
    body: {
      instrumentId: string;
      strategyType?: import('@bolsa/shared').BacktestStrategyType;
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
      labEvidence?: import('@bolsa/shared').PaperLabEvidenceSnapshot | null;
    },
    init?: { signal?: AbortSignal },
  ) =>
    request<import('@bolsa/shared').BacktestRunResponseDto>('/api/backtests/run', {
      method: 'POST',
      body: JSON.stringify(body),
      signal: init?.signal,
    }),

  getResearchTrials: (query: import('@bolsa/shared').ResearchTrialsQuery = {}) => {
    const params = new URLSearchParams();
    if (query.instrumentId) params.set('instrumentId', query.instrumentId);
    if (query.proposedBy) params.set('proposedBy', query.proposedBy);
    if (query.presetKey) params.set('presetKey', query.presetKey);
    if (query.strategy) params.set('strategy', query.strategy);
    if (query.strategyDefinitionId) params.set('strategyDefinitionId', query.strategyDefinitionId);
    if (query.optimizationRunId) params.set('optimizationRunId', query.optimizationRunId);
    if (query.backtestRunId) params.set('backtestRunId', query.backtestRunId);
    if (query.failCode) params.set('failCode', query.failCode);
    if (query.dateFrom) params.set('dateFrom', query.dateFrom);
    if (query.dateTo) params.set('dateTo', query.dateTo);
    if (query.sort) params.set('sort', query.sort);
    if (query.sortDir) params.set('sortDir', query.sortDir);
    if (query.limit != null) params.set('limit', String(query.limit));
    if (query.offset != null) params.set('offset', String(query.offset));
    const qs = params.toString();
    return request<import('@bolsa/shared').ResearchTrialsListResponseDto>(
      `/api/research/trials${qs ? `?${qs}` : ''}`,
    );
  },

  getResearchTrial: (id: string) =>
    request<import('@bolsa/shared').ResearchTrialDetailResponseDto>(`/api/research/trials/${id}`),

  getInstrumentResearchSummary: (instrumentId: string) =>
    request<{ data: import('@bolsa/shared').InstrumentResearchSummaryDto }>(
      `/api/research/instruments/${instrumentId}/summary`,
    ),

  getLaboratoryResearchSummary: () =>
    request<{ data: import('@bolsa/shared').LaboratoryResearchSummaryDto }>('/api/research/summary'),

  getLabHealth: () =>
    request<{ data: import('@bolsa/shared').LabHealthDto }>('/api/research/lab-health'),

  /** Evidence sesión C DÍA D → Fase 2 research_evidence (source=dia_d_session). */
  persistDiaDSessionEvidence: (body: {
    instrumentId: string;
    symbol: string;
    mode: string;
    strategyLabel: string;
    diaD: string;
    endDate: string;
    engine?: string;
    evidence: Record<string, unknown>;
  }) =>
    request<{
      data: {
        id: string;
        instrumentId: string;
        level: string;
        source: string;
        evidenceWeight: number;
        summary: Record<string, unknown>;
        createdAt: string;
      };
    }>('/api/research/dia-d-session-evidence', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  optimizeBacktest: (body: import('@bolsa/shared').OptimizeSmaGridRequestDto) =>
    request<import('@bolsa/shared').OptimizeSmaGridResponseDto>('/api/backtests/optimize', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  enqueueOptimizeJob: (body: import('@bolsa/shared').OptimizeSmaGridRequestDto) =>
    request<import('@bolsa/shared').OptimizationRunResponseDto>('/api/backtests/optimize/jobs', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  getOptimizeRun: (runId: string) =>
    request<import('@bolsa/shared').OptimizationRunResponseDto>(
      `/api/backtests/optimize/runs/${runId}`,
    ),

  getOptimizeRuns: () =>
    request<import('@bolsa/shared').OptimizationRunsListResponseDto>('/api/backtests/optimize/runs'),

  getStrategies: () =>
    request<{ data: import('@bolsa/shared').StrategyDefinitionSummaryDto[] }>('/api/strategies'),

  getStrategy: (id: string) =>
    request<{ data: import('@bolsa/shared').StrategyDefinitionDetailDto }>(`/api/strategies/${id}`),

  createStrategyFromPreset: (body: import('@bolsa/shared').CreateStrategyFromPresetDto) =>
    request<{ data: import('@bolsa/shared').StrategyDefinitionDetailDto }>(
      '/api/strategies/from-preset',
      { method: 'POST', body: JSON.stringify(body) },
    ),

  draftStrategyFromPrompt: (body: import('@bolsa/shared').DraftStrategyFromPromptRequestDto) =>
    request<{ data: import('@bolsa/shared').DraftStrategyFromPromptResultDto }>(
      '/api/strategies/draft-from-prompt',
      { method: 'POST', body: JSON.stringify(body) },
    ),

  draftIndicatorFromPrompt: (body: import('@bolsa/shared').DraftIndicatorFromPromptRequestDto) =>
    request<{ data: import('@bolsa/shared').DraftIndicatorFromPromptResultDto }>(
      '/api/indicators/draft-from-prompt',
      { method: 'POST', body: JSON.stringify(body) },
    ),

  createStrategy: (body: import('@bolsa/shared').UpsertStrategyDefinitionDto) =>
    request<{ data: import('@bolsa/shared').StrategyDefinitionDetailDto }>('/api/strategies', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  updateStrategy: (id: string, body: import('@bolsa/shared').UpdateStrategyDefinitionDto) =>
    request<{ data: import('@bolsa/shared').StrategyDefinitionDetailDto }>(
      `/api/strategies/${id}`,
      { method: 'PATCH', body: JSON.stringify(body) },
    ),

  deleteStrategy: (id: string) =>
    request<void>(`/api/strategies/${id}`, { method: 'DELETE' }),

  getTrackers: (enabledOnly = false) =>
    request<import('@bolsa/shared').TrackerDefinitionsListResponseDto>(
      `/api/trackers${enabledOnly ? '?enabled_only=true' : ''}`,
    ),

  getTracker: (id: string) =>
    request<import('@bolsa/shared').TrackerDefinitionResponseDto>(`/api/trackers/${id}`),

  createTracker: (body: import('@bolsa/shared').CreateTrackerDefinitionDto) =>
    request<import('@bolsa/shared').TrackerDefinitionResponseDto>('/api/trackers', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  updateTracker: (id: string, body: import('@bolsa/shared').UpdateTrackerDefinitionDto) =>
    request<import('@bolsa/shared').TrackerDefinitionResponseDto>(`/api/trackers/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),

  deleteTracker: (id: string) =>
    request<void>(`/api/trackers/${id}`, { method: 'DELETE' }),

  runTrackerScan: (trackerId: string) =>
    request<import('@bolsa/shared').ScanRunResponseDto>(`/api/trackers/${trackerId}/scan`, {
      method: 'POST',
    }),

  enqueueTrackerScanJob: (trackerId: string) =>
    request<import('@bolsa/shared').ScanJobResponseDto>(
      `/api/trackers/${trackerId}/scan-jobs`,
      { method: 'POST' },
    ),

  evaluateTrackerSchedules: (options?: { trackerId?: string; force?: boolean }) => {
    const params = new URLSearchParams();
    if (options?.trackerId) params.set('trackerId', options.trackerId);
    if (options?.force) params.set('force', 'true');
    const query = params.toString();
    return request<import('@bolsa/shared').EvaluateTrackerSchedulesResponseDto>(
      `/api/trackers/schedules/evaluate${query ? `?${query}` : ''}`,
      { method: 'POST' },
    );
  },

  getExecutionPolicies: (enabledOnly = false) =>
    request<import('@bolsa/shared').ExecutionPoliciesListResponseDto>(
      `/api/execution-policies${enabledOnly ? '?enabled_only=true' : ''}`,
    ),

  getExecutionPolicy: (id: string) =>
    request<import('@bolsa/shared').ExecutionPolicyResponseDto>(
      `/api/execution-policies/${id}`,
    ),

  createExecutionPolicy: (body: import('@bolsa/shared').CreateExecutionPolicyDto) =>
    request<import('@bolsa/shared').ExecutionPolicyResponseDto>(
      '/api/execution-policies',
      { method: 'POST', body: JSON.stringify(body) },
    ),

  updateExecutionPolicy: (
    id: string,
    body: import('@bolsa/shared').UpdateExecutionPolicyDto,
  ) =>
    request<import('@bolsa/shared').ExecutionPolicyResponseDto>(
      `/api/execution-policies/${id}`,
      { method: 'PATCH', body: JSON.stringify(body) },
    ),

  deleteExecutionPolicy: (id: string) =>
    request<void>(`/api/execution-policies/${id}`, { method: 'DELETE' }),

  routeSignalsThroughPolicy: (
    policyId: string,
    body: import('@bolsa/shared').RouteSignalsRequestDto,
  ) =>
    request<import('@bolsa/shared').RouteSignalsResponseDto>(
      `/api/execution-policies/${policyId}/route`,
      { method: 'POST', body: JSON.stringify(body) },
    ),

  executeScanJobHits: (jobId: string, body: import('@bolsa/shared').ExecuteScanJobRequestDto) =>
    request<import('@bolsa/shared').RouteSignalsResponseDto>(
      `/api/scans/jobs/${jobId}/execute`,
      { method: 'POST', body: JSON.stringify(body) },
    ),

  getPositionPolicies: (accountId?: string) =>
    request<import('@bolsa/shared').PositionPoliciesListResponseDto>(
      `/api/position-policies${accountId ? `?accountId=${encodeURIComponent(accountId)}` : ''}`,
    ),

  lookupPositionPolicy: (accountId: string, instrumentId: string) =>
    request<import('@bolsa/shared').PositionPolicyResponseDto>(
      `/api/position-policies/lookup?accountId=${encodeURIComponent(accountId)}&instrumentId=${encodeURIComponent(instrumentId)}`,
    ),

  createPositionPolicy: (body: import('@bolsa/shared').CreatePositionPolicyDto) =>
    request<import('@bolsa/shared').PositionPolicyResponseDto>('/api/position-policies', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  updatePositionPolicy: (id: string, body: import('@bolsa/shared').UpdatePositionPolicyDto) =>
    request<import('@bolsa/shared').PositionPolicyResponseDto>(
      `/api/position-policies/${id}`,
      { method: 'PATCH', body: JSON.stringify(body) },
    ),

  deletePositionPolicy: (id: string) =>
    request<void>(`/api/position-policies/${id}`, { method: 'DELETE' }),

  evaluatePositionExits: (
    accountId: string,
    options?: { executeTrades?: boolean; timeframe?: '1d' | '1wk' },
  ) => {
    const params = new URLSearchParams({ accountId });
    if (options?.executeTrades) params.set('executeTrades', 'true');
    if (options?.timeframe) params.set('timeframe', options.timeframe);
    return request<import('@bolsa/shared').EvaluatePositionExitsResponseDto>(
      `/api/position-policies/evaluate-exits?${params.toString()}`,
      { method: 'POST' },
    );
  },

  getPlatformEvents: (options?: import('@bolsa/shared').ListPlatformEventsQuery) => {
    const params = new URLSearchParams();
    if (options?.limit) params.set('limit', String(options.limit));
    if (options?.type) params.set('type', options.type);
    if (options?.correlationId) params.set('correlationId', options.correlationId);
    const query = params.toString();
    return request<import('@bolsa/shared').PlatformEventsListResponseDto>(
      `/api/platform-events${query ? `?${query}` : ''}`,
    );
  },

  deployStrategyPaperAccount: (
    strategyId: string,
    body: import('@bolsa/shared').DeployPaperAccountRequestDto = {},
  ) =>
    request<import('@bolsa/shared').DeployPaperAccountResponseDto>(
      `/api/strategies/${strategyId}/paper-account`,
      { method: 'POST', body: JSON.stringify(body) },
    ),

  deployBacktestPaperAccount: (
    runId: string,
    body: import('@bolsa/shared').DeployPaperAccountRequestDto = {},
  ) =>
    request<import('@bolsa/shared').DeployPaperAccountResponseDto>(
      `/api/backtests/${runId}/deploy-paper`,
      { method: 'POST', body: JSON.stringify(body) },
    ),

  searchMarketIndices: (q: string, limit = 12) =>
    request<{ data: import('@bolsa/shared').MarketIndexHitDto[] }>(
      `/api/market-indices/search?q=${encodeURIComponent(q)}&limit=${limit}`,
    ),

  getMarketIndexCatalog: () =>
    request<{ data: import('@bolsa/shared').CatalogIndexEntryDto[] }>('/api/market-indices/catalog'),

  getMarketIndexConstituents: (indexKey: string) =>
    request<{ data: import('@bolsa/shared').IndexConstituentsDto }>(
      `/api/market-indices/${encodeURIComponent(indexKey)}/constituents`,
    ),

  subscribeMarketIndex: (body: {
    indexKey: string;
    syncBars?: boolean;
    yearsBack?: number;
  }) =>
    request<{ data: import('@bolsa/shared').SubscribeMarketIndexResultDto }>(
      '/api/market-indices/subscribe',
      { method: 'POST', body: JSON.stringify(body) },
    ),

  enqueueIndexSubscribeJob: (body: {
    indexKey: string;
    syncBars?: boolean;
    yearsBack?: number;
  }) =>
    request<{ data: import('@bolsa/shared').IndexSubscribeJobDto }>(
      '/api/market-indices/subscribe/jobs',
      { method: 'POST', body: JSON.stringify(body) },
    ),

  getIndexSubscribeJob: (jobId: string) =>
    request<{ data: import('@bolsa/shared').IndexSubscribeJobDto }>(
      `/api/market-indices/subscribe/jobs/${encodeURIComponent(jobId)}`,
    ),

  getLists: () =>
    request<{ data: import('@bolsa/shared').InstrumentListSummaryDto[] }>('/api/lists'),

  getList: (id: string) =>
    request<{ data: import('@bolsa/shared').InstrumentListDetailDto }>(`/api/lists/${id}`),

  getListQuotes: (id: string) =>
    request<{ data: import('@bolsa/shared').InstrumentWithMetaDto[] }>(`/api/lists/${id}/quotes`),

  getListTrackers: (listId: string) =>
    request<{ data: import('@bolsa/shared').TrackerDefinitionDetailDto[] }>(
      `/api/lists/${listId}/trackers`,
    ),

  createList: (body: {
    name: string;
    instrumentIds?: string[];
    source?: string;
    kind?: string;
  }) =>
    request<{ data: import('@bolsa/shared').InstrumentListDetailDto }>('/api/lists', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  updateList: (id: string, body: { name?: string; instrumentIds?: string[] }) =>
    request<{ data: import('@bolsa/shared').InstrumentListDetailDto }>(`/api/lists/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),

  deleteList: (id: string) =>
    request<void>(`/api/lists/${id}`, { method: 'DELETE' }),

  getAlerts: (activeOnly = false) =>
    request<{ data: import('@bolsa/shared').PriceAlertDto[] }>(
      `/api/alerts${activeOnly ? '?activeOnly=true' : ''}`,
    ),

  createAlert: (body: {
    instrumentId: string;
    condition: import('@bolsa/shared').AlertCondition;
    priceSource?: import('@bolsa/shared').AlertPriceSource;
    targetPrice: number;
    note?: string;
  }) =>
    request<{ data: import('@bolsa/shared').PriceAlertDto }>('/api/alerts', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  deleteAlert: (id: string) => request<void>(`/api/alerts/${id}`, { method: 'DELETE' }),

  reactivateAlert: (id: string) =>
    request<{ data: import('@bolsa/shared').PriceAlertDto }>(`/api/alerts/${id}/reactivate`, {
      method: 'POST',
    }),

  evaluateAlerts: () =>
    request<{ data: import('@bolsa/shared').PriceAlertDto[] }>('/api/alerts/evaluate', {
      method: 'POST',
    }),

  getSignalAlerts: (activeOnly = false) =>
    request<import('@bolsa/shared').SignalAlertSubscriptionsResponseDto>(
      `/api/signal-alerts${activeOnly ? '?activeOnly=true' : ''}`,
    ),

  createSignalAlert: (body: import('@bolsa/shared').CreateSignalAlertSubscriptionRequestDto) =>
    request<import('@bolsa/shared').SignalAlertSubscriptionResponseDto>('/api/signal-alerts', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  deleteSignalAlert: (id: string) =>
    request<void>(`/api/signal-alerts/${id}`, { method: 'DELETE' }),

  resetSignalAlertDedupe: (id: string) =>
    request<import('@bolsa/shared').SignalAlertSubscriptionResponseDto>(
      `/api/signal-alerts/${id}/reset-dedupe`,
      { method: 'POST' },
    ),

  evaluateSignalAlerts: () =>
    request<import('@bolsa/shared').EvaluateSignalAlertsResponseDto>('/api/signal-alerts/evaluate', {
      method: 'POST',
    }),

  getWorkspaces: () =>
    request<{ data: import('@bolsa/shared').WorkspaceSummaryDto[] }>('/api/workspaces'),

  getDefaultWorkspace: () =>
    request<{ data: WorkspaceDetailApi }>('/api/workspaces/default'),

  getWorkspace: (id: string) =>
    request<{ data: WorkspaceDetailApi }>(`/api/workspaces/${id}`),

  createWorkspace: (body: {
    name: string;
    document?: import('@bolsa/shared').WorkspaceDocument;
    dockLayout?: import('@bolsa/shared').TradingDockLayoutPrefs;
    isDefault?: boolean;
  }) =>
    request<{ data: WorkspaceDetailApi }>('/api/workspaces', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  updateWorkspace: (
    id: string,
    body: {
      name?: string;
      document?: import('@bolsa/shared').WorkspaceDocument;
      dockLayout?: import('@bolsa/shared').TradingDockLayoutPrefs;
      isDefault?: boolean;
    },
  ) =>
    request<{ data: WorkspaceDetailApi }>(`/api/workspaces/${id}`, {
      method: 'PUT',
      body: JSON.stringify(body),
    }),

  deleteWorkspace: (id: string) =>
    request<void>(`/api/workspaces/${id}`, { method: 'DELETE' }),

  /** PUT con keepalive para guardar al cerrar pestaña / apagar PC. */
  updateWorkspaceKeepalive: (
    id: string,
    body: {
      name?: string;
      document?: import('@bolsa/shared').WorkspaceDocument;
      dockLayout?: import('@bolsa/shared').TradingDockLayoutPrefs;
      isDefault?: boolean;
    },
  ) => {
    const token = getAuthToken();
    void fetch(`${API_URL}/api/workspaces/${id}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(body),
      keepalive: true,
    });
  },

  getSyncSettings: () =>
    request<{ data: import('@bolsa/shared').SyncSettingsDto }>('/api/sync/settings'),

  updateSyncSettings: (body: Partial<import('@bolsa/shared').SyncSettingsDto>) =>
    request<{ data: import('@bolsa/shared').SyncSettingsDto }>('/api/sync/settings', {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),

  getSyncQueue: () =>
    request<{ data: import('@bolsa/shared').SyncQueueItemDto[] }>('/api/sync/queue'),

  enqueueStaleInstruments: () =>
    request<{ data: { scanned: number; enqueued: number } }>('/api/sync/queue/enqueue-stale', {
      method: 'POST',
    }),

  getPendingOrders: () =>
    request<{ data: import('@bolsa/shared').PendingOrderDto[] }>('/api/pending-orders'),

  createPendingOrder: (body: {
    instrumentId: string;
    symbol: string;
    side: 'buy' | 'sell';
    orderType?: string;
    quantity: number;
    limitPrice: number;
    expiryAt?: string | null;
  }) =>
    request<{ data: import('@bolsa/shared').PendingOrderDto[] }>('/api/pending-orders', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  deletePendingOrder: (id: string) =>
    request<void>(`/api/pending-orders/${id}`, { method: 'DELETE' }),
};

type WorkspaceDetailApi = {
  id: string;
  name: string;
  isDefault: boolean;
  document: import('@bolsa/shared').WorkspaceDocument;
  dockLayout: import('@bolsa/shared').TradingDockLayoutPrefs | null;
  createdAt: string;
  updatedAt: string;
};
