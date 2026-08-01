---
id: rfc-001
title: Artifact System & Catalog
status: approved
date: 2026-07-21
audience: development, data, ml, product
complements:
  - docs/rfc/000-ubiquitous-language.md
  - docs/AI_PLATFORM_SOLUTION.md
  - docs/adr/010-platform-kernel-radar-execution.md
---

# RFC-001: Artifact System & Catalog

> **Propósito:** Definir el **sistema de artefactos** de Bolsa V1: metamodelo común, ciclo de vida unificado, catálogo exhaustivo de tipos, grafo de dependencias y envelope compartido por todos los registries.  
> **Principio:** Todo lo que se versiona, se entrena, se ejecuta o se audita es un **Artifact**. Si no está en este catálogo, no es concepto formal.  
> **Alcance:** Constitución técnica. **No** exige migrar Prisma en el mismo PR; el §10 fija el mapeo actual y el target.

Complementa: [RFC-000](./000-ubiquitous-language.md).

---

## 1. Por qué este RFC es el corazón

Tras el lenguaje (RFC-000), **todo** en la plataforma se modela como artefacto:

```
Dataset · Feature · Prediction · Signal · Recommendation · Intent · Order · Trade
Prompt · Model · Policy · Backtest · Experiment · Manifest · …
```

Un solo metamodelo + lifecycle + grafo implica que Feature Registry, Model Registry, Policy Registry, Prediction Registry y Prompt Registry **no inventan formatos distintos**.

---

## 2. Artifact System (dimensiones)

Todo tipo de artefacto se describe en estas dimensiones:

| Dimensión | Contenido |
|-----------|-----------|
| **Identity** | `artifactId`, `artifactType` (`ART-*`), `version` / hash |
| **Metadata** | `name`, `description`, `tags`, `schemaVersion` |
| **Lifecycle** | `status` (máquina de estados §3) |
| **Ownership** | `owner`, `domain` (Domain ID RFC-000), `capability` (`CAP-*`) |
| **Version** | SemVer o content-hash; `parentArtifactId` opcional |
| **Dependencies** | Lista de `artifactId@version` (entradas del grafo) |
| **Lineage** | `lineageRefs` (datasets, snapshots, transforms) |
| **Validation** | Gates que permiten promoción de estado |
| **Storage** | `storageRefs` vía adapters (no acoplar a Redis/PG en la definición) |
| **Observability** | Eventos, métricas, `checksum`, audit |

---

## 3. Lifecycle unificado

Alineado con [RFC-000 §8](./000-ubiquitous-language.md). Estados canónicos:

```
Draft → Experimental → Validated → Production → Deprecated → Archived
```

| Status | Significado | Research / BT | Paper | Live |
|--------|-------------|-----------------|-------|------|
| `Draft` | Edición / salida de authoring | ❌\* | ❌ | ❌ |
| `Experimental` | Pruebas controladas | ✅ acotado | ❌ | ❌ |
| `Validated` | Gates sintácticos + tests deterministas | ✅ | ❌ | ❌ |
| `Production` | Autorizado en runtime (sujeto a Policy) | ✅ | ✅ | ✅ si Policy lo permite |
| `Deprecated` | Sin nuevos usos; histórico OK | ✅ histórico | ❌ nuevos | ❌ |
| `Archived` | Solo auditoría | ❌ | ❌ | ❌ |

\*Excepto jobs de validación explícitos sobre drafts de research.

**Estado operativo adicional (no sustituye lifecycle):**

| Flag | Uso |
|------|-----|
| `disabled` | Circuit breaker / kill-switch temporal sobre un artefacto `Production` (p. ej. policy o model). Reversible sin archivar. |

Alias prohibidos en código nuevo: `ACTIVE` → usar `Production`; `REJECTED` → volver a `Draft` o `Archived` con motivo.

### 3.1 Regla de promoción del grafo

Un artefacto en `Production` **no puede depender** de dependencias en `Draft`, `Experimental` (salvo excepción documentada en research), `Deprecated` (nuevas deps) o `Archived`.

---

## 4. Metamodelo común (Base Artifact Envelope)

Envelope **obligatorio** para cualquier entrada de registry (YAML/JSON/PG). Todos los registries extienden este schema; no lo reinventan.

