---
id: rfc-002
title: Capability Model & Domain Registry
status: approved
date: 2026-07-21
audience: development, product, data, ml, ops
complements:
  - docs/rfc/000-ubiquitous-language.md
  - docs/rfc/001-artifact-catalog.md
  - docs/AI_PLATFORM_SOLUTION.md
---

# RFC-002: Capability Model & Domain Registry

> **Propósito:** Definir **quién** es responsable de **qué**: Domain Registry, Capability IDs (`CAP-*`), Capability Matrix (produce/consume/registry), tiers/SLA y reglas de dependencia.  
> **Principio:** Si una capability no está mapeada, no es responsabilidad formal. Si un `ART-*` no tiene custodio `CAP-*`, no se puede auditar.  
> **Alcance:** Gobernanza organizativa. No implementa código; asigna fronteras verificables (lint futuro en RFC-004).

Complementa: [RFC-000](./000-ubiquitous-language.md), [RFC-001](./001-artifact-catalog.md).

---

## 1. Objetivo — jerarquía de conceptos

Para que nunca se mezclen:

```
Domain          (área de responsabilidad + límites)
  └── Capability   (unidad funcional CAP-* medible)
        └── Component   (módulo/paquete/servicio en código)
              └── Artifact   (ART-* producido o consumido)
```

| Concepto | Pregunta que responde | Ejemplo |
|----------|----------------------|---------|
| **Domain** | ¿De quién es el problema? | `EXECUTION` |
| **Capability** | ¿Qué capacidad ofrece? | `CAP-EXEC-OMS` |
| **Component** | ¿Dónde vive en el repo? | `pending_order_repository.py` |
| **Registry** | ¿Dónde se cataloga el artefacto? | Policy Registry |
| **Artifact** | ¿Qué objeto versionado/auditable? | `ART-ORDER` |

---

## 2. Domain Registry

Domain IDs **canónicos** = [RFC-000 §2](./000-ubiquitous-language.md). No inventar sinónimos (`DOM-EXEC` informal → usar `EXECUTION` en docs/código nuevo).

### 2.1 Tiers de criticidad

| Tier | Nombre | Disponibilidad orientativa | RTO orientativo | Impacto de fallo |
|------|--------|----------------------------|-----------------|------------------|
| **0** | Critical hot-path | 99.95% | &lt; 1 min | Órdenes erróneas, desacople broker/paper, pérdida financiera |
| **1** | Core operations | 99.5% | &lt; 15 min | Señales, cartera, datos/features críticos |
| **2** | Analytics & research | 99.0% | &lt; 2 h | BT, train, authoring, inferencia batch |
| **3** | Auxiliary / UX | 95% | best effort | Dashboard, reports no críticos, métricas UI |

**Regla:** Un artefacto `Production` Tier 0 **no** puede depender en caliente de un artefacto Tier 2/3 sin caché/réplica local o degradación definida.

### 2.2 Tabla maestra de dominios

| Domain ID | Tier | Capa* | Owner (rol) | Responsabilidad | Límites (no hace) |
|-----------|------|-------|-------------|-----------------|-------------------|
| `INFRA` | 0–1 | 0 | Platform | PG, Redis, colas, secrets, auth base | Lógica de trading |
| `MARKET` / `DATA` | 1 | 1 | Data | Ingesta, OHLCV, corp actions, snapshots | Señales, órdenes |
| `FEATURE` | 1 | 1+3 | Data/Quant | Feature Registry, compute, adapters | Órdenes, LLM |
| `RESEARCH` | 2 | 2 | Quant | Backtest, optimize, train offline | Live OMS |
| `RUNTIME` | 1–2 | 3 | ML/Quant | Inferencia, scoring, ranking | Broker, Intent |
| `STRATEGY` | 1 | 4 | Platform/Quant | Kernel: rules → Signal; trackers | Recommendation, Order |
| `PORTFOLIO` | 1 | 5 | Quant/Risk | Recommendation, sizing, portfolio view | Envío a broker |
| `TRADING` | — | transversal | — | Vocabulario Signal…Position (no es un deployable) | — |
| `EXECUTION` | 0 | 6 | Trading Ops | Intent approval, OMS, paper/broker adapters | LLM, Feature compute |
| `POLICY` | 0–1 | 5–6 | Risk/Ops | Execution/Position policies, circuit breakers | Authoring |
| `MODEL` / `OBS` | 2 | 8 | MLOps | Model registry, manifests, events, audit | Hot-path OMS |
| `AI` / `AIGOV` | 2 | 7 | AI/Platform | Proxy LLM, authoring, explanation, prompts | Execution, Kernel imports |
| `UI` | 3 | transversal | Product | Workspace, charts, confirmaciones humanas | Cálculo de PnL/server |

