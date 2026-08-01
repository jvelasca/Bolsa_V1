# Arquitectura de datos — Backtesting → IA

Documento de diseño (jul 2026). Define **cómo procesaremos datos en el futuro cercano con IA** y qué estructura hay que plantear **ahora** para que el hub de backtesting encaje sin reescrituras.

Complementa: [BACKTESTING_AUDIT.md](./BACKTESTING_AUDIT.md), [ADR-003](./adr/003-python-backend-ai-platform.md), [ADR-007](./adr/007-intraday-ohlcv-persistence.md), [CHART_INDICATORS.md](./CHART_INDICATORS.md).

---

## 1. Principio rector

> **Una sola tubería de datos validados.** El mismo OHLCV, los mismos indicadores y las mismas reglas de tiempo alimentan: gráfico, backtest clásico, optimización masiva, entrenamiento ML y (más adelante) generación de estrategias por IA.

La IA **no calcula números de trading**. Genera o propone **especificaciones** y **código/spec ejecutable**; un **motor determinista** (Python) produce métricas, trades y features. Patrón validado en 2025–2026 por Keel, Algosmithy, AlphaForgeBench, QuantGenie SDL y backtester-mcp.

```
                    ┌─────────────────────────────────────────┐
                    │              UI (React)                  │
                    │  Chart │ Backtest Hub │ (futuro) AI Lab  │
                    └───────────────┬─────────────────────────┘
                                    │ OpenAPI (contratos)
┌───────────────────────────────────▼───────────────────────────────────┐
│                         apps/api-python (HTTP fino)                    │
│   /backtests  /strategies  /features  /jobs  /datasets  /ai/* (futuro) │
└───────────────────────────────────┬───────────────────────────────────┘
                                    │
┌───────────────────────────────────▼───────────────────────────────────┐
│                      bolsa_application (casos de uso)                  │
│  RunBacktest │ OptimizeStrategy │ BuildFeatureMatrix │ QueueResearchJob│
└───────┬─────────────┬──────────────┬──────────────┬───────────────────┘
        │             │              │              │
        ▼             ▼              ▼              ▼
  bolsa_analytics  bolsa_features  bolsa_research   bolsa_ai (fase 6+)
  (determinista)   (capa features) (datasets/jobs)  (LLM/ML probabilístico)
        │             │              │              │
        └─────────────┴──────────────┴──────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        ▼                           ▼                           ▼
  bolsa_market                 bolsa_domain              bolsa_infrastructure
  (ingesta/sanity)             (entidades/specs)         (PG, Redis, MinIO, workers)
```

---

## 2. Tres horizontes temporales

| Horizonte | Plazo | Objetivo | Procesamiento |
|-----------|-------|----------|---------------|
| **H0 — Ahora** | BT-0…BT-4 | Hub backtest manual, motor extensible, paridad indicadores | Sync API, bar-by-bar Python, ~500–5k barras |
| **H1 — Futuro cercano** | 6–12 meses | Optimización masiva, features batch, jobs async, intraday backtest | VectorBT + Optuna, workers Arq, Redis cache, Parquet datasets |
| **H2 — IA operativa** | 12–24 meses | NL→spec, ML tabular, validación estadística, MCP agentes | Mismo motor + `bolsa_ai` + manifests + walk-forward/PBO |

**Regla ADR-003 (no negociable):** H2 solo cuando H0+H1 sean fiables. La IA amplifica errores de datos y de paridad indicador.

---

## 3. Capas de datos (modelo objetivo)

Inspirado en arquitecturas quant 2.0 (lakehouse + feature store + MLOps), **adaptado a escala retail/prosumer** con PostgreSQL + MinIO, sin Databricks.

### 3.1 Capa 0 — Raw ingest

| Qué | Dónde hoy | Evolución |
|-----|-----------|-----------|
| OHLCV Yahoo/XTB | `ohlcv_bars` PostgreSQL | Hypertable Timescale + compresión |
| Validación Pydantic | `bolsa_market/ingest.py` | Mantener; ampliar splits/corp actions |
| Sanity checks | `bolsa_market/sanity.py` | Gates antes de **cualquier** compute |
| Sync logs | `data_sync_log`, `sync_queue` | + `data_snapshot` metadata |