```yaml
# Envelope común — todos los registries
id: string                    # estable, único en el registry
type: ART-*                   # Artifact Type ID (§5)
version: string               # semver o content hash
status: Draft|Experimental|Validated|Production|Deprecated|Archived
disabled: boolean             # default false; kill-switch operativo
owner: string
domain: string                # Domain ID RFC-000 (FEATURE, TRADING, …)
capability: string            # CAP-* (detalle RFC-002)
schema_version: string        # versión del envelope/spec del tipo
name: string
description: string
tags: string[]
created_at: datetime
updated_at: datetime
producer: string              # sistema/usuario/job que lo creó
consumers: string[]           # CAP-* o artifact ids esperados
dependencies:                 # edges del Artifact Graph
  - { id: string, version: string, relation: uses|derived_from|validates }
lineage:
  data_snapshot_ref: string | null
  transform_ids: string[]
storage:
  adapter: postgres|parquet|redis|duckdb|minio|memory|external
  refs: object                # claves específicas del adapter
quality:
  score: number | null
  checks: string[]
visibility: private|workspace|public
metadata: object              # extensiones no tipadas
checksum: string | null       # sha256 del payload canónico
payload: object               # campos específicos del tipo (§6)
```

### 4.1 Extensiones por registry (mismo envelope)

| Registry | Campos típicos en `payload` |
|----------|----------------------------|
| Feature Registry | `formula` / `compute_key`, `inputs`, `compute_engine`, `params` |
| Model Registry | `algorithm`, `metrics`, `feature_set_id`, `training_dataset_id` |
| Prediction Registry | `horizon`, `output_schema`, `confidence_scale`, `model_id` |
| Policy Registry | `policy_rules`, `risk_limits`, `modes` (paper/live) |
| Prompt Registry | `template`, `provider_hints`, `variables`, `response_schema_ref` |
| Artifact Registry | índice maestro de tipos + puntero al registry especializado |

---

## 5. Artifact Type IDs (`ART-*`)

Usar en ADR, RFC, matrices, manifests y trazabilidad.

| ART-* | Nombre | Clase (§7) |
|-------|--------|------------|
| `ART-DATASOURCE` | Datasource | Data |
| `ART-DATASET` | Dataset | Data |
| `ART-ASSET` | Asset / Instrument ref | Business |
| `ART-UNIVERSE` | Universe (lista/universo de scan) | Business |
| `ART-CALENDAR` | Trading calendar / session rules | Data |
| `ART-CORP-ACTION` | Corporate action | Data |
| `ART-OHLCV` | OHLCV series / bar set | Data |
| `ART-FEATURE-DEF` | FeatureDefinition | Data / ML |
| `ART-FEATURE-SET` | FeatureSet | Data / ML |
| `ART-FEATURE-SNAP` | FeatureSnapshot / FeatureValue batch | Data / ML |
| `ART-PREDICTION` | Prediction (instancia) | ML |
| `ART-PRED-BATCH` | PredictionBatch | ML |
| `ART-PRED-SPEC` | PredictionSpec (contrato de salida) | ML |
| `ART-SIGNAL` | Signal | Trading |
| `ART-RECOMMENDATION` | Recommendation | Trading |
| `ART-INTENT` | Intent (OrderIntent) | Trading |
| `ART-ORDER` | Order | Trading |
| `ART-TRADE` | Trade (fill cartera) | Trading |
| `ART-BT-TRADE` | BacktestTrade | Research |
| `ART-POSITION` | Position | Trading |
| `ART-PORTFOLIO-SNAP` | PortfolioSnapshot | Trading |
| `ART-RISK-REPORT` | RiskReport | Trading / Monitoring |
| `ART-STRATEGY` | StrategyDefinition | Trading / Strategy |
| `ART-INDICATOR` | Indicator (catalog/chart spec) | Trading |
| `ART-RULE` | Rule / RuleGroup (si versionado aparte) | Strategy |
| `ART-BACKTEST` | BacktestRun | Research |
| `ART-WALKFORWARD` | WalkForwardRun | Research |
| `ART-OPTIMIZE` | OptimizationRun | Research |
| `ART-EXPERIMENT` | Experiment | Research / ML |
| `ART-MODEL` | Model | ML |
| `ART-MODEL-VER` | ModelVersion | ML |
| `ART-PROMPT` | Prompt / PromptTemplate | AI |
| `ART-DRAFT` | Draft (authoring candidate) | AI |
| `ART-LLM-CALL` | LLMCall (audit record) | AI / Monitoring |
| `ART-POLICY` | Policy (genérico) | Trading |
| `ART-EXEC-POLICY` | ExecutionPolicy | Trading |
| `ART-POS-POLICY` | PositionPolicy | Trading |
| `ART-SCAN` | Scan job / run | Trading |
| `ART-TRACKER` | TrackerDefinition | Trading |
| `ART-ALERT` | Alert subscription / fired alert | Monitoring |
| `ART-MANIFEST` | Manifest (Scan/Run/…) | Monitoring |
| `ART-EVENT` | PlatformEvent | Monitoring |
| `ART-METRIC` | Metric definition / sample | Monitoring |
| `ART-AUDIT` | AuditRecord | Monitoring |
| `ART-REPORT` | Report | Business |
| `ART-DASHBOARD` | Dashboard / workspace view config | Infrastructure |
| `ART-BENCHMARK` | BenchmarkResult | Research |

