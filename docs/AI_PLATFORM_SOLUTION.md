# Bolsa V1 — Solución de plataforma + IA

> **Estado:** **CONSTITUCIÓN + NÚCLEO COGNITIVO** — RFC-000…008 aprobados.  
> **Estado:** F1/F1+ ✅ · F2 Feature Registry ✅ · `llm_calls` en PG local ✅ · import-linter ✅.  
> **Núcleo cognitivo:** [RFC-008](./rfc/008-cognitive-decision-architecture.md) (**approved**) — pipeline jerárquico Opportunity → Context → Evidence → Policy Gate (no comité LLM).  
> **Congelación IND-\*:** levantable (D2+ hecho).  
> **Hecho:** D0–D7 ✅ + PG cognitiva + Gate→Memory + catálogo ART-PROFILE + Observed persistido + perfil default al crear cuenta.  
> **En curso:** **FASE IA BACKEND CONGELADA (MVP)** — Propose→Confirm→Session→Replay→Outcome + paper_auto Session + Prediction PG.  
> **Fuera de esta fase:** broker (F6), Learning v2 auto-pesos, binarios modelo, split `bolsa_ai` packages.  
> **Constitución:** RFC-008 **Amendment-2** — Evidence ≠ Assessment ≠ Decision; contrato `Assessment` común.  
> **Ayuda:** sync `HELP_CONTENT_AS_OF` — **Análisis del valor** + **Plataforma IA**.

### Definition of Done — fase IA backend (2026-07-23)

1. Propose persiste `DecisionSession` (`kind=propose`) + Prediction PG best-effort.
2. Confirm acepta `sessionId`, escribe `execution` y marca `kind=confirm` (o crea Session confirm).
3. `paper_auto` / `live_dry_run` persisten Session + Decision Memory.
4. Replay + Outcome v1.1 (barra D1+N, `mature` / `premature_mtm`).
5. Effectiveness incluye `sessionLearning` (hit-rate Outcomes) separado de Memory Gate.
6. FUND v3 (ROE/D/E/Altman) + Macro VIX/curva + News en propose.
7. API documentada: `/api/ai/*` + `/api/predictions/*`.
8. **No-goals:** sin broker, sin auto-ajuste WeightRules, sin Fine-tune LLM.

### F3 — Recommendation Proposal (Arquitectura bloqueada 2026-07-23)

Endpoint único: `POST /api/ai/recommendations/propose`.

```text
OHLCV → FeatureSet → Evidence → TechnicalAssessment (+ Fund/Macro/News/Evidence Assessment)
                              ↓
                     Assessment[] → DecisionRuntime v1.1 (WeightRules + w_news)
                              ↓
                     DecisionPackage (único) + Recommendation
                              ↓
                     Policy Gate (propose = pasivo; paper_auto = hard)
```

**Reglas:** ningún Assessment emite BUY. Solo el Runtime construye el DecisionPackage. Fund/Macro/Evidence/News cableados en propose (Macro via Yahoo ^VIX + curva proxy; News via Yahoo search + heurística de título + earnings `calendarEvents`).

### F4 — Paper auto (MVP 2026-07-23)

- `EquityMarkBook` marca equity day/week open → `account_*_drawdown_pct` al Gate (`HardDailyDrawdown` / `HardWeeklyDrawdown` / `HardMaxDrawdown`).
- Persistencia: `settings_json.equityMarks` (merge en paper_auto; `update_settings` no borra la clave).
- `paperAutoManifest` en Decision Memory: signalId, strategyDefinitionId, policyId, dataVersion, scanId, featureSetHash, drawdowns.
- **`live_auto` dry-run:** Gate + `check_auto_live` + manifest (`dryRun: true`); statuses `live_dry_run_pass` / `live_dry_run_veto`. **Sin broker** (F6).

### F2 — Predictions (MVP 2026-07-23)

- `PredictionV1` / `ModelArtifact` (shared TS + Python).
- `PredictionService`: `technical_rating_v1` (heuristic) + `lgbm_direction_v1` (LightGBM opcional `bolsa-analytics[ml]`, sino `numpy_fallback`).
- HTTP: `GET /api/predictions/models`, `POST /api/predictions/predict`, `POST /api/predictions/models/train`.