**Contrato:** ningún job de backtest, feature o ML lee datos que no pasaron sanity.

### 3.2 Capa 1 — DataSnapshot (referencia inmutable)

Cada run (backtest, optimización, entrenamiento) apunta a un **snapshot lógico**, no a «lo que haya en BD ahora».

```typescript
// packages/shared — contrato objetivo
interface DataSnapshotRef {
  id: string;                    // hash o UUID
  instrumentIds: string[];
  timeframe: Timeframe;
  from: string;                  // ISO instant
  to: string;
  barCount: number;
  dataVersion: string;           // hash(contenido o max(updated_at))
  sanityReportId?: string;
  source: 'postgres' | 'parquet_export';
}
```

**Por qué ahora:** reproducibilidad IA y auditoría. Sin snapshot, un re-sync de Yahoo invalida comparar runs.

**Implementación H0:** calcular `dataVersion` al ejecutar backtest (hash de timestamps+closes); persistir en `backtest_runs`. Tabla `data_snapshots` en H1.

### 3.3 Capa 2 — Features (indicadores + derivados)

**Problema actual:** chart calcula 9 indicadores en TS; backtest usa 4 fijos en Python → **training-serving skew** garantizado.

**Solución objetivo — catálogo único + compute server-side:**

```
IndicatorDefinition (shared TS)
        ↓
IndicatorSpec { definitionId, parameters }  ← ya existe en indicators-runtime.ts
        ↓
bolsa_analytics/indicators/compute.py  ← implementación canónica Python
        ↓
FeatureMatrix (parquet) o API series
        ↓
Chart (consume API) │ Backtest │ VectorBT │ ML
```

| Modo | Uso | Motor |
|------|-----|-------|
| **On-demand** | Chart, single backtest | API sync / Redis cache |
| **Batch** | Optimización 10k configs | VectorBT / Polars partition |
| **Stream** (H2) | Paper/live | Redis online store |

**Endpoint planificado:** `POST /api/indicators/compute` (ya anotado en `indicators-runtime.ts`).

**Chart en H0:** sigue computando local para UX; **backtest y research usan Python**. Migración chart → API gradual cuando paridad testeada (golden tests).

**Paquete nuevo sugerido:** `packages/py/features/` o submódulo `bolsa_analytics/features/`:
- `compute_spec(spec, ohlcv) → series`
- `build_matrix(specs[], ohlcv) → DataFrame`
- `point_in_time_join(bars, features, t)` — anti look-ahead

### 3.4 Capa 3 — StrategySpec (reglas ejecutables)

Puente entre UI, backtest clásico e IA. Inspirado en QuantGenie SDL y Composer visual logic.

```typescript
interface StrategyDefinitionV1 {
  id: string;
  version: number;
  name: string;
  kind: 'rule_based' | 'indicator_signals' | 'ml_model' | 'hybrid';
  universe: { instrumentIds: string[] };
  timeframe: Timeframe;
  dataSnapshotPolicy: 'latest' | 'pinned';  // pinned = DataSnapshotRef

  // Señales (H0)
  entries: RuleGroup;
  exits: RuleGroup;
  sizing: { mode: 'fixed_cash' | 'percent_equity'; value: number };
  risk: { stopLossPct?: number; takeProfitPct?: number; maxPositions?: number };

  // Indicadores referenciados (paridad con chart)
  indicatorSpecs: IndicatorSpec[];

  // Costes (realismo)
  execution: {
    fillModel: 'next_bar_open' | 'bar_close';
    commissionBps: number;
    slippageBps: number;
  };

  // Provenance (IA futuro)
  origin: 'manual' | 'assisted' | 'ai_generated' | 'imported';
  sourcePrompt?: string;       // si IA — no ejecutar, solo audit
  parentStrategyId?: string;
}

interface RuleGroup {
  operator: 'all' | 'any';
  rules: Rule[];
}

interface Rule {
  type: 'indicator_compare' | 'indicator_cross' | 'price_above' | 'drawing_trigger';
  // ... params tipados
}
```

