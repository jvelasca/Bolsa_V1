---
id: rfc-000
title: Ubiquitous Language (Lenguaje Ubicuo)
status: approved
date: 2026-07-21
audience: development, product, data, quant
complements:
  - docs/AI_PLATFORM_SOLUTION.md
  - docs/adr/003-python-backend-ai-platform.md
  - docs/adr/010-platform-kernel-radar-execution.md
  - docs/adr/015-scientific-domain-vs-trading-domain.md
  - docs/domain-language.md
---

# RFC-000: Ubiquitous Language

> **Propósito:** Establecer el idioma oficial del sistema. Una palabra, un significado.  
> **Efecto:** Cualquier término de dominio no definido aquí es **deuda semántica** hasta su inclusión vía enmienda a este RFC **o** entrada en [docs/domain-language.md](../domain-language.md) (glosario QROS vivo).  
> **QROS / Scientific Domain:** el diccionario operativo de Hypothesis, Evidence, Belief, Discovery Vector, etc. vive en **domain-language.md** y se alinea con ADR-011…015. Este RFC conserva la cadena Trading/Feature/Execution.  
> **No define** tecnología de almacenamiento ni APIs concretas (eso va en RFC posteriores).

---

## 1. Objetivo y alcance

Este RFC es obligatorio para:

- Nombres de tipos, interfaces, entidades de dominio y esquemas nuevos
- Documentación técnica, manifests, eventos y logs de auditoría
- Conversación entre dominios (Research, Runtime, Portfolio, Execution, AI)

Los ADRs 001–010 y el código existente **no se renombran de golpe**. El §6 fija el mapeo *actual → canónico* y el estado de migración.

---

## 2. Domain IDs (identificadores estables)

Usar en logs, manifests, métricas, YAML, eventos y documentación.

| Domain ID | Nombre | Rol |
|-----------|--------|-----|
| `MARKET` | Market Data | Instrumentos, OHLCV, sesiones, corporate actions |
| `DATA` | Data Platform | Ingesta, snapshots, lineage, adapters de almacenamiento |
| `FEATURE` | Features | Definición y cómputo de variables derivadas |
| `RESEARCH` | Quant Research | Backtest, optimización, entrenamiento offline → **Scientific Domain** (ADR-015; glosario QROS) |
| `RUNTIME` | Quant Runtime | Inferencia / scoring batch o online |
| `STRATEGY` | Strategy Engine (Kernel) | Rules, StrategyDefinition, Signal |
| `PORTFOLIO` | Portfolio Engine | Recommendation, sizing, visión de cartera |
| `TRADING` | Trading Domain | Vocabulario de negocio Signal…Position (transversal) |
| `EXECUTION` | Execution Platform | Intent → Order → fill; OMS / paper / broker |
| `INFRA` | Infrastructure | Workers, DB, adapters, telemetry *(no Belief ni Position)* |
| `MODEL` | Models / MLOps | Model Registry, experimentos, MDR |
| `AI` | AI (particionado) | Authoring / prediction contracts / explanation |
| `AIGOV` | AI Governance | Único acceso LLM (`AIGovernanceProxy`) |
| `POLICY` | Policies | ExecutionPolicy, PositionPolicy, circuit breakers |
| `OBS` | Observability | PlatformEvent, manifests, audit trail |

**Qualified names** (recomendados):

```
TRADING.SIGNAL
TRADING.RECOMMENDATION
TRADING.INTENT
TRADING.ORDER
TRADING.TRADE
TRADING.POSITION
FEATURE.RSI_14
MODEL.LGBM_RANK_V1
POLICY.PAPER_AUTO_V1
CAP-BACKTEST   (ver Capability IDs en RFC-002)
```

---

## 3. Dominios de alto nivel (lenguaje)

