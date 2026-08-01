---
id: rfc-003
title: Platform Architecture
status: approved
date: 2026-07-21
audience: development, data, ml, ops, product
complements:
  - docs/rfc/000-ubiquitous-language.md
  - docs/rfc/001-artifact-catalog.md
  - docs/rfc/002-capability-model.md
  - docs/adr/010-platform-kernel-radar-execution.md
  - docs/AI_PLATFORM_SOLUTION.md
---

# RFC-003: Platform Architecture

> **Propósito:** Mostrar **cómo se conectan** los conceptos ya definidos (RFC-000…002): principios, capas 0–8, planos de ejecución, hot/research/AI paths, Event Bus, interfaces y anti-patrones.  
> **Principio:** Este RFC **no introduce semántica nueva**. Solo fronteras, flujos y contratos de comunicación.  
> **Alcance:** Arquitectura de referencia. Schemas detallados → RFC-006; reglas de import/CI → RFC-004.

---

## 1. Architecture Principles

| Principio | Significado operativo |
|-----------|----------------------|
| **Domain First** | El diseño parte de Domain / Capability / Artifact (RFC-000…002), no de frameworks. |
| **Deterministic Core** | Indicadores, PnL, backtest, rules y fills: motor determinista. |
| **AI Outside Critical Path** | LLM solo en authoring/explanation vía `AIGOV`; nunca en OMS/hot path. |
| **Registry Driven** | Definiciones viven en registries + envelope (RFC-001); storage = adapters. |
| **Event Friendly** | Flujos largos desacoplados por eventos tipados; CRUD puntual por API. |
| **Adapter Based** | Dominio no conoce Redis/PG/Parquet/broker SDK; solo interfaces. |
| **Replaceability** | Cambiar LightGBM, Ollama, Redis o broker no rediseña el dominio. |
| **Auditability** | Toda decisión material (Signal→Trade) deja Manifest / PlatformEvent / checksums. |

---

## 2. Context Map (dominios)

```
MARKET / DATA
      ↓
   FEATURE
      ↓
   RUNTIME ──────┐
      ↓          │ Prediction (opcional)
   STRATEGY      │
      ↓ Signal   │
   PORTFOLIO ◄───┘
      ↓ Recommendation
    POLICY
      ↓ Intent
   EXECUTION
      ↓ Order / Trade / Position

RESEARCH ↔ MODEL (artefactos offline → Production)

AIGOV ──► Draft specs ──► STRATEGY / FEATURE   (nunca ► EXECUTION)

OBS ◄── escucha / manifiesta a todos
UI  ◄──► APIs (cliente; no es capa de cálculo)
```

Dependencias permitidas/prohibidas: [RFC-002 §2.3](./002-capability-model.md).

---

## 3. Capas 0–8

```
8  MLOps & Observability     OBS / MODEL
7  AI Governance             AIGOV
6  Execution Engine          EXECUTION + POLICY (gate)
5  Portfolio Engine          PORTFOLIO
4  Strategy Engine (Kernel)  STRATEGY
3  Quant Runtime             RUNTIME
2  Quant Research            RESEARCH
1  Data Platform             DATA / FEATURE / MARKET
0  Infrastructure            INFRA
```

### 3.1 Por capa

| Capa | Responsabilidad | Caps principales | Produce | Consume | Depende de | Prohibido |
|------|-----------------|------------------|---------|---------|------------|-----------|
| **0 INFRA** | PG, Redis, colas, secrets, auth base, filesystem/MinIO | — | infra | — | — | lógica de negocio |
| **1 DATA** | Ingesta, snapshots, Feature Registry + adapters | `CAP-DATA-*`, `CAP-FEAT-*` | OHLCV, FEATURE-*, DATASET | Datasource | 0 | STRATEGY/PORTFOLIO/EXEC/AIGOV |
| **2 RESEARCH** | BT, optimize, train | `CAP-QUANT-BT/OPT/TRAIN` | BACKTEST, MODEL, OPTIMIZE | DATASET, STRATEGY, FEATURE-SET | 0–1 | EXECUTION live |
| **3 RUNTIME** | Inferencia / ranking | `CAP-QUANT-INFER` | PREDICTION | MODEL, FEATURE-SNAP | 0–1 (+ MODEL) | EXECUTION, AIGOV |
| **4 STRATEGY** | Rules → Signal; trackers/scans | `CAP-STRAT-EVAL/TRACK` | SIGNAL, SCAN, TRACKER | STRATEGY, FEATURE-SNAP (+ PREDICTION en track) | 0–1,(3) | EXECUTION, AIGOV, UI |
| **5 PORTFOLIO** | Recommendation, sizing, portfolio view | `CAP-PORT-RECOM/POS` | RECOMMENDATION, PORTFOLIO-SNAP | SIGNAL, PREDICTION? | 0–1,3–4 | broker SDK, AIGOV hot |
| **6 EXECUTION** | Policy gate, Intent, OMS, adapters | `CAP-POLICY-GATE`, `CAP-EXEC-*` | INTENT, ORDER, TRADE, POSITION | RECOMMENDATION, POLICY | 0,5 | RUNTIME/STRATEGY/AIGOV/FEATURE compute |
| **7 AIGOV** | Proxy LLM, authoring, explain | `CAP-AI-*` | DRAFT, PROMPT, LLM-CALL | schemas | 0 | EXECUTION |
| **8 OBS** | Manifests, events, métricas, audit | `CAP-OBS-*` | MANIFEST, EVENT, METRIC | lectura todos | 0 | no bloquea hot path |