Tipos futuros se añaden por **enmienda** a este RFC (no inventar `ART-*` ad hoc en código).

---

## 6. Catálogo por clase (universo conceptual)

El catálogo describe el **universo**, no solo lo implementado hoy. Columna **Hoy** = presencia en repo.

### 6.1 Data artifacts

| ART-* | Descripción | Hoy |
|-------|-------------|-----|
| `ART-DATASOURCE` | Proveedor (Yahoo, XTB, …) | Parcial (config) |
| `ART-DATASET` | Snapshot inmutable para train/BT | Parcial (`DataSnapshotRef` diseño) |
| `ART-OHLCV` | Serie de barras | ✅ PG |
| `ART-CORP-ACTION` | Split/dividendo | Parcial |
| `ART-CALENDAR` | Sesiones / festivos | ❌ |
| `ART-FEATURE-DEF` | Definición versionada de feature | Parcial (`IndicatorSpec` como proxy) |
| `ART-FEATURE-SET` | Conjunto de defs + hash | Parcial (hash en cache) |
| `ART-FEATURE-SNAP` | Valores materializados | ✅ FeatureCache (adapter online) |

### 6.2 ML / Research artifacts

| ART-* | Descripción | Hoy |
|-------|-------------|-----|
| `ART-MODEL` / `ART-MODEL-VER` | Modelo + versión | ❌ registry |
| `ART-PRED-SPEC` | Contrato de predicción | ❌ |
| `ART-PREDICTION` / `ART-PRED-BATCH` | Instancias / lotes | ❌ (scores heurísticos sin envelope) |
| `ART-EXPERIMENT` | Experimento ML/opt | Parcial (optimization runs) |
| `ART-BACKTEST` | Run de backtest | ✅ |
| `ART-BT-TRADE` | Trade de backtest | ✅ |
| `ART-WALKFORWARD` | Walk-forward run | ❌ |
| `ART-OPTIMIZE` | Optimization run | ✅ parcial |
| `ART-BENCHMARK` | Métricas vs benchmark | Parcial |

### 6.3 Trading / Strategy / Portfolio / Execution

| ART-* | Descripción | Hoy |
|-------|-------------|-----|
| `ART-ASSET` / `ART-UNIVERSE` | Instrumento / universo | ✅ Instrument, lists |
| `ART-STRATEGY` | StrategyDefinition | ✅ |
| `ART-INDICATOR` | Indicator de catálogo/chart | ✅ |
| `ART-SIGNAL` | SignalEvent | ✅ |
| `ART-RECOMMENDATION` | Recommendation de portfolio | ❌ |
| `ART-INTENT` | OrderIntent | ❌ |
| `ART-ORDER` | Order | ✅ PendingOrder |
| `ART-TRADE` | Fill cartera | Parcial (ledger/transactions) |
| `ART-POSITION` | Position | ✅ |
| `ART-PORTFOLIO-SNAP` | Snapshot cartera | Parcial |
| `ART-RISK-REPORT` | Informe de riesgo | ❌ |
| `ART-EXEC-POLICY` / `ART-POS-POLICY` | Políticas | ✅ |
| `ART-TRACKER` / `ART-SCAN` | Tracker / scan | ✅ |
| `ART-ALERT` | Alertas | ✅ parcial |

### 6.4 AI / Governance / Monitoring

| ART-* | Descripción | Hoy |
|-------|-------------|-----|
| `ART-PROMPT` | PromptTemplate | ❌ |
| `ART-DRAFT` | Draft authoring | ✅ APIs draft |
| `ART-LLM-CALL` | Auditoría llamada LLM | ❌ formal |
| `ART-MANIFEST` | Manifests | ✅ |
| `ART-EVENT` | PlatformEvent | ✅ |
| `ART-METRIC` / `ART-AUDIT` / `ART-REPORT` | Obs / audit / reports | Parcial |
| `ART-DASHBOARD` | Workspace UI persistido | ✅ workspace |