**H0:** subset mínimo — `kind: 'indicator_signals'`, 2–3 tipos de regla, mapeo desde estrategias enum actuales.

**H2:** LLM produce JSON validado contra schema Pydantic → **nunca** ejecuta texto libre.

### 3.5 Capa 4 — Labels (solo ML — H1/H2)

Para ML tabular (LightGBM/XGBoost), pipeline separado del backtest rule-based:

| Label scheme | Uso | Referencia |
|--------------|-----|------------|
| Triple barrier / double barrier | Dirección + horizon | cTrader-MLAuto-Trader, López de Prado |
| Forward return bins | Clasificación | Research estándar |
| Meta-labels | Filtrar señales primary | Fase avanzada |

```
Features(t) + Labels(t) → Dataset versionado (Parquet + manifest)
                       → Train/val/test splits temporales (NO random shuffle)
```

**Tabla futura:** `ml_datasets`, `ml_dataset_versions`, `ml_models`.

### 3.6 Capa 5 — Artifacts (runs, modelos, reports)

| Artifact | Storage H0 | Storage H1+ |
|----------|------------|-------------|
| BacktestRun + trades | PostgreSQL | + Parquet export |
| RunManifest (JSON) | columna JSON en run | MinIO + DuckDB analytics |
| Equity curve | calculada on-read | Parquet precomputado |
| Optimización trials | — | PostgreSQL + Parquet |
| Modelos ML | — | MinIO (`models/{id}/{version}.pkl/onnx`) |
| HTML validation report | — | MinIO (estilo backtester-mcp) |

---

## 4. RunManifest — reproducibilidad total

Cada ejecución (backtest, optimize, train, ai_proposal) guarda un manifest. Patrón Algosmithy YAML + FINSABER artifact schema + Keel compiled graph.

```json
{
  "manifestVersion": "1.0",
  "runId": "clx...",
  "runType": "backtest",
  "createdAt": "2026-07-11T10:00:00Z",
  "engine": {
    "name": "bolsa_event_backtest",
    "version": "0.2.0",
    "gitSha": "abc123"
  },
  "dataSnapshot": { "...": "DataSnapshotRef" },
  "strategy": { "...": "StrategyDefinitionV1" },
  "indicatorSpecs": [ "..." ],
  "executionParams": { "initialCash": 10000 },
  "environment": {
    "python": "3.12.4",
    "bolsa_analytics": "0.1.0"
  },
  "outputs": {
    "metricsHash": "sha256:...",
    "tradeCount": 42
  },
  "provenance": {
    "origin": "manual",
    "userId": null,
    "parentRunId": null
  }
}
```

**Acción H0:** añadir `manifest JSONB` a `backtest_runs` aunque el motor siga siendo simple.

---

## 5. Dos motores de simulación (complementarios)

La industria separa **research throughput** de **execution realism**.

| Motor | Cuándo | Tech | Bolsa package |
|-------|--------|------|---------------|
| **Event-driven** | Backtest final, paper, live, reglas complejas | Loop bar-by-bar, comisiones, órdenes parciales | `bolsa_analytics/backtest/` (actual, evolucionar) |
| **Vectorized** | Grid search, Optuna, screening IA | VectorBT, NumPy broadcast | `bolsa_analytics/vectorized/` (H1) |

```
                    ┌─────────────────┐
  StrategySpec ────►│  FeatureMatrix   │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼                             ▼
     EventBacktestEngine            VectorizedEngine
     (verdad operativa)            (exploración rápida)
              │                             │
              └──────────────┬──────────────┘
                             ▼
                      RunManifest + metrics
```

**Flujo IA (H2):** LLM propone 20 variantes → VectorBT filtra → top 3 → Event engine valida → manifest + PBO/walk-forward.

---

## 6. Procesamiento masivo Python — diseño

### 6.1 Escala Bolsa V1 (realista)

| Dimensión | Volumen típico | Notas |
|-----------|----------------|-------|
| Instrumentos watchlist | 50–500 | IBEX + listas usuario |
| Timeframes | 9 | 1m…1mo |
| Barras/instrumento 1D | 5–20 años (~1.5k–5k) | Yahoo |
| Barras 1m (cache) | ~30–90 días × 390 | ADR-007 lazy cache |
| Grid Optuna | 500–50k trials | VectorBT |
| Features por barra | 20–100 columnas | Indicadores + derivados |