### DecisionSession — auditabilidad (2026-07-23)

- **`ART-DECISION-SESSION`**: fotografía completa del propose (assessments + `WeightContext` + runtime + recommendation + gate).
- Tabla `decision_sessions` (payload JSONB). Distincto de `decision_memory` (outcome del Gate).
- Cada `POST /api/ai/recommendations/propose` persiste una Session (`kind=propose`, `status=open`).
- **Confirm:** `POST /api/ai/intents/confirm` con `sessionId` opcional → adjunta `execution` y `kind=confirm`.
- **paper_auto / live_dry_run:** además de Decision Memory, persisten Session (`kind=paper_auto|live_dry_run`).
- `WeightContext` incluye `ruleVersion` (`WEIGHT_RULES_VERSION`), horizonte, régimen, pesos, rationale, missingAssessments.
- HTTP: `GET /api/ai/decision-sessions`, `GET /api/ai/decision-sessions/{id}`, `…/replay`, `…/outcome`, `…/learning-summary`.
- UI: Supervisado F3 muestra fusión de pesos + `sessionId` + Abrir Replay. Ayuda → **Análisis del valor**.
- **Decision Replay:** timeline context→…→outcome (no re-ejecuta).
- **Outcome / Learning v1.1:** close D1 **+N** horizonte; `premature_mtm` si faltan barras. Effectiveness expone `sessionLearning`.
- **FUND Yahoo v3:** ROE/márgenes/D/E + Altman Z.
- **Prediction PG:** `model_artifacts` + `predictions` (metadata; sin binario).
- **Siguiente (fuera freeze):** probar bucle en UI · Learning v2 · broker F6.

> Índice: [rfc/README.md](./rfc/README.md).

---

## 0. Dictamen consolidado (3 auditorías)

### 0.1 Voto unánime — bloques estratégicos

| # | Bloque | Resultado |
|---|--------|-----------|
| 1 | Motor determinista vs IA probabilística | **ACUERDO ABSOLUTO** — inquebrantable |
| 2 | Cadena de decisión (con Recommendation) | **ACUERDO** (matiz abajo §0.2) |
| 3 | Stack tabular OSS + LLM OSS local + cloud opcional | **ACUERDO** |
| 4 | Feature Registry = catálogo + adapters | **ACUERDO ABSOLUTO** |
| 5 | Documentos fundacionales antes que más IA | **ACUERDO** |

### 0.2 Única discrepancia resuelta — ¿Recommendation en dominio?

| Auditoría | Posición |
|-----------|----------|
| A1 | Quitar del dominio; solo UX; cadena Prediction → Signal → Intent → Order |
| A2 | Mantener; capa Portfolio (sizing) entre Signal e Intent |
| A3 | Mantener; Signal = mercado/reglas; Recommendation = híbrido rules+ML |

**Resolución BLOQUEADA (mayoría 2/3 + utilidad operativa):**

- **Recommendation permanece como artefacto de dominio** (no es “texto de UI”).
- Vive en el **Portfolio / Trading Domain**, no en el Kernel de reglas ni en el OMS.
- Semántica fija:
  - **Signal** — evento táctico (rules / hybrid gate): “qué dice el mercado / la estrategia”.
  - **Recommendation** — sugerencia de acción + sizing base (puede incorporar Prediction): “qué haríamos con esa info”.
  - **Intent** — voluntad autorizada (humano o policy gate): “vamos a operar”.
  - **Order** — instrucción de ejecución.

```
Feature Matrix → Quant Runtime (Prediction | Rules)
                      ↓
               SignalEventV1
                      ↓
            Recommendation (sizing / acción)
                      ↓
           Risk & Policy Gate
                      ↓
              OrderIntentV1
                      ↓
           Execution (paper / broker)
```

### 0.3 Refuerzos adoptados de las auditorías