\*Capas 0–8 = [AI_PLATFORM_SOLUTION §3](../AI_PLATFORM_SOLUTION.md).

**Owners hoy:** en proyecto individual, el mismo humano ocupa varios roles; los nombres de rol siguen siendo obligatorios para no dejar el conocimiento implícito.

### 2.3 Dependencias permitidas entre dominios

| Desde \ Hacia | Puede depender de | **Prohibido** |
|---------------|-------------------|---------------|
| `INFRA` | — (base) | Dominios de negocio |
| `DATA` / `MARKET` | `INFRA` | `STRATEGY`, `PORTFOLIO`, `EXECUTION`, `AIGOV` |
| `FEATURE` | `DATA`, `INFRA` | `TRADING` runtime, `EXECUTION`, `AIGOV` |
| `RESEARCH` | `DATA`, `FEATURE`, `INFRA` | `EXECUTION` |
| `RUNTIME` | `FEATURE`, `MODEL`/`RESEARCH` (artefactos), `INFRA` | `EXECUTION`, `AIGOV` |
| `STRATEGY` | `FEATURE`, `DATA`, `INFRA` (+ Prediction **solo** vía capacidades de ranking/tracker, no en Kernel puro de Signal) | `EXECUTION`, `AIGOV`, `UI` |
| `PORTFOLIO` | `STRATEGY` (Signal), `RUNTIME` (Prediction), `POLICY`, `DATA` | Llamadas broker; `AIGOV` en hot path |
| `EXECUTION` | `PORTFOLIO` (Intent), `POLICY`, `INFRA` | `RUNTIME`, `STRATEGY`, `AIGOV`, `FEATURE` compute |
| `AIGOV` | Lectura de specs/schemas; `INFRA` | `EXECUTION` (nunca envía órdenes) |
| `OBS` | Lectura de todos (métricas/eventos) | Bloquear hot-path |
| `UI` | APIs de todos (cliente) | Implementar reglas de trading en servidor |

Expresado en cadena de producto:

```
DATA → FEATURE → RUNTIME → STRATEGY → PORTFOLIO → EXECUTION
                     ↘ RESEARCH (offline)
AIGOV ──authoring──► STRATEGY / FEATURE specs   (nunca ► EXECUTION)
```

---

## 3. Capability Registry (`CAP-*`)

IDs **estables**; no se renombran (solo se deprecan). Prefijo `CAP-`.

### 3.1 Catálogo