---

## 7. Clasificación de artefactos

| Clase | Ejemplos ART-* |
|-------|----------------|
| **Business** | `ART-ASSET`, `ART-UNIVERSE`, `ART-REPORT` |
| **Trading** | Signal → Position, Strategy, Tracker, Policies |
| **Data** | Datasource, Dataset, OHLCV, Feature\* |
| **ML** | Model, Prediction\*, Experiment, Benchmark |
| **AI** | Prompt, Draft, LLMCall |
| **Research** | Backtest, WalkForward, Optimize, BT-Trade |
| **Infrastructure** | Dashboard/workspace config, storage adapter config |
| **Monitoring** | Manifest, Event, Metric, Audit, Alert |

---

## 8. Artifact Graph (DAG canónico)

Grafo de negocio (simplificado). Edges = `dependencies` / lineage.

```
Datasource
    → Dataset / OHLCV (+ CorporateAction, Calendar)
        → FeatureDefinition → FeatureSet → FeatureSnapshot
            → Dataset (train) → Model / ModelVersion
                → Prediction / PredictionBatch
        → StrategyDefinition (+ Indicator)
            → Signal
                → Recommendation  ← (Prediction opcional)
                    → Intent  ← (Policy gate)
                        → Order → Trade → Position
                            → PortfolioSnapshot → Dashboard / Report

BacktestRun / OptimizationRun / WalkForwardRun
    → consumen Dataset + Strategy (+ Model opcional)
    → producen Manifest + BenchmarkResult + BT-Trade

Draft (AI) → (humano) → StrategyDefinition | FeatureDefinition | Indicator
Prompt + LLMCall → auditan el Draft
```

### 8.1 Invariantes del grafo (refuerzo RFC-000)

1. Un **Model** no depende directamente de OHLCV crudo; depende de **FeatureSet** (+ Dataset).
2. **Signal** no *es* una Prediction; la Prediction alimenta **Recommendation** (opcionalmente el hybrid score se modela como Prediction con `modelId` determinista).
3. **Intent** siempre desde **Recommendation** aprobada; nunca Signal→Order ni LLM→Order.
4. **Manifest** referencia el closure de artefactos usados en un run (ids+versions+checksums).

### 8.2 Ejemplo de lineage de una Recommendation

```
ART-OHLCV@snap_… 
  → ART-FEATURE-SET@fs_… 
    → ART-PREDICTION@pred_… (MODEL.LGBM_… o technical_rating_v1)
  → ART-STRATEGY@… → ART-SIGNAL@…
    → ART-RECOMMENDATION@…
```

---

## 9. Payloads tipados (mínimos)

Campos **además** del envelope. Contratos TS formales → Fases F2–F3 / shared.

### 9.1 `ART-PREDICTION` (`PredictionV1`)

`value`, `confidence`, `modelId`, `featureSetHash`, `horizon`, `timestamp`, `instrumentId?`

### 9.2 `ART-RECOMMENDATION` (`RecommendationV1`)

`signalIds[]`, `predictionIds[]?`, `side`, `suggestedSize`, `confidence`, `accountScope?`

### 9.3 `ART-INTENT` (`OrderIntentV1`)

`recommendationId`, `status` (`Pending` \| `Approved` \| `Rejected`), `approvedBy` (`human` \| `policy:<id>`), `expiresAt?`

### 9.4 `ART-FEATURE-DEF`

`compute_key` / formula ref, `params`, `inputs[]`, `output_dtype`, `parity_ref?` (indicator id si aplica)

### 9.5 `ART-MODEL` / `ART-MODEL-VER`

`algorithm`, `metrics`, `feature_set_id`, `training_dataset_id`, `artifact_uri` (via storage adapter)

### 9.6 `ART-PROMPT`

`template`, `variables[]`, `response_schema_ref`, `provider_hints`

### 9.7 `ART-EXEC-POLICY`

Ya parcialmente en `ExecutionPolicyV1` — envolver con envelope cuando entre en Policy Registry.

---

## 10. Mapeo a código y persistencia actual