| Refuerzo | Origen | Adopción |
|----------|--------|----------|
| Dominio **Trading** (Signal…Position) separado de Execution/IA | A1 | **Sí** |
| Partir `bolsa_ai` → authoring / prediction / explanation / governance | A1 + A2 Capa 7 | **Sí** |
| **Prediction Registry** (tipo, schema, horizon, version, producer) | A1 | **Sí** (bajo Artifact Catalog) |
| Registries: Feature + Artifact + Model + **Policy** | A1 | **Sí** |
| Domain Registry con Owner, SLA, criticality (Execution = Tier 0) | A1 | **Sí** (RFC Capability / Handbook) |
| Data Products (Market Prices, Feature Set, Prediction Set…) | A1 | **Sí** (alineado a Lineage) |
| Capas 0–8 (Infra → Data → Research → Runtime → Strategy → Portfolio → Execution → AI Gov → MLOps) | A2 | **Sí** (mapa constitucional) |
| `AIGovernanceProxy` — único camino LLM; Kernel/Execution no importan `bolsa_ai` | A2 + A3 | **Sí** |
| Prediction = objeto (`value`, `confidence`, `modelId`, `featureSetHash`, `timestamp`) | A3 | **Sí** (RFC-000) |
| Circuit breaker paper→live (p.ej. drawdown) | A3 | **Sí** (Policy Registry) |
| RAG sobre registry/señales; no fine-tune v1 | A3 | **Sí** |
| No K8s / Kafka / microservicios / Feast / Ray / Spark / LangGraph / RL aún | A1 | **Sí** |
| Renombrar FeatureCache → adapter online (concepto; rename código en F1) | A3 | **Sí** (tras RFC) |

### 0.4 Decisiones D1–D10 — BLOQUEADAS

| ID | Decisión | Valor bloqueado | Notas |
|----|----------|-----------------|-------|
| D1 | LLM default | **Ollama local + OpenAI opcional** + fallback heurístico | Unánime |
| D2 | Modelo LLM local | **Qwen2.5-Coder 14B** (authoring); Llama 3.1 8B si VRAM baja / explicación | Unánime con matiz A3 |
| D3 | ML tabular | **LightGBM** primario; CatBoost solo experimentos | Unánime |
| D4 | Modelos propios | **Sí**, tabulares sobre Feature Sets | Unánime |
| D5 | Fine-tune LLM | **No en v1** (RAG + constrained decoding) | Unánime |
| D6 | Feature Store | **Registry + adapters** | Unánime |
| D7 | Orden docs | Pirámide RFC abajo (§7) | Unánime en espíritu; numeración refinada |
| D8 | Cadena | **Prediction → Signal → Recommendation → Intent → Order** | Mantener Recommendation (§0.2) |
| D9 | Auto-trading | **Paper → live**; live vía policy/webhook + circuit breaker | Unánime |
| D10 | DL / RL | **Aplazado** (F6+) | Unánime |

**Cesa** la discusión de tecnología de modelos hasta nueva RFC de cambio.

---

## 1. Objetivo de producto

| Capacidad | Descripción |
|-----------|-------------|
| Indicadores generados por IA | Prompt → spec del catálogo; compute determinista |
| Trading IA supervisado | Recommendation → humano confirma Intent → Order |
| Trading IA automático | Paper primero; live con policy + circuit breaker |
| Rastreadores con IA | Gate reglas + Prediction/score + ranking |
| Backtesting por IA | NL→estrategia validada → mismo motor BT |

**Principio inquebrantable:**

```
LLM / modelo generativo  →  Specification | explicación (nunca órdenes ni PnL)
ML tabular (opcional)    →  Prediction / Evidence (entra como Assessment, no como fill)
                 ↓
DecisionRuntime + Policy Gate + Execution / Backtest  (determinista)
                 ↓
Órdenes paper/live, fills, PnL contable, walk-forward — auditables
```

Matiz importante: **sí** habrá backtest y trading automático que ejecuten y midan PnL. Eso lo hace el **motor determinista** (Decision Engine + Execution), no el LLM. “Plataforma IA” ≠ “el chat manda la orden”.

Regla de código (Handbook): `execution/` y Platform Kernel **no pueden importar** paquetes `ai_*` (LLM).

---

## 2. Base ya integrada (resumen)