| Término | Domain ID | Significado | No usar |
|---------|-----------|-------------|---------|
| Data Platform | `DATA` | Ingesta, almacenamiento, transformación, servido de datos y features | “ETL” como sinónimo del dominio |
| Quant Research | `RESEARCH` | Experimentación offline: BT, train, candidatos | “El notebook” |
| Quant Runtime | `RUNTIME` | Inferencia con modelos **ya registrados** | “El modelo en prod” (informal) |
| Strategy Engine / Platform Kernel | `STRATEGY` | Motor determinista de reglas → `Signal` | “Algoritmo” / “Trading Engine” |
| Portfolio Engine | `PORTFOLIO` | De Signal (+ Prediction opcional) → `Recommendation` | Confundir con “Risk” solo |
| Execution Platform | `EXECUTION` | `Intent` → `Order` → fill | “Broker” (el broker es un adapter) |
| AI Governance | `AIGOV` | Único camino a LLMs | “ChatGPT directo” |
| Trading Domain | `TRADING` | Entidades de negocio del ciclo operativo | — |

---

## 4. Cadena de decisión (Trading Domain)

```
Feature Matrix → Quant Runtime (Prediction | Rules en Kernel)
                        ↓
                 Signal  (TRADING.SIGNAL)
                        ↓
              Recommendation  (TRADING.RECOMMENDATION)
                        ↓
             Risk & Policy Gate  (POLICY)
                        ↓
                  Intent  (TRADING.INTENT)
                        ↓
                  Order   (TRADING.ORDER)
                        ↓
                  Trade   (TRADING.TRADE / fill)
                        ↓
                Position  (TRADING.POSITION)
```

| # | Término | ID cualificado | Definición | Responde a |
|---|---------|----------------|------------|------------|
| 1 | **Feature** | `FEATURE.*` | Valor derivado versionado (numérico/categórico) con definición en Feature Registry | “¿Qué variables alimentan modelos y reglas?” |
| 2 | **Prediction** | `RUNTIME.PREDICTION` | Salida tipada de un modelo: `value`, `confidence`, `modelId`, `featureSetHash`, `horizon`, `timestamp` | “¿Qué estima el modelo?” |
| 3 | **Signal** | `TRADING.SIGNAL` | Evento táctico discreto del Strategy Engine (rules / umbrales / hybrid gate) | “¿Qué dice el mercado/estrategia?” |
| 4 | **Recommendation** | `TRADING.RECOMMENDATION` | Acción propuesta + sizing base (`side`, `suggestedSize`, refs a signal/prediction) | “¿Qué haríamos con esa info?” |
| 5 | **Intent** | `TRADING.INTENT` | Voluntad autorizada (humano o policy) para operar | “¿Está aprobado operar?” |
| 6 | **Order** | `TRADING.ORDER` | Instrucción de ejecución (market/limit/stop…; estados PENDING/FILLED/…) | “¿Qué se envió al OMS/broker?” |
| 7 | **Trade** | `TRADING.TRADE` | Fill materializado (parcial o total) | “¿Qué se ejecutó?” |
| 8 | **Position** | `TRADING.POSITION` | Exposición abierta agregada en una cuenta | “¿Qué inventario tenemos?” |

### 4.1 Reglas de dependencia semántica

1. **Prediction es opcional.** Una Signal puede existir sin Prediction (p. ej. RSI > 70 puro rules).
2. **Recommendation** se basa en ≥1 Signal; puede incorporar Prediction.
3. **Intent** se basa en una Recommendation aprobada (humano o Policy Gate).
4. **Order** se deriva de un Intent; nunca directamente de un Signal o de un LLM.
5. **Trade** (fill) actualiza **Position**.

### 4.2 Dos contextos de “Trade” (anti-colisión)

| Contexto | Nombre canónico | Uso |
|----------|-----------------|-----|
| Cartera / ejecución | `TRADING.TRADE` (fill) | Operación real o paper en cuenta |
| Backtest | `RESEARCH.BACKTEST_TRADE` | Fill simulado en un `BacktestRun` |

No llamar “Trade” a una Order ni a un Intent.

---

## 5. Prediction — forma canónica del objeto