Interfaces públicas de capa = APIs FastAPI + eventos §6 + puertos §7. Detalle de schemas → RFC-006.

---

## 4. Planos de ejecución

Tres planos operativos (alineados ADR-010) + plano de observabilidad:

### 4.1 Research Plane (Tier 2, offline / batch)

| | |
|--|--|
| **Hace** | Train, Optimize, WalkForward, Experiments, Backtest, Authoring jobs |
| **Caps** | `CAP-QUANT-BT/OPT/TRAIN`, `CAP-AI-AUTH` (on-demand) |
| **Emite** | MODEL, STRATEGY candidates, BACKTEST, BENCHMARK — **no** Orders live |
| **Aislamiento** | Fallo de job ≠ afecta Radar/Execution |

### 4.2 Radar Plane (Tier 1, scan / track)

| | |
|--|--|
| **Hace** | Ingest → Feature → (Prediction) → Signal / scan ranking / alerts |
| **Caps** | `CAP-DATA-INGEST`, `CAP-FEAT-*`, `CAP-QUANT-INFER`, `CAP-STRAT-EVAL/TRACK` |
| **Emite** | SIGNAL, SCAN hits, ALERT — órdenes solo si se encadena a Execution bajo Policy |
| **Modo** | Cron / on-demand / worker |

### 4.3 Execution Plane (Tier 0, hot path)

| | |
|--|--|
| **Hace** | Recommendation → Policy → Intent → OMS → Paper/Live → Trade → Position |
| **Caps** | `CAP-PORT-RECOM`, `CAP-POLICY-GATE`, `CAP-EXEC-OMS/BROKER` |
| **Invariante** | Cero LLM; cero SDK OpenAI/Ollama; entrada por Intent autorizado |

### 4.4 Observability Plane (transversal)

| | |
|--|--|
| **Hace** | Events, Metrics, Audit, Manifests |
| **Caps** | `CAP-OBS-*` |
| **Modo** | Escucha bus + escribe manifests; no decide trades |

```
        RESEARCH PLANE
              │ ART-MODEL / ART-STRATEGY (Production)
              ▼
        RADAR PLANE ──Signal──► EXECUTION PLANE
              │                        │
              └──────── OBS ◄──────────┘
```

---

## 5. Paths canónicos (sin semántica nueva)

### 5.1 Hot Path (crítico)

```
OHLCV → Features → Prediction? → Signal → Recommendation
    → Policy → Intent → Order → Trade → Position
```

**Fuera del hot path:** LLM, UI rendering, dashboards, reports, train, notebooks.

### 5.2 Research Path

```
Dataset → FeatureSet → Train → Model → Benchmark
    → Production candidate (lifecycle RFC-001)
```

Nunca mezcla fills live con trades de backtest (`ART-BT-TRADE` ≠ `ART-TRADE`).

### 5.3 AI Path

```
Prompt → AIGovernanceProxy → LLM → Draft
    → Human review → Strategy / Feature / Indicator spec → Kernel
```

**Prohibido:** `LLM → Order` / `LLM → Intent` / `LLM → Execution`.

### 5.4 Supervised vs auto (producto)

| Modo | Tras Recommendation |
|------|---------------------|
| Supervisado | Humano aprueba Intent (UI) |
| Paper/Live auto | `CAP-POLICY-GATE` aprueba Intent si Policy `Production` + circuit breaker OK |