| Pieza | Estado |
|-------|--------|
| FastAPI + PG + shared + capas Python | ✅ |
| Platform Kernel (strategies, signals, trackers, policies, manifests, events) | ✅ parcial |
| Feature **cache** runtime (Redis/PG) | ✅ → reclasificar como online adapter |
| Hybrid trackers + rating determinista | ✅ MVP |
| Draft estrategia/indicador (Proxy + heurística + Ollama/OpenAI) | ✅ F1 |
| RFC-000…007 / Ubiquitous Language | ✅ constitución |
| AIGovernanceProxy + audit JSONL/PG | ✅ F1/F1+ |
| Feature Registry (`IFeaturePort` + ≥12 DEFs + HTTP/scan) | ✅ F2 esqueleto+ |
| Feature / Model / Prediction / Policy Registry completos | ❌ |
| Prediction / Recommendation / Intent como entidades formales | ❌ |

Detalle histórico: ADR-010 · historial git (sessions/audits antiguas eliminadas del árbol vivo).

---

## 3. Mapa constitucional de capas (adoptado)

```
Capa 0  Infrastructure     PG, Redis, Parquet/MinIO, colas, secrets
Capa 1  Data Platform      Ingest, Lineage, Feature Registry + adapters
Capa 2  Quant Research     Backtest hub, train/Optuna
Capa 3  Quant Runtime      Inference, scoring/ranking (LightGBM, heurísticas)
Capa 4  Strategy Engine    Signal engine & rules (Platform Kernel núcleo)
Capa 5  Portfolio Engine   Recommendation, sizing, risk view
Capa 6  Execution          Intent, OMS/pending orders, ExecutionPolicy
Capa 7  AI Governance      Prompt registry, LLM router, constrained authoring, audit
Capa 8  MLOps / Observability  MDR, Inference/Prediction registry, manifests, audit trail
```

**Trading Domain** (lenguaje de negocio, transversal a capas 4–6):  
`Signal · Recommendation · Intent · Order · Trade · Position · PortfolioSnapshot`  
— sin broker, sin LLM, sin detalles de infraestructura.

**Platform Kernel** (Capa 4 + contratos compartidos): reglas, señales, eventos, políticas, manifests — **no conoce IA**.

---

## 4. Paquetes IA (partición adoptada)

En lugar de un `bolsa_ai` monolítico:

| Paquete / módulo | Responsabilidad |
|------------------|-----------------|
| `ai_governance` | `AIGovernanceProxy`, router Ollama/OpenAI/none, audit, guardrails |
| `ai_authoring` | Prompt → Strategy/Indicator specs (structured JSON) |
| `ai_prediction` | Contratos e integración con Quant Runtime (no el train loop) |
| `ai_explanation` | Narrativa post-hoc de resultados ya calculados |

`bolsa_analytics.research.llm_*` orquesta authoring; **todas** las llamadas LLM pasan por `bolsa_ai.AIGovernanceProxy`.

---

## 5. Registries y Data Products

### 5.1 Registries

| Registry | Contiene |
|----------|----------|
| **Feature Registry** | Definición, schema, owner, version, lineage refs |
| **Artifact Registry** | Catálogo maestro de tipos de artefacto + lifecycle |
| **Model Registry** | modelId, métricas, featureSetId, status (draft/prod) |
| **Prediction Registry** | PredictionType, schema, horizon, confidence contract, producer/consumer |
| **Policy Registry** | `paper_auto_v1`, `live_safe_v3`, circuit breakers |
| **Prompt Registry** | plantillas versionadas de authoring |

Storage físico siempre vía **adapters** (PG, Parquet, Redis, DuckDB, Arrow).

### 5.2 Data Products (visión)

Ejemplos: Market Prices, Corporate Actions, Feature Set, Prediction Set, Risk Metrics, Portfolio Snapshot — cada uno con Owner, Quality, SLA, Schema, Consumers, Version (detalle en RFC Lineage / Data Contracts).

---

## 6. Stack de modelos (cerrado)

| Capa | Elección |
|------|----------|
| LLM authoring | Ollama + **Qwen2.5-Coder 14B**; OpenAI opcional; fallback heurístico |
| ML ranking/score | **LightGBM**; CatBoost solo research |
| Entrenamiento propio | Sí, sobre Feature Sets versionados |
| Fine-tune LLM | No v1 |
| DL / RL | Aplazado |