| CAP-* | Nombre | Domain | Tier | Inputs (ART/otros) | Outputs (ART) | Registry / store |
|-------|--------|--------|------|--------------------|---------------|------------------|
| `CAP-DATA-INGEST` | Market ingestion | `DATA` | 1 | Datasource | `ART-OHLCV` | Data |
| `CAP-DATA-SYNC` | Corp actions / sync | `DATA` | 1 | Datasource | `ART-CORP-ACTION` | Data |
| `CAP-DATA-SNAPSHOT` | Data snapshots | `DATA` | 1 | OHLCV | `ART-DATASET` | Data |
| `CAP-FEAT-CATALOG` | Feature catalog | `FEATURE` | 1 | — | `ART-FEATURE-DEF`, `ART-FEATURE-SET` | Feature Registry |
| `CAP-FEAT-COMPUTE` | Feature compute | `FEATURE` | 1 | DEF, OHLCV | values → SNAP | Feature Registry |
| `CAP-FEAT-STORE` | Online/offline adapters | `FEATURE` | 1 | SNAP | SNAP (persist) | Adapters |
| `CAP-QUANT-BT` | Backtest engine | `RESEARCH` | 2 | STRATEGY, DATASET | `ART-BACKTEST`, `ART-BT-TRADE` | Research |
| `CAP-QUANT-OPT` | Optimization | `RESEARCH` | 2 | STRATEGY, DATASET | `ART-OPTIMIZE` | Research |
| `CAP-QUANT-TRAIN` | Tabular train | `RESEARCH` | 2 | FEATURE-SET, DATASET | `ART-MODEL` | Model Registry |
| `CAP-QUANT-INFER` | Prediction runtime | `RUNTIME` | 1 | MODEL, FEATURE-SNAP | `ART-PREDICTION` | Prediction Registry |
| `CAP-STRAT-EVAL` | Strategy / signal engine | `STRATEGY` | 1 | STRATEGY, FEATURE-SNAP | `ART-SIGNAL` | Kernel |
| `CAP-STRAT-TRACK` | Tracker / scan radar | `STRATEGY` | 1–2 | STRATEGY, SIGNAL, PREDICTION? | `ART-SCAN`, hits | Kernel |
| `CAP-PORT-RECOM` | Sizing & recommendation | `PORTFOLIO` | 1 | SIGNAL, PREDICTION? | `ART-RECOMMENDATION` | Portfolio |
| `CAP-PORT-POS` | Positions & ledger view | `PORTFOLIO` | 1 | TRADE, POSITION | `ART-PORTFOLIO-SNAP` | Portfolio |
| `CAP-POLICY-GATE` | Risk / circuit breaker | `POLICY`/`EXECUTION` | 0 | RECOMMENDATION, POLICY | `ART-INTENT` (approved) | Policy Registry |
| `CAP-EXEC-OMS` | Order management | `EXECUTION` | 0 | INTENT | `ART-ORDER`, `ART-TRADE` | Execution |
| `CAP-EXEC-BROKER` | Broker / paper adapter | `EXECUTION` | 0 | ORDER | fills → TRADE/POSITION | Execution |
| `CAP-AI-PROXY` | AIGovernanceProxy | `AIGOV` | 2 | PROMPT | routed LLM I/O | Prompt Registry |
| `CAP-AI-AUTH` | Authoring | `AIGOV` | 2 | PROMPT | `ART-DRAFT` | Prompt / Draft |
| `CAP-AI-EXPLAIN` | Explanation | `AIGOV` | 3 | Prediction/Reco (read) | narrativa + `ART-LLM-CALL` | AIGOV |
| `CAP-OBS-MANIFEST` | Manifests & lineage | `OBS` | 2 | closure ART-* | `ART-MANIFEST` | Obs |
| `CAP-OBS-AUDIT` | Audit trail | `OBS` | 2 | events | `ART-EVENT`, `ART-AUDIT` | Obs |
| `CAP-OBS-MONITOR` | Metrics / alerts ops | `OBS` | 2–3 | — | `ART-METRIC`, `ART-ALERT` | Obs |

Adelantos RFC-000 (`CAP-BACKTEST`, etc.) se consideran **aliases** de los IDs de esta tabla (`CAP-QUANT-BT` ≡ backtest). En código/docs nuevos preferir la tabla §3.1.

### 3.2 Campos obligatorios por capability (registro)

Cada `CAP-*` documenta (YAML futuro / esta tabla ampliada):

- `id`, `name`, `domain`, `tier`
- `technical_owner`, `business_owner` (roles)
- `sla` (hereda del tier salvo override)
- `consumes` / `produces` (`ART-*`)
- `dependencies` (`CAP-*` / domains)
- `criticality` notes

---

## 4. Capability Matrix (referencia diaria)

Vista compacta produce / consume / custodia:

| Capability | Produce (custodia) | Consume | Registry / adapter |
|------------|-------------------|---------|---------------------|
| `CAP-DATA-INGEST` | `ART-OHLCV` | Datasource | Data |
| `CAP-FEAT-CATALOG` | `ART-FEATURE-DEF`, `ART-FEATURE-SET` | — | Feature Registry |
| `CAP-FEAT-COMPUTE` | valores de feature | DEF, OHLCV | — |
| `CAP-FEAT-STORE` | `ART-FEATURE-SNAP` | valores | Online/Offline adapters |
| `CAP-QUANT-TRAIN` | `ART-MODEL` | FEATURE-SET, DATASET | Model Registry |
| `CAP-QUANT-INFER` | `ART-PREDICTION` | MODEL, FEATURE-SNAP | Prediction Registry |
| `CAP-QUANT-BT` | `ART-BACKTEST`, `ART-BT-TRADE` | STRATEGY, DATASET | Research |
| `CAP-STRAT-EVAL` | `ART-SIGNAL` | STRATEGY, FEATURE-SNAP | Kernel |
| `CAP-STRAT-TRACK` | `ART-SCAN`, ranking hits | STRATEGY, SIGNAL, PREDICTION? | Kernel |
| `CAP-PORT-RECOM` | `ART-RECOMMENDATION` | SIGNAL, PREDICTION? | Portfolio |
| `CAP-POLICY-GATE` | `ART-INTENT` | RECOMMENDATION, POLICY | Policy Registry |
| `CAP-EXEC-OMS` | `ART-ORDER`, `ART-TRADE` | INTENT | Execution |
| `CAP-AI-AUTH` | `ART-DRAFT` | PROMPT | Prompt Registry |
| `CAP-AI-PROXY` | (I/O gobernado) | PROMPT | AIGOV |
| `CAP-OBS-MANIFEST` | `ART-MANIFEST` | closure del run | Obs |