---

## 6. Event Bus (contratos, no implementación)

Hoy: persistencia `PlatformEvent` + workers/colas existentes. Target: bus interno (Redis pub/sub u otro) **sin** exigir Kafka.

### 6.1 Clases de evento

| Clase | Uso |
|-------|-----|
| **Domain events** | Hechos de negocio (`SignalRaised`, `IntentApproved`, …) |
| **Platform events** | Operativos/audit (`ManifestCompleted`, job lifecycle) |
| **Infrastructure events** | Salud/colas (fuera del lenguaje de trading) |

### 6.2 Envelope mínimo de evento

Alineado al envelope de artefacto (RFC-001) + tracing:

```yaml
eventId: string
eventType: string              # ver §6.3
domain: string                 # Domain ID
capability: string             # CAP-*
timestamp: datetime
traceId: string
checksum: string | null
payload: object                # tipado por eventType
artifactRefs:                  # ART-* tocados
  - { type: ART-*, id: string, version: string | null }
```

### 6.3 Catálogo inicial de domain events

| eventType | Emisor CAP-* | Payload (idea) |
|-----------|--------------|----------------|
| `MarketUpdated` | `CAP-DATA-INGEST` | instruments, timeframe, dataVersion |
| `FeaturesReady` | `CAP-FEAT-COMPUTE` / STORE | featureSetId, snapshotHash |
| `PredictionGenerated` | `CAP-QUANT-INFER` | modelId, predictionIds / batchId |
| `SignalRaised` | `CAP-STRAT-EVAL` | signalId (= SignalEventV1) |
| `RecommendationCreated` | `CAP-PORT-RECOM` | recommendationId |
| `IntentApproved` | `CAP-POLICY-GATE` | intentId, approvedBy |
| `IntentRejected` | `CAP-POLICY-GATE` | intentId, reason |
| `OrderSubmitted` | `CAP-EXEC-OMS` | orderId |
| `TradeFilled` | `CAP-EXEC-OMS` | tradeId, orderId |
| `PositionUpdated` | `CAP-EXEC-OMS` / `CAP-PORT-POS` | positionId |
| `ManifestCompleted` | `CAP-OBS-MANIFEST` | manifestId, closure |
| `DraftCreated` | `CAP-AI-AUTH` | draftId (fuera hot path) |

Compatibilidad: eventos existentes en `PlatformEventV1` / tipos ADR-010 se **mapean** a este catálogo; no se exige rename inmediato.

### 6.4 Flujo canónico en el bus

```
CAP-STRAT-EVAL        → SignalRaised
CAP-PORT-RECOM        → RecommendationCreated  (consulta Prediction si aplica)
CAP-POLICY-GATE       → IntentApproved | IntentRejected
CAP-EXEC-OMS          → OrderSubmitted → TradeFilled → PositionUpdated
CAP-OBS-MANIFEST      → ManifestCompleted
```

**Regla:** un dominio no inicia el hot path llamando REST interno al siguiente; emite evento (o use-case application orquesta en monólito **respetando** las mismas fronteras de import). En el monólito actual, la orquestación en `bolsa_application` es válida si no viola RFC-002 isolation.

---

## 7. Interfaces entre dominios (puertos)

Siempre contratos; nunca “llamar al FeatureCache interno” desde Strategy.

| Puerto | Consumidor | Proveedor | Contrato (nombre) |
|--------|------------|-----------|-------------------|
| Features | RUNTIME, STRATEGY | FEATURE | `IFeaturePort` / `IFeatureAdapter` — get snapshot by featureSet + instrument + time |
| Predictions | PORTFOLIO, STRAT-TRACK | RUNTIME | `IPredictionPort` — get/read Prediction by id or latest |
| Signals | PORTFOLIO | STRATEGY | eventos `SignalRaised` / read API |
| Recommendations | POLICY, UI | PORTFOLIO | evento + API |
| Intents | EXEC-OMS | POLICY | `IntentApproved` |
| Orders/Fills | PORTFOLIO/OBS | EXECUTION | `IBrokerAdapter` (Paper \| Live) |
| LLM | solo AIGOV clients | AIGOV | `AIGovernanceProxy.generate_structured_spec(...)` |

Implementaciones de adapter viven en infraestructura; dominio solo ve el puerto.

---

## 8. Deployment view (simple — no microservicios)