| ART-* | Código / persistencia hoy | Acción (no bloquea aprobación) |
|-------|---------------------------|--------------------------------|
| `ART-OHLCV` | `ohlcv_bars` / entities | ✅ |
| `ART-FEATURE-DEF` | `IndicatorSpec` (+ compute Python) | Convivencia; registry futuro |
| `ART-FEATURE-SNAP` | `FeatureCache` | Reclasificar → OnlineFeatureAdapter |
| `ART-STRATEGY` | `StrategyDefinitionV1` + Prisma | ✅ + envelope opcional después |
| `ART-SIGNAL` | `SignalEventV1` | ✅ |
| `ART-RECOMMENDATION` | — (`Instrument.recommendation` ≠ esto) | Crear cuando Portfolio Engine |
| `ART-INTENT` | — | Crear antes de supervisado/auto |
| `ART-ORDER` | `PendingOrder` | ✅ |
| `ART-BT-TRADE` | `BacktestTrade` | ✅ |
| `ART-TRADE` | `Transaction` / fills | Aclarar en implementación OMS |
| `ART-POSITION` | `Position` | ✅ |
| `ART-BACKTEST` | `BacktestRun` | ✅ |
| `ART-OPTIMIZE` | optimization runs | Parcial |
| `ART-TRACKER` / `ART-SCAN` | Tracker + scan jobs | ✅ |
| `ART-EXEC-POLICY` / `ART-POS-POLICY` | policies V1 | ✅ |
| `ART-MANIFEST` | Scan/Run manifests | ✅ |
| `ART-EVENT` | `PlatformEvent` | ✅ |
| `ART-DRAFT` | draft-from-prompt APIs | ✅ sin registry |
| `ART-PROMPT` / `ART-MODEL` / `ART-PREDICTION` | — | Tras registries |

### 10.1 Persistencia target (no inmediato)

Tabla/índice maestro opcional `artifact_registry` (o equivalente) con el envelope + `payload` JSON **cuando** se implementen registries.  
**Prohibido** bloquear el desarrollo actual exigiendo esa tabla antes de RFC-005/007.  
Los artefactos efímeros (Signal, Recommendation en hot path) pueden persistirse en tablas propias **siempre que** puedan proyectarse al envelope para auditoría/manifests.

---

## 11. Registries y el Artifact System

```
Artifact Registry (catálogo de tipos + índice)
        │
        ├── Feature Registry      (ART-FEATURE-*)
        ├── Model Registry        (ART-MODEL*)
        ├── Prediction Registry   (ART-PRED*)
        ├── Policy Registry       (ART-*-POLICY, ART-POLICY)
        ├── Prompt Registry       (ART-PROMPT)
        └── (otros índices por clase)
```

Cada registry:

1. Usa el **mismo envelope** (§4).
2. Valida `type` ∈ catálogo §5.
3. Enforce lifecycle §3 y regla de dependencias §3.1.
4. Delega bytes a **storage adapters**.

---

## 12. Criterios de aceptación (ejecutables)

- [x] Existe este RFC en `docs/rfc/001-artifact-catalog.md`.
- [x] Lifecycle alineado con RFC-000 (+ flag `disabled`).
- [x] Envelope común documentado para todos los registries.
- [x] Catálogo `ART-*` exhaustivo (universo conceptual).
- [x] Artifact Graph + invariantes documentados.
- [x] Mapeo honesto a código actual (§10).
- [ ] (Posterior) Schemas JSON/Pydantic del envelope en repo + test de validación.
- [ ] (Posterior) Al menos un artefacto existente (p. ej. StrategyDefinition) exportable como envelope en un manifest.

---

## 13. Qué no hace este RFC

- No implementa Feast/MLflow/Kubeflow.
- No obliga a renombrar `IndicatorSpec` → `FeatureDefinition` de inmediato (RFC-000 convivencia).
- No redefine la cadena Trading (eso es RFC-000).
- No asigna owners/SLA/tiers (eso es **RFC-002 Capability Map**).

---

## 14. Próximo paso

**RFC-002 — Capability Map + Domain Registry + Capability Matrix**  
(owner, tier, SLA, `CAP-*`, qué registry custodia cada `ART-*`).

Paralelo suave permitido: Ollama authoring contra validators actuales, sin nuevos `ART-*` en API hasta existir contrato shared.

---

## 15. Enmiendas

Nuevos `ART-*` o cambios al envelope requieren PR a este RFC. Cambios de lifecycle requieren acuerdo con RFC-000.

---

*Integra: Artifact System (A1), envelope/lifecycle/grafo (A1+A2), catálogo por dominio (A3), mapeo real al repo. Aprobado para constitución 2026-07-21.*