Hasta existir el contrato en `@bolsa/shared`, toda Prediction debe conceptualmente incluir:

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `value` | number \| string \| object | Salida del modelo (score, clase, vector) |
| `confidence` | number \| null | 0–1 o escala documentada por `modelId` |
| `modelId` | string | ID en Model Registry (`MODEL.*`) |
| `featureSetHash` | string | Hash del Feature Set usado |
| `horizon` | string \| null | p. ej. `1d`, `5d` |
| `timestamp` | ISO-8601 | Momento de la inferencia |
| `instrumentId` | string \| null | Si aplica a un activo |

**Prohibido:** persistir un “score” anónimo sin `modelId` + `featureSetHash` cuando el consumidor es Ranking/ML.

Los scores heurísticos actuales (`technical_rating_v1`) se tratan como **Prediction** con `modelId` determinista (no LLM).

---

## 6. Kernel y artefactos de plataforma

| Término | Definición | No usar |
|---------|------------|---------|
| **StrategyDefinition** | Spec formal de estrategia (entries/exits, kind, timeframe) | “Código de estrategia” suelto |
| **Rule** / **RuleGroup** | Condición atómica / grupo booleano | “Filtro” ambiguo |
| **Policy** | Gobierna *cómo* se autoriza/ejecuta (`ExecutionPolicy`, `PositionPolicy`, circuit breaker) | “Config” genérico |
| **Manifest** | Snapshot inmutable de un run (scan/backtest/job) | “Log” |
| **PlatformEvent** | Evento de plataforma auditable | “Auditoría” como único término |
| **TrackerDefinition** | Rastreador: estrategia + universo + schedule | UI/producto: siempre **Rastreadores** (no «Screeners»). Código/ruta pueden usar `screeners` |
| **Draft** | Spec propuesta por authoring (LLM/heurística) aún no validada | “Estrategia generada” como final |
| **Model** | Artefacto ML en Model Registry | “La IA” |
| **Prompt** | Plantilla versionada en Prompt Registry | “Consulta al chat” |

---

## 7. Feature vs Indicator (convivencia explícita)

| Término | Uso canónico |
|---------|----------------|
| **Indicator** | Spec de indicador de gráfico / catálogo de trading (`IndicatorSpec`, paneles chart). Lenguaje de producto UI válido. |
| **Feature** | Variable versionada en Feature Registry que alimenta ML, ranking o pipelines de research. |

Un Indicator **puede materializarse como** Feature (mismo cómputo, distinto rol de gobernanza).  
**No** se exige renombrar mañana todo `indicator*` del frontend.  
**Sí** se exige: código nuevo de ML/registry use `Feature` / `FeatureDefinition`.

---

## 8. Lifecycle oficial de artefactos

Ciclo único para: Model, Prompt, Feature definition, Policy, Dataset, StrategyDefinition, Indicator catalog entry (cuando versionado):

```
Draft → Experimental → Validated → Production → Deprecated → Archived
```

| Estado | Significado |
|--------|-------------|
| `Draft` | En edición; no usable en auto |
| `Experimental` | Pruebas controladas / research |
| `Validated` | Pasó gates (tests, walk-forward mínimo) |
| `Production` | Autorizado en paper/live según Policy |
| `Deprecated` | No nuevos usos; runs existentes OK |
| `Archived` | Solo histórico |

Detalle de transiciones y owners → **RFC-001 Artifact Catalog**.

---

## 9. Anti-sinónimos (prohibidos en dominio nuevo)

| ❌ Prohibido (sentido de dominio) | ✅ Correcto | Motivo |
|----------------------------------|-------------|--------|
| Alert / Trigger (como táctica) | `Signal` | Alertas de UI son *notificaciones* sobre Signals |
| Advice / Suggestion | `Recommendation` | Entidad formal con sizing |
| Trade request / Draft order | `Intent` | Voluntad autorizada ≠ Order |
| AI decision / “la IA compró” | Prediction → Recommendation → Intent | La IA no ejecuta |
| Prompt engine | `AIGovernanceProxy` | Gobernanza, no “chat” |
| Score suelto (ML) | `Prediction` | Debe llevar modelId + featureSetHash |
| Enviar la señal al broker | Intent → Order → adapter | Nunca Signal→broker |
| El modelo hizo el backtest | Motor BT + StrategyDefinition | IA no calcula BT |