```
Browser (React / Vite)
        │ HTTPS / OpenAPI
        ▼
FastAPI (apps/api-python)     ← orquestación fina
        │
        ▼
bolsa_application             ← use cases / CAP orchestration
        │
   ┌────┴────┐
   ▼         ▼
domain    analytics / market / (futuro ai_*)
   │
   ▼
infrastructure → Postgres | Redis | Parquet/MinIO | Ollama (lado AIGOV) | Broker mock/live
        │
        ▼
Workers (Arq / inline) — Radar jobs, optimize, sync
```

Un solo deploy lógico es válido. Escalado horizontal de workers ≠ microservicios de dominio.

---

## 9. Sequence sketches

### 9.1 Radar scan (sin auto-trade)

```
Scheduler/UI → CAP-STRAT-TRACK
  → CAP-DATA-INGEST / features (cache)
  → CAP-QUANT-INFER? → CAP-STRAT-EVAL
  → SignalRaised / scan hits → UI + alerts
  → CAP-OBS-MANIFEST
```

### 9.2 Paper trading (auto bajo policy)

```
SignalRaised → RecommendationCreated
  → CAP-POLICY-GATE (paper_auto + circuit breaker)
  → IntentApproved → CAP-EXEC-OMS → PaperBrokerAdapter
  → TradeFilled → PositionUpdated → ManifestCompleted
```

### 9.3 Supervisado

```
RecommendationCreated → UI
  → humano POST Intent → approve
  → IntentApproved → OMS → …
```

### 9.4 Authoring (fuera hot path)

```
UI → CAP-AI-AUTH → CAP-AI-PROXY → Ollama|OpenAI
  → Draft → human promote → ART-STRATEGY / FEATURE-DEF
  → (opcional) CAP-QUANT-BT validate
```

---

## 10. Anti-patterns (prohibidos)

| ❌ | ✅ |
|---|---|
| `EXECUTION` → OpenAI/Ollama SDK | Solo `AIGOV` vía proxy |
| `STRATEGY` → Broker | `STRATEGY` → Signal; Execution aparte |
| `FEATURE` → OMS | Feature solo data/runtime/strategy inputs |
| `Signal` → `Order` | Signal → Recommendation → Intent → Order |
| `Prediction` → `Order` | Prediction → Recommendation (opcional) |
| `LLM` → `Order` / `Intent` | LLM → Draft → humano/registry |
| Runtime lee `FeatureCache` concreto | Runtime usa `IFeaturePort` |
| Mezclar Research fills con Position live | `ART-BT-TRADE` vs `ART-TRADE` |
| Dashboard en el critical path | UI fuera del hot path |

---

## 11. Relación con el monólito actual

| Elemento | Hoy | Target arquitectónico |
|----------|-----|------------------------|
| Planos | Mezcla en un proceso + workers | Mismos planos lógicos; isolation por imports/caps |
| Eventos | `PlatformEvent` persistido | Envelope §6 + más eventTypes |
| Features | `FeatureCache` | `IFeaturePort` + adapters |
| OMS | `PendingOrder` | `IBrokerAdapter` Paper/Live |
| LLM | `llm_*` en analytics | `AIGovernanceProxy` (F1) |
| Orquestación | `bolsa_application` | Permitida si respeta fronteras CAP/Domain |

---

## 12. Criterios de aceptación

- [x] RFC en `docs/rfc/003-architecture.md`
- [x] Principios + context map + capas 0–8
- [x] Planos Research / Radar / Execution / Obs
- [x] Hot / Research / AI paths
- [x] Event catalog + envelope (sin forzar Kafka)
- [x] Puertos adapter + anti-patterns
- [x] Deployment view monólito-first
- [ ] (Posterior) Schemas TS/Pydantic de eventos (RFC-006)
- [ ] (Posterior) Lint de imports (RFC-004)

---

## 13. Próximo paso

**RFC-004 — Engineering Handbook** (estructura de paquetes, imports `kernel ↛ ai_*`, adapters, tests, lint semántico, releases).

Paralelo suave: Ollama authoring síncrono; no requiere Event Bus completo.

---

## 14. Enmiendas

Nuevos planos o eventTypes de dominio requieren PR a este RFC. Nuevos Domain/CAP/ART siguen siendo enmiendas a 000–002.

---

*Síntesis A1 (principios, paths, anti-patterns) + A2 (capas/planos/adapters) + A3 (event flow/secuencias); sin conceptos fundamentales nuevos.*