### 4.1 Custodia unívoca (invariante)

Para cada `ART-*` de producción hay **un custodio primario** `CAP-*` que puede crear/mutar el artefacto. Otros solo consumen o proyectan a manifests.

| ART-* | Custodio CAP-* | Domain |
|-------|----------------|--------|
| `ART-OHLCV` | `CAP-DATA-INGEST` | `DATA` |
| `ART-FEATURE-DEF` / `SET` | `CAP-FEAT-CATALOG` | `FEATURE` |
| `ART-FEATURE-SNAP` | `CAP-FEAT-STORE` | `FEATURE` |
| `ART-MODEL` | `CAP-QUANT-TRAIN` (+ gobernanza `OBS`/Model Registry) | `RESEARCH`/`MODEL` |
| `ART-PREDICTION` | `CAP-QUANT-INFER` | `RUNTIME` |
| `ART-STRATEGY` | `CAP-STRAT-EVAL` (CRUD vía application; eval en kernel) | `STRATEGY` |
| `ART-SIGNAL` | `CAP-STRAT-EVAL` | `STRATEGY` |
| `ART-RECOMMENDATION` | `CAP-PORT-RECOM` | `PORTFOLIO` |
| `ART-INTENT` | `CAP-POLICY-GATE` | `POLICY`/`EXECUTION` |
| `ART-ORDER` / `ART-TRADE` | `CAP-EXEC-OMS` | `EXECUTION` |
| `ART-POSITION` | `CAP-EXEC-OMS` / `CAP-PORT-POS` (lectura cartera) | `EXECUTION`/`PORTFOLIO` |
| `ART-EXEC-POLICY` | `CAP-POLICY-GATE` | `POLICY` |
| `ART-PROMPT` | `CAP-AI-PROXY` | `AIGOV` |
| `ART-DRAFT` | `CAP-AI-AUTH` | `AIGOV` |
| `ART-MANIFEST` | `CAP-OBS-MANIFEST` | `OBS` |
| `ART-BACKTEST` | `CAP-QUANT-BT` | `RESEARCH` |
| `ART-TRACKER` / `ART-SCAN` | `CAP-STRAT-TRACK` | `STRATEGY` |

Co-propiedad (train vs registry): RESEARCH produce el binario; `MODEL`/`OBS` custodia el **registro** y el lifecycle `Production`.

---

## 5. Relación Domain → Capabilities

```
DATA        → CAP-DATA-INGEST, CAP-DATA-SYNC, CAP-DATA-SNAPSHOT
FEATURE     → CAP-FEAT-CATALOG, CAP-FEAT-COMPUTE, CAP-FEAT-STORE
RESEARCH    → CAP-QUANT-BT, CAP-QUANT-OPT, CAP-QUANT-TRAIN
RUNTIME     → CAP-QUANT-INFER
STRATEGY    → CAP-STRAT-EVAL, CAP-STRAT-TRACK
PORTFOLIO   → CAP-PORT-RECOM, CAP-PORT-POS
POLICY      → CAP-POLICY-GATE
EXECUTION   → CAP-EXEC-OMS, CAP-EXEC-BROKER
AIGOV       → CAP-AI-PROXY, CAP-AI-AUTH, CAP-AI-EXPLAIN
OBS         → CAP-OBS-MANIFEST, CAP-OBS-AUDIT, CAP-OBS-MONITOR
```

---

## 6. Isolation rules (código)

Vinculantes; detalle de tooling en **RFC-004 Engineering Handbook**.