---

## 7. Pirámide RFC (orden BLOQUEADO — ajuste A1 post-dictamen)

Lenguaje → Artefactos → Capabilities → Architecture → Handbook → …

| RFC | Título | Estado |
|-----|--------|--------|
| **000** | [Ubiquitous Language](./rfc/000-ubiquitous-language.md) | **approved** |
| **001** | [Artifact System & Catalog](./rfc/001-artifact-catalog.md) | **approved** |
| **002** | [Capability Model & Domain Registry](./rfc/002-capability-model.md) | **approved** |
| **003** | [Platform Architecture](./rfc/003-architecture.md) | **approved** |
| **004** | [Engineering Handbook](./rfc/004-engineering-handbook.md) | **approved** |
| **005** | [Feature Registry & IFeaturePort](./rfc/005-feature-registry.md) | **approved** |
| **006** | [Data Contracts & Lineage](./rfc/006-data-contracts-and-lineage.md) | **approved** |
| **007** | [AI Governance](./rfc/007-ai-governance.md) | **approved** |

**Refuerzos A1 ya en RFC-000:** Domain IDs (`TRADING`, `FEATURE`, …), adelanto Capability IDs (`CAP-*`), lifecycle unificado, anti-sinónimos, mapeo **real** a Prisma/shared/domain.

ADR 001–010: permanecen. Índice RFC: [docs/rfc/README.md](./rfc/README.md).

---

## 8. Roadmap de ejecución (post-constitución)

| Fase | Nombre | Entregables |
|------|--------|-------------|
| **F0** | Constitución | RFC-000…006 (mínimo 000+001+004 antes de entidades nuevas) |
| **F1** | Authoring | `AIGovernanceProxy` + Ollama (Docker separado OK) + OpenAI; golden JSON tests |
| **F2** | Predictions | `PredictionV1` + LightGBM pipeline en Quant Runtime + Prediction Registry |
| **F3** | Supervisado | Recommendation → Intent en UI (confirmación humana) |
| **F4** | Paper auto | `paper_auto` + manifests + circuit breaker |
| **F5** | Backtest-by-IA | Prompt→strategy→walk-forward con gates |
| **F6** | Live (opcional) | Webhook/policy; solo tras paper estable |

**Paralelo suave permitido en F0:** contenedor Ollama + test de authoring JSON con el validador actual — **sin** nuevas entidades de dominio en API/UI.

---

## 9. Lo que NO se introduce ahora

Kubernetes, Kafka, microservicios reales, Ray, Spark, Feast, LangGraph, MCP distribuido, agentes autónomos, Reinforcement Learning, fine-tune LLM, LLM en hot path de scan/órdenes.

---

## 10. Cómo seguimos (orden operativo)

1. ~~RFC-000…007~~ → constitución cerrada.
2. ~~F1 / F1+~~ → Proxy, draft APIs, audit JSONL/PG, compose Ollama.
3. **Ahora:** aplicar migración `llm_calls` en cada entorno; Ollama live opcional.
4. **F2+:** golden ≥10 features; consumidores scan/ML vía `IFeaturePort`; tipos shared.
5. RFC-008+ solo si el código fuerza una decisión de plataforma.

Cesa la fase de auditorías de opinión. Solo RFCs ejecutables + implementación alineada.

---

## 11. Criterio de éxito (12–24 meses)

1. Mismo OHLCV/features para gráfico, BT, scan y ML.  
2. Toda Recommendation trazable (manifest + modelId + featureSetHash).  
3. Cambiar Redis/broker/LightGBM↔CatBoost sin rediseñar el dominio.  
4. Authoring OSS local sin clave cloud.  
5. Auto solo sobre modelos y políticas **registradas**.

---

*Dictamen cerrado 2026-07-21. Constitución + F1 hechos. F2 esqueleto. Ver [rfc/README.md](./rfc/README.md).  
UI seguimiento: Ayuda → **Plataforma IA** · tracker + [HELP.md](./HELP.md) (`HELP_CONTENT_AS_OF`).*