No necesitamos Spark/Ray al inicio. **Polars + VectorBT + partición por (instrument, timeframe)** es suficiente hasta ~100M filas feature.

### 6.2 Particionado (patrón QuantFlow)

```
Partition key = (instrument_id, timeframe, date_window)
Worker job = 1 partition → FeatureMatrix parquet shard
Reduce = merge metrics / union trials
```

Implementación H1:
- **Arq** workers leyendo jobs de Redis
- Input: `DataSnapshotRef` + `StrategyDefinition` + param grid
- Output: Parquet en MinIO + filas resumen en PostgreSQL

### 6.3 Cola de jobs (evolución desde sync_queue)

| Cola | Hoy | Objetivo |
|------|-----|----------|
| OHLCV sync | PostgreSQL `sync_queue` | Mantener |
| Research/backtest | — | Redis + Arq `research_queue` |
| IA batch | — | Misma cola, prioridad baja |

**JobSpec mínimo (definir ya en shared):**

```typescript
interface ResearchJobSpec {
  id: string;
  type: 'backtest' | 'optimize' | 'feature_build' | 'ml_train' | 'ai_strategy_draft';
  status: 'queued' | 'running' | 'completed' | 'failed';
  payload: Record<string, unknown>;
  resultRunId?: string;
  error?: string;
  createdAt: string;
  completedAt?: string;
}
```

H0: jobs sync disfrazados de «run inmediato» pero **misma forma JSON** → migración transparente a async.

### 6.4 Caché Redis (H1)

| Key pattern | TTL | Contenido |
|-------------|-----|-----------|
| `feat:{inst}:{tf}:{specHash}` | 1h–24h | Series indicador serializadas |
| `snap:{dataVersion}` | largo | Metadata snapshot |
| `bt:result:{runId}` | 7d | Métricas hot |

`REDIS_URL` ya está en config — sin uso. Activar en BT-1/BT-8.

---

## 7. Adaptación de datos para IA (H1–H2)

### 7.1 Point-in-time (anti look-ahead)

Reglas obligatorias en **todo** compute:

1. Indicador en barra `t` usa solo barras `≤ t` (close confirmado).
2. Señal en `t` ejecuta en `t+1` open (default TradingView/ProRealTime).
3. Joins feature-label: label en `t+h` no visible en decisión `t`.
4. Splits temporales: train `[T0,T1]`, val `[T1,T2]`, test `[T2,T3]` — **nunca** shuffle.

Implementar en `bolsa_features/point_in_time.py` + tests unitarios.

### 7.2 Validación estadística (pre-deploy IA)

Integrar en H2 (paquete `bolsa_research/validation/`):

| Test | Propósito | Ref |
|------|-----------|-----|
| Walk-forward | OOS rolling | QuantStrategy, MT5 |
| Deflated Sharpe (DSR) | Corrección multiple testing | Bailey & López de Prado |
| PBO | Overfitting paramétrico | backtester-mcp |
| Bootstrap Sharpe CI | Significancia | backtester-mcp |
| Monte Carlo permutations | Robustez equity curve | Keel lab |

**UI:** panel «Robustez» en hub — semáforo pass/caution/fail.

### 7.3 Pipeline LLM (H2 — diseño, no implementar ahora)

```
Usuario NL ──► LLM (tool-calling)
                  │
                  ├─► strategy_draft_tool → StrategyDefinitionV1 JSON
                  ├─► validate_spec_tool → Pydantic + lint reglas
                  ├─► run_backtest_tool → EventEngine (determinista)
                  ├─► validate_robustness_tool → DSR/PBO/walk-forward
                  └─► explain_results_tool → NL sobre métricas (OK alucinar aquí)
```

**Nunca:** LLM devuelve Sharpe directamente. Siempre `run_backtest_tool`.

Patrones: Keel typed tools, Algosmithy Docker sandbox, AlphaForgeBench executable code, BacktestLoop MCP.