**Excepción documentada:** `Instrument.recommendation` (Yahoo/XTB) es **metadato de proveedor**, no `TRADING.RECOMMENDATION`. En código nuevo referirlo como `BrokerInstrumentOpinion` / campo legacy; no reutilizar el nombre Recommendation para Portfolio.

---

## 10. Mapeo a código actual (fuente de verdad)

Mapeo **real** del repo (2026-07-21). Los borradores de auditoría con `StrategySignal` / `AiRecommendation` en Prisma **no existen**.

### 10.1 Cadena Trading

| Lenguaje (RFC-000) | `@bolsa/shared` / UI | Prisma / PG | `bolsa_domain` | Estado |
|--------------------|----------------------|-------------|----------------|--------|
| Feature | `IndicatorSpec` (parcial); FeatureCache runtime | — (cache, no registry) | — | 🔄 Registry pendiente; cache = online adapter |
| Prediction | — | — | — | 🚧 Crear `PredictionV1` |
| Signal | `SignalEventV1` | vía alertas / eventos | lógica en analytics | ✅ |
| Recommendation | — (no confundir con `InstrumentXtbRecommendation`) | — | — | 🚧 Crear `RecommendationV1` |
| Intent | — | — | — | 🚧 Crear `OrderIntentV1` |
| Order | `PendingOrderDto` | `PendingOrder` | infra repo | ✅ Order pendiente; OMS completo futuro |
| Trade (cartera) | movimientos / ledger | `Transaction` (+ fills implícitos) | `TradeResult` en portfolio | 🔄 Aclarar fill vs ledger en RFC-001 |
| Trade (backtest) | `BacktestTradeDto` | `BacktestTrade` | `BacktestTrade` | ✅ usar `RESEARCH.BACKTEST_TRADE` |
| Position | `PositionDto` | `Position` | `Position` | ✅ |

### 10.2 Kernel / research

| Lenguaje | Código actual | Estado |
|----------|---------------|--------|
| StrategyDefinition | `StrategyDefinitionV1` + Prisma `StrategyDefinition` | ✅ |
| ExecutionPolicy | `ExecutionPolicyV1` | ✅ |
| PositionPolicy | `PositionPolicyV1` | ✅ |
| ScanManifest / RunManifest | `ScanManifestV1`, manifests BT | ✅ |
| PlatformEvent | `PlatformEventV1` + Prisma `PlatformEvent` | ✅ |
| TrackerDefinition | `TrackerDefinitionV1` | ✅ |
| Draft (estrategia/indicador) | `llm_*` + Prompt Registry | ✅ F1 |
| Feature online store | `OnlineFeatureAdapter` + `FeatureCache` | ✅ F2 esqueleto |

### 10.3 IA

| Lenguaje | Código actual | Estado |
|----------|---------------|--------|
| AIGovernanceProxy | `bolsa_ai.AIGovernanceProxy` | ✅ F1 |
| LLM authoring | `llm_draft` / `llm_indicator_draft` → Proxy | ✅ |
| Heuristic draft | `prompt_catalog_v1` / `prompt_indicator_draft` | ✅ fallback |

---

## 11. Invariantes de dependencia (lenguaje → arquitectura)

| Componente | Puede conocer | No puede conocer |
|------------|---------------|------------------|
| Strategy Engine (Kernel) | StrategyDefinition, Rule, Signal, Feature (como input de rules) | Recommendation, Intent, Order, LLM |
| Portfolio Engine | Signal, Prediction, Position, Recommendation | Order, broker APIs, LLM |
| Execution Platform | Intent, Order, Trade, Policy | Signal, Prediction, Recommendation, `ai_*` |
| AI Governance | Prompt, Draft, schemas de authoring | Order, Trade, Position, envío a broker |
| Quant Runtime | Feature, Model, Prediction | Order, Intent |