1. **`EXECUTION`, Kernel (`CAP-STRAT-EVAL`), `CAP-EXEC-OMS`** no importan paquetes `ai_*` / `AIGOV`.
2. **LLM solo** vía `CAP-AI-PROXY` (schemas/DTOs); nunca SDK OpenAI/Ollama desde Kernel/OMS.
3. **`CAP-EXEC-OMS`** solo acepta `ART-INTENT` emitidos/aprobados por `CAP-POLICY-GATE`.
4. **`FEATURE`** no importa módulos de trading (`STRATEGY`/`PORTFOLIO`/`EXECUTION`).
5. **`CAP-QUANT-INFER`** no conoce broker ni `ART-ORDER`.

---

## 7. Mapeo a módulos actuales (honesto)

| CAP-* | Ubicación actual (aprox.) | Target evolutivo (no obligatorio ahora) |
|-------|---------------------------|----------------------------------------|
| `CAP-DATA-INGEST` | `bolsa_market`, sync routes API | mantener; adapters claros |
| `CAP-FEAT-COMPUTE` | `bolsa_analytics` indicators/compute | Feature platform |
| `CAP-FEAT-STORE` | `bolsa_analytics/.../feature_cache.py` | `OnlineFeatureAdapter` |
| `CAP-QUANT-BT` | analytics backtest + API `/backtests` | — |
| `CAP-QUANT-OPT` | `bolsa_application/optimize.py` + workers | — |
| `CAP-QUANT-TRAIN` | — | F2+ |
| `CAP-QUANT-INFER` | scores heurísticos en analytics (rating) | Prediction runtime F2 |
| `CAP-STRAT-EVAL` | `bolsa_analytics.signals` + rules engine | — |
| `CAP-STRAT-TRACK` | scan/tracker application + workers | — |
| `CAP-PORT-RECOM` | — | F3 |
| `CAP-POLICY-GATE` | execution policies routes + domain entities | Intent F3–F4 |
| `CAP-EXEC-OMS` | `PendingOrder` + trading routes | OMS completo |
| `CAP-AI-PROXY` / `AUTH` | `bolsa_analytics.research.llm_*` | `ai_governance` F1 |
| `CAP-OBS-MANIFEST` | ScanManifest / RunManifest | — |
| `CAP-OBS-AUDIT` | `PlatformEvent` | — |

No se exigen renames de paquetes (`packages/strategy_engine/`, etc.) en este RFC.

---

## 8. Esqueleto YAML (materialización futura)

```yaml
# domain-registry.example.yaml — no runtime aún
domains:
  - id: EXECUTION
    tier: 0
    sla_availability: 99.95
    technical_owner: trading_ops
    business_owner: product
    capabilities: [CAP-EXEC-OMS, CAP-EXEC-BROKER]
    allowed_dependencies: [PORTFOLIO, POLICY, INFRA]
    prohibited_dependencies: [AIGOV, RUNTIME, STRATEGY, FEATURE]

capabilities:
  - id: CAP-PORT-RECOM
    domain: PORTFOLIO
    tier: 1
    produces: [ART-RECOMMENDATION]
    consumes: [ART-SIGNAL, ART-PREDICTION]
    dependencies: [CAP-STRAT-EVAL, CAP-QUANT-INFER]
```

---

## 9. Criterios de aceptación

- [x] RFC en `docs/rfc/002-capability-model.md`
- [x] Domain Registry con tiers/SLA y límites
- [x] Catálogo `CAP-*` estable
- [x] Capability Matrix + custodia `CAP-*` × `ART-*`
- [x] Reglas de dependencia / aislamiento
- [x] Mapeo honesto al repo actual
- [ ] (Posterior) YAML versionado + CI lint de imports (RFC-004)

---

## 10. Próximo paso

**RFC-003 — Architecture** (capas 0–8, planos Research/Radar/Execution, Event Bus, interfaces entre dominios).

Paralelo suave: Ollama authoring bajo `CAP-AI-*` sin tocar `EXECUTION`.

---

## 11. Enmiendas

Nuevos `CAP-*` o cambios de custodia `ART-*` requieren PR a este RFC. Cambios de Domain ID requieren acuerdo con RFC-000.

---

*Integra estructura A1 (Capability Model), matriz/custodia A2 y organigrama A3; Domain IDs alineados a RFC-000; sin paths de paquetes ficticios.*