**MCP Bolsa (BT-10):** exponer tools al Cursor agent del usuario — coherente con monorepo.

### 7.4 RAG sobre documentación propia (H2)

Corpus: ADRs, catálogo indicadores, ejemplos StrategySpec, runs históricos anonimizados.

`packages/py/ai/rag/` — embeddings + pgvector o Qdrant. **No** RAG sobre precios (usar features compute).

---

## 8. Evolución `packages/py/` (estructura objetivo)

```
packages/py/
├── domain/                    # ✅ Existente — ampliar
│   ├── entities/
│   │   ├── strategy.py        # NEW StrategyDefinition
│   │   ├── data_snapshot.py   # NEW
│   │   ├── research_job.py    # NEW
│   │   └── feature_spec.py    # NEW
│   └── value_objects/
│       └── indicator_spec.py  # NEW (mirror shared)
│
├── market/                    # ✅ Sin cambio sustancial
│
├── analytics/                 # ✅ Ampliar
│   ├── indicators/
│   │   ├── compute.py         # Canónico multi-indicador
│   │   ├── catalog.py         # Mirror TS definitions
│   │   └── parity_tests/      # Golden vs TS
│   ├── backtest/
│   │   ├── event_engine.py    # Refactor actual
│   │   └── vectorized.py      # H1 VectorBT wrapper
│   └── validation/            # H2 DSR, PBO, walk-forward
│
├── features/                  # NEW H1
│   ├── matrix.py              # OHLCV + specs → DataFrame
│   ├── point_in_time.py
│   └── export_parquet.py
│
├── research/                  # NEW H1
│   ├── datasets.py
│   ├── manifests.py
│   └── optimize.py            # Optuna orchestration
│
├── ai/                        # H2
│   ├── llm/                   # Tool calling, prompts
│   ├── ml/                    # LightGBM pipelines
│   └── rag/
│
├── application/               # ✅ Casos de uso nuevos
│   ├── run_backtest.py
│   ├── run_optimization.py
│   ├── build_features.py
│   └── queue_research_job.py
│
└── infrastructure/            # ✅ Ampliar
    ├── redis/
    ├── minio/
    ├── workers/               # Arq tasks
    └── database/              # Nuevas tablas
```

**Regla ADR-003:** `analytics` = determinista; `ai` = probabilístico. No mezclar.

---

## 9. Evolución base de datos

### 9.1 Tablas nuevas (planificadas)

| Tabla | Horizonte | Propósito |
|-------|-----------|-----------|
| `data_snapshots` | H1 | Referencia inmutable datos |
| `strategy_definitions` | H0–H1 | Specs versionadas |
| `research_jobs` | H1 | Cola async |
| `optimization_trials` | H1 | Optuna/VectorBT results |
| `feature_cache_meta` | H1 | Invalidación Redis |
| `ml_datasets` / `ml_models` | H2 | ML tabular |
| `ai_strategy_drafts` | H2 | NL → spec pendiente validación |

### 9.2 Ampliación `backtest_runs` (H0 — hacer ya)

```sql
-- Campos a añadir progresivamente
ALTER TABLE backtest_runs ADD COLUMN IF NOT EXISTS
  strategy_definition_id TEXT,
  timeframe TEXT DEFAULT '1d',
  data_snapshot_id TEXT,
  manifest JSONB,
  commission_bps INT DEFAULT 0,
  slippage_bps INT DEFAULT 0;
```

### 9.3 Timescale + MinIO (H1)

| Componente | Acción |
|------------|--------|
| `create_hypertable('ohlcv_bars')` | Alembic migration pendiente |
| Continuous aggregates | 1h/1d rollups desde 1m |
| MinIO bucket `bolsa-research` | `datasets/`, `models/`, `reports/` |
| Parquet layout | `datasets/{snapshotId}/features.parquet` |

---

## 10. Contratos shared TypeScript ↔ Python

Todo contrato vive en `packages/shared` y se replica Pydantic en Python (hasta OpenAPI codegen completo).