**Regla de import (refuerzo):** módulos de ejecución y kernel **no importan** `ai_*` / `bolsa_ai`. Detalle normativo → **RFC-004 Engineering Handbook**.

---

## 12. Anti-patrones de fraseo (documentos y PRs)

| ❌ | ✅ |
|---|---|
| “La IA decidió comprar” | “Prediction → Recommendation; Intent aprobado; Order enviada” |
| “Mandamos la señal al broker” | “Intent materializado en Order vía Execution adapter” |
| “El LLM hizo el backtest” | “El motor de backtest ejecutó la StrategyDefinition” |
| “Feature store Redis” | “OnlineFeatureAdapter (Redis) detrás del Feature Registry” |

---

## 13. Capability IDs (adelanto; detalle en RFC-002)

IDs estables para referenciar capacidades desde ADR/RFC/código:

| Capability ID | Capacidad |
|---------------|-----------|
| `CAP-MARKET-INGEST` | Ingesta y sanity de mercado |
| `CAP-FEATURE` | Feature Registry + compute |
| `CAP-BACKTEST` | Backtesting |
| `CAP-OPTIMIZE` | Optimización (grid/Optuna/VectorBT) |
| `CAP-TRACKER` | Rastreadores / scans |
| `CAP-SIGNAL` | Evaluación de señales |
| `CAP-RECOMMEND` | Portfolio recommendations |
| `CAP-RISK` | Policy / risk gates |
| `CAP-EXECUTION` | Intent → Order → fill |
| `CAP-ML` | Train + inferencia tabular |
| `CAP-LLM` | Authoring / explanation vía AIGOV |
| `CAP-OBS` | Eventos, manifests, métricas |

La **Capability Matrix** (Capability · Owner · Registry · SLA · Tier · RFC) vive en **RFC-002**.

---

## 14. Cambios derivados (no bloquean la aprobación de este RFC)

Orden sugerido; **no** reescribir el frontend entero en un día:

1. Añadir contratos `PredictionV1`, `RecommendationV1`, `OrderIntentV1` en `@bolsa/shared` **después** de RFC-001 (Artifact Catalog) o en el mismo PR si el catálogo ya lista esos artefactos.
2. Documentar `Instrument.recommendation` (XTB) como legacy de proveedor.
3. Reclasificar `FeatureCache` → adapter online (rename interno, F1).
4. Nuevo código ML/registry: vocabulario Feature/Prediction únicamente.
5. No usar “Recommendation” para nada que no sea `TRADING.RECOMMENDATION`.

---

## 15. Criterio de cumplimiento (ejecutable)

Este RFC se considera **aplicado** cuando:

- [ ] Existe `docs/rfc/000-ubiquitous-language.md` en el repo (este archivo).
- [ ] `docs/AI_PLATFORM_SOLUTION.md` apunta a la pirámide RFC actualizada.
- [ ] PRs nuevos que introduzcan entidades de dominio citan el término RFC-000 o enmiendan este doc.
- [ ] CI opcional futuro: lint de términos prohibidos en `packages/shared` / `bolsa_domain` (RFC-004).

---

## 16. Enmiendas

Cualquier término nuevo de dominio requiere PR que actualice este RFC **y/o** [docs/domain-language.md](../domain-language.md) **antes** o **junto** al código que lo introduce.

### 16.1 QROS (2026-07-24)

Términos Scientific Domain (Hypothesis, Evidence, Belief, Knowledge, Discovery Vector, Research Value, …) y frontera Scientific/Trading/Infra: **[domain-language.md](../domain-language.md)**. No duplicar tablas largas aquí.

---

*Aprobado conceptualmente por dictamen triple + refuerzos A1 (Domain IDs, lifecycle, Capability IDs). Mapeo §10 verificado contra el repositorio el 2026-07-21.*