| Contrato | Estado | Prioridad H0 |
|----------|--------|--------------|
| `IndicatorSpec` | Implícito en runtime | Formalizar export |
| `parametersKey()` / `instanceSpecKey()` | ✅ | Usar en StrategySpec |
| `StrategyDefinitionV1` | ❌ | **Crear** |
| `DataSnapshotRef` | ❌ | **Crear** |
| `RunManifest` | ❌ | **Crear** |
| `ResearchJobSpec` | ❌ | Crear (stub) |
| `ExecutionModel` | ❌ | Crear enum |
| `BACKTEST_STRATEGIES` enum | ✅ legacy | Migrar a StrategySpec |

**Golden tests:** JSON fixtures shared → Python valida → mismos hashes.

---

## 11. Flujos end-to-end

### 11.1 Backtest manual (H0)

```
UI Hub → StrategyDefinitionV1 (o preset enum)
      → Resolve DataSnapshotRef (instrument, tf, range)
      → market sanity gate
      → features.compute(indicatorSpecs, ohlcv)
      → event_engine.run(strategy, features)
      → RunManifest + metrics + trades → PostgreSQL
      → UI equity chart
```

### 11.2 «Backtest setup actual del chart» (H1)

```
Active chart tab → serialize:
  - instrumentId, timeframe
  - indicatorInstances[] → IndicatorSpec[]
  - (optional) drawings with triggers
→ StrategyDefinitionV1 draft
→ Usuario confirma reglas entry/exit
→ Mismo pipeline 11.1
```

### 11.3 Optimización masiva (H1)

```
StrategyDefinitionV1 + param ranges
→ ResearchJobSpec (type: optimize)
→ Arq worker:
    build FeatureMatrix once
    VectorBT grid / Optuna study
    top-N → EventEngine confirm
→ trials parquet + manifest per champion
```

### 11.4 ML tabular (H2)

```
IndicatorSpecs + label scheme + DataSnapshotRef
→ features.build_matrix + labels.build
→ dataset manifest → MinIO parquet
→ LightGBM train (bolsa_ai/ml)
→ model artifact + validation report
→ StrategyDefinitionV1 kind: 'ml_model'
→ EventEngine usa predicciones como señales
```

### 11.5 IA generativa (H2)

```
Usuario NL → LLM tools
→ StrategyDefinitionV1 (draft) → user review UI
→ validate → backtest → robustness panel
→ save strategy_definitions (origin: ai_generated)
→ (optional) paper deploy
```

---

## 12. Qué plantear EN BT-0…BT-4 para alinear con IA

Checklist de decisiones **de arquitectura** (no implementar IA aún):

| # | Decisión | Razón futuro IA |
|---|----------|-----------------|
| 1 | Introducir `StrategyDefinitionV1` aunque solo 2 presets | LLM genera mismo schema |
| 2 | `RunManifest` en cada run | Reproducibilidad agentes |
| 3 | `DataSnapshotRef` + `dataVersion` hash | Datasets ML consistentes |
| 4 | Formalizar `IndicatorSpec` + roadmap `POST /indicators/compute` | Una sola verdad features |
| 5 | `ResearchJobSpec` shape (sync OK) | Async VectorBT sin refactor UI |
| 6 | Separar `event_engine` / preparar `vectorized` | Research vs production |
| 7 | `execution.fillModel` en spec | Mismo enum LLM y manual |
| 8 | `origin` + `sourcePrompt` en strategy | Audit trail IA |
| 9 | No añadir lógica indicador nueva solo en TS | Skew mata ML |
| 10 | Hub UI con slots: Robustez, IA (disabled) | UX crece sin rediseño |

---

## 13. Anti-patrones a evitar

| Anti-patrón | Consecuencia |
|-------------|--------------|
| LLM calcula métricas | Números irreproducibles |
| Indicadores solo en chart TS | Backtest ≠ chart ≠ ML |
| Optimizar en todo el histórico | Curve-fitting garantizado |
| Random train/test split | Look-ahead temporal |
| Jobs solo sync sin manifest | Imposible auditar IA |
| VectorBT como único motor | Reglas complejas mal modeladas |
| Event engine para 50k grid | Demasiado lento |
| Datos sin sanity → features | Basura en, basura out |
| Schema strategy ad-hoc por UI | NL no puede generar |

---

## 14. Benchmark externo — síntesis aplicada

| Fuente | Aprendizaje Bolsa |
|--------|-------------------|
| **Finantrix / Feast / Tecton** | Feature store con online/offline parity — nosotros: `IndicatorSpec` + Redis + PG |
| **TradersView lakehouse** | Versionado datos + lineage — nosotros: `DataSnapshotRef` + manifest |
| **Quant 2.0 / AltStreet** | Separar storage/compute — nosotros: PG + MinIO + workers |
| **QuantFlow** | Partición (symbol×window) — nosotros: Arq jobs |
| **Keel / Algosmithy** | LLM → tools → engine determinista | 
| **AlphaForgeBench** | LLM genera código ejecutable, no trades |
| **FINSABER** | Artifact schema (`metrics.json`, `trades.csv`) |
| **backtester-mcp** | MCP validate_strategy con PBO/DSR |
| **VectorBT 2026** | Grid masivo + walk-forward nativo |
| **ProRealTime** | Assisted creation → backtest → paper → auto |
| **Composer / QuantGenie** | NL → spec editable → backtest → deploy |

---

## 15. Roadmap integrado (datos + producto)

| ID | Entregable | Capa datos tocada |
|----|------------|-------------------|
| BT-0 | Nav hub, quitar Indicadores top bar | — |
| BT-1 | Motor extensible + manifest + snapshot hash | Capa 1, 5 |
| BT-2 | `StrategyDefinitionV1` + DB + CRUD UI | Capa 3 ✅ jul 2026 |
| BT-3 | `IndicatorSpec` compute Python + golden tests + API | Capa 2 ✅ jul 2026 |
| BT-3b | Setup desde gráfico activo → StrategyDefinition draft | Capa 3 ✅ jul 2026 |
| BT-4 | Equity UI + export artifacts | Capa 5 ✅ jul 2026 |
| BT-5 | Chart replay manual en hub | Capa 0 ✅ jul 2026 |
| BT-6 | Drawing replay | Capa 3 rules ✅ jul 2026 |
| BT-7 | Paper bridge | Execution ✅ jul 2026 |
| **RD-1** | Timescale hypertable + aggregates | Capa 0 |
| **RD-2** | Redis cache + job queue scaffold | Infra |
| **RD-3** | VectorBT + Optuna worker | Capa 2 vectorized |
| **RD-4** | Parquet datasets + MinIO | Capa 2 batch |
| **RD-5** | Feature matrix pipeline | Capa 2 |
| **AI-1** | LLM tools + spec draft UI | Capa 3 |
| **AI-2** | ML tabular pipeline | Capa 4 |
| **AI-3** | Robustness suite (DSR/PBO) | Validation |
| **AI-4** | MCP server research tools | Integración Cursor |

---

## 16. Siguiente paso acordado

1. **Revisar y aprobar** este documento + [BACKTESTING_AUDIT.md](./BACKTESTING_AUDIT.md).
2. **Redactar ADR-009** formalizando BT-0…BT-4 y contratos H0.
3. **Crear tipos shared** (`StrategyDefinitionV1`, `DataSnapshotRef`, `RunManifest`) — sin motor completo aún.
4. **Implementar BT-0** (nav hub) con slots UI para fases futuras.

---

## Referencias

- [ADR-003](./adr/003-python-backend-ai-platform.md)
- [Finantrix ML platform](https://www.finantrix.com/in-focus/systematic-alpha-technology-stack-modern-hedge-fund/building-ml-platform-alpha-research)
- [TradersView data architecture](https://tradersview.net/practical-data-architecture-for-trading-firms-solving-the-we)
- [Keel LLM strategy generation](https://usekeel.io/learn/llm-strategy-generation)
- [Algosmithy](https://github.com/disciplinedware/algosmithy)
- [FINSABER](https://github.com/waylonli/finsaber)
- [backtester-mcp](https://github.com/bcosm/backtester-mcp)
- [VectorBT](https://vectorbt.dev/)
- [QuantGenie SDL](https://quantgenie.ai/build)
- [BacktestLoop MCP](https://backtestloop.com/)
