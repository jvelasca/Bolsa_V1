---
id: rfc-006
title: Data Contracts & Lineage
status: approved
date: 2026-07-21
audience: development, data, ml, qa, ops, compliance
complements:
  - docs/rfc/000-ubiquitous-language.md
  - docs/rfc/001-artifact-catalog.md
  - docs/rfc/002-capability-model.md
  - docs/rfc/003-architecture.md
  - docs/rfc/004-engineering-handbook.md
  - docs/rfc/005-feature-registry.md
---

# RFC-006: Data Contracts & Lineage

> **Propósito:** Fijar de forma **inmutable** los contratos de datos entre capas/planos, los schemas canónicos (TS ↔ Python), la propagación de lineage/trace y las reglas de compatibilidad — desde mercado hasta posición.  
> **Principio:** Sin contrato versionado no hay integración oficial. Sin lineage no hay auditoría.  
> **Alcance:** Constitución de contratos. La implementación vive en `@bolsa/shared` + Pydantic; este RFC es la fuente de verdad semántica.

---

## 1. Objetivos

1. Catalogar **todos** los contratos V1 de la cadena Trading + research.
2. Definir **lineage E2E** y campos obligatorios de auditoría.
3. Unificar **envelope** de artefacto/evento con IDs canónicos.
4. Reglas de **versionado / compatibilidad** y **golden contract tests**.
5. Mapa de **migración** desde tipos actuales del repo.
6. Dejar base estable para Model/Prediction/Policy/Prompt registries y F1 (sin reabrir 000–005).

---

## 2. Principios de contratos

| Principio | Regla |
|-----------|--------|
| **Contract First** | Comunicación cross-domain solo vía contrato Vn |
| **Strict at boundaries** | Validación Pydantic / TS en bordes API, bus, workers |
| **SemVer** | Breaking → MAJOR; additive → MINOR; fix docs → PATCH |
| **Backward window** | Consumidores soportan N y N-1 durante ≥ 1 release menor |
| **Immutability** | Predictions, Signals emitidos, Manifests: append-only |
| **Traceability** | Toda decisión material lleva `traceId` + bloque `lineage` |
| **No silent coercion** | Tipos inválidos → reject / DLQ; no “arreglar” en caliente |

---

## 3. Base Envelope (reafirmación)

### 3.1 Artifact envelope

Ver [RFC-001 §4](./001-artifact-catalog.md). Campos mínimos en tránsito: `id`, `type` (`ART-*`), `version`, `schemaVersion`, `status`, `checksum`, `dependencies`, `lineage`, `payload`.

| Campo | Significado |
|-------|-------------|
| `version` | Versión del **artefacto instancia** (SemVer o content-hash) |
| `schemaVersion` | Versión del **contrato/schema** del payload (entero o SemVer menor del contrato) |

Ejemplo: `schemaVersion: "1"` + `version: "2.4.3"` — evolucionar un modelo sin cambiar el shape del contrato.

### 3.2 Event envelope

Ver [RFC-003 §6.2](./003-architecture.md). Campos mínimos:

```yaml
eventId: string
eventType: string
domain: string
capability: string   # CAP-*
timestamp: datetime
traceId: string
causationId: string | null   # eventId del evento causa inmediata
checksum: string | null
producer:
  capability: string         # CAP-*
  version: string            # producerVersion del componente
lineage: LineageBlock        # §5
payload: object
artifactRefs: [{ type, id, version }]
```

| ID | Rol |
|----|-----|
| `traceId` | Cadena completa de un path (hot/research/AI) |
| `eventId` | Este hop |
| `causationId` | `eventId` del padre causal (p.ej. Recommendation ← SignalRaised) |

`correlationId` legacy en `PlatformEventV1` se mapea a `traceId`.

### 3.3 Canonical IDs

| ID | Formato | Ejemplo |
|----|---------|---------|
| Domain | RFC-000 | `STRATEGY` |
| Capability | `CAP-*` | `CAP-STRAT-EVAL` |
| Artifact type | `ART-*` | `ART-SIGNAL` |
| Instance | uuid / ulid / prefijo | `sig_…`, `pred_…` |
| Trace | `tr_` + ulid | `tr_01J…` |
| Composition | hex sha256 trunc/full | FeatureSet hash |

---

## 4. Grafo de lineage E2E (DAG)

```
ART-DATASOURCE / ART-OHLCV (+ dataVersion)
        ↓ CAP-FEAT-COMPUTE
ART-FEATURE-DEF → ART-FEATURE-SET → ART-FEATURE-SNAP (+ composition_hash)
        ↓                         ↓
CAP-QUANT-INFER              CAP-STRAT-EVAL
ART-PREDICTION               ART-SIGNAL
        ↓                         ↓
        └──────────┬──────────────┘
                   ↓ CAP-PORT-RECOM
            ART-RECOMMENDATION
                   ↓ CAP-POLICY-GATE
              ART-INTENT
                   ↓ CAP-EXEC-OMS
         ART-ORDER → ART-TRADE → ART-POSITION
                   ↓
            ART-MANIFEST / ART-EVENT (OBS)
```

Research offline (paralelo):

```
ART-DATASET + ART-FEATURE-SET → ART-MODEL → (promote) → RUNTIME
ART-BACKTEST / ART-BT-TRADE (no mezclar con ART-TRADE)
```

---

## 5. LineageBlock (propagación obligatoria)

```yaml
LineageBlock:
  dataVersion: string | null           # OHLCV / DataSnapshotRef
  featureSetId: string | null
  compositionHash: string | null       # FeatureSet
  featureSnapshotId: string | null     # ART-FEATURE-SNAP concreto (debug/PIT)
  predictionIds: string[]              # puede ser []
  signalIds: string[]
  recommendationId: string | null
  intentId: string | null
  modelId: string | null
  strategyDefinitionId: string | null
  manifestId: string | null
```

### 5.1 Reglas de completitud

| Evento / artefacto | Lineage mínimo |
|--------------------|----------------|
| `FeaturesReady` | `dataVersion`, `compositionHash` |
| `PredictionGenerated` | + `modelId`, `featureSetId`, `compositionHash` |
| `SignalRaised` | `dataVersion` y/o `compositionHash`; `strategyDefinitionId` |
| `RecommendationCreated` | `signalIds` (≥1); `predictionIds` opcional |
| `IntentApproved` (paper/live auto) | `recommendationId` + `dataVersion` + `compositionHash` (si hubo features) |
| `OrderSubmitted` / `TradeFilled` | hereda Intent + `intentId` |
| `ManifestCompleted` | closure completo de refs |

**Policy gate (Production auto):** si falta `lineage.recommendationId` o (cuando aplica) `compositionHash`/`dataVersion` → `IntentRejected`, no Order.

**Modo research / draft:** validación puede ser warn-only hasta promoción.

---

## 6. Catálogo de contratos (origen → destino)

| Contrato | Origen CAP / Domain | Destino | Notas |
|----------|---------------------|---------|-------|
| `OhlcvBarV1` | DATA | FEATURE, RESEARCH, UI | barras |
| `DataSnapshotRefV1` | DATA | RESEARCH, OBS | ya en shared |
| `FeatureRequestV1` | RUNTIME, STRATEGY | FEATURE | RFC-005 |
| `FeatureSnapshotV1` | FEATURE | RUNTIME, STRATEGY | RFC-005 |
| `ModelArtifactV1` | RESEARCH / MODEL | RUNTIME | §7.3 |
| `PredictionV1` | RUNTIME | PORTFOLIO, TRACK | §7.4 |
| `SignalEventV1` | STRATEGY | PORTFOLIO, ALERTS | **ya existe** |
| `RecommendationV1` | PORTFOLIO | POLICY, UI | §7.6 |
| `OrderIntentV1` | POLICY / UI | EXECUTION | §7.7 |
| `PendingOrder` / `OrderV1` | EXECUTION | broker adapter | hoy PendingOrder |
| `TradeFillV1` | EXECUTION | PORTFOLIO | ART-TRADE |
| `BacktestTradeV1` | RESEARCH | UI | ART-BT-TRADE |
| `PositionV1` | EXECUTION | PORTFOLIO, UI | hoy PositionDto |
| `PlatformEventV1` | OBS | todos | ya existe |
| `RunManifest` / `ScanManifestV1` | OBS / jobs | UI, audit | ya existen |
| `DraftV1` | AIGOV | UI / STRATEGY | authoring |

---

## 7. Canonical DTOs (campos V1)

Los nombres TypeScript canónicos viven en `@bolsa/shared`. Python: Pydantic mirror (`model_config` camelCase aliases donde aplique).

### 7.1 `OhlcvBarV1`

`instrumentId`, `timestamp`, `open`, `high`, `low`, `close`, `volume?`, `dataVersion?`

### 7.2 `FeatureSnapshotV1`

Ver [RFC-005](./005-feature-registry.md): `instrumentId`, `timestamp`, `featureSetId`, `compositionHash`, `values`, `dataVersion?`

### 7.3 `ModelArtifactV1` (`ART-MODEL` payload)

| Campo | Descripción |
|-------|-------------|
| `modelId`, `version` | identidad del artefacto modelo |
| `schemaVersion` | versión del contrato ModelArtifactV1 |
| `framework` | `lightgbm` \| `catboost` \| `xgboost` \| `heuristic` \| … |
| `featureSetId`, `compositionHash` | inputs |
| `target` | `{ name, type: continuous\|class\|rank }` |
| `metrics` | object (sharpe, auc, …) research |
| `artifactUri` / `binaryChecksum` (`modelChecksum`) | integridad del binario |
| `hyperparameters` | object |

### 7.4 `PredictionV1` (`ART-PREDICTION`)

| Campo | Obligatorio |
|-------|-------------|
| `predictionId` | sí |
| `instrumentId` | sí |
| `modelId`, `modelVersion` | sí |
| `modelChecksum` | sí (sha256 del binario/artefacto Model; reproducibilidad) |
| `schemaVersion` | sí (contrato PredictionV1) |
| `featureSetId`, `compositionHash` | sí |
| `featureSnapshotId` | recomendado |
| `timestamp` / `asOf` | sí |
| `horizon` | sí (string, p.ej. `1d`) |
| `value` | sí (number \| object tipado) |
| `confidence` | sí (0–1 o escala documentada por modelId) |
| `probabilities` | no |
| `dataVersion` | recomendado |
| `traceId` | sí en tránsito |

### 7.5 `SignalEventV1` (existente — canónico)

Mantener [signal-events.ts](../../packages/shared/src/signal-events.ts):

- `kind`: `entry_long` \| `entry_short` \| `exit` \| `watch` (**no** reemplazar por BUY/SELL en V1)
- `strategyDefinitionId`, `strategyVersion`, `instrumentId`, `timestamp`, `barIndex`, `price`
- `dataVersion?`, `indicatorSnapshotHash?` → mapear a lineage (`compositionHash` cuando migre FeatureSet)

Side de portfolio se deriva en Recommendation (`BUY`/`SELL`/`HOLD`), no reescribe SignalKind.

### 7.6 `RecommendationV1`

| Campo | Descripción |
|-------|-------------|
| `recommendationId` | |
| `signalIds` | ≥1 |
| `predictionIds?` | |
| `instrumentId` | |
| `side` | `BUY` \| `SELL` \| `HOLD` |
| `suggestedSize` | número + unidad en metadata (`shares`\|`cash`\|`pct_equity`) |
| `confidence` | 0–1 |
| `timestamp` | |
| `accountScope?` | |
| `lineage` | LineageBlock |

### 7.7 `OrderIntentV1`

| Campo | Descripción |
|-------|-------------|
| `intentId` | |
| `recommendationId` | |
| `instrumentId`, `side`, `size` | |
| `status` | `Pending` \| `Approved` \| `Rejected` \| `Expired` |
| `approvedBy` | `human:<id>` \| `policy:<id>` |
| `timestamp`, `expiresAt?` | |
| `lineage` | obligatorio en Approved (auto) |

### 7.8 `OrderV1` / PendingOrder

Hoy: `PendingOrderDto` / Prisma `PendingOrder`. Target V1 añade `intentId?`, `lineage?` sin romper campos existentes.

Campos lógicos: `orderId`, `intentId`, `instrumentId`, `side`, `size`, `orderType` (`MARKET`\|`LIMIT`\|`STOP`), precios opcionales, `status`, timestamps.

### 7.9 `TradeFillV1` (`ART-TRADE`)

`tradeId`, `orderId`, `instrumentId`, `side`, `size`, `price`, `fees`, `timestamp`, `lineage?`

Distinto de `BacktestTradeDto` (`ART-BT-TRADE`).

### 7.10 `PositionV1`

Alineado a `PositionDto`: `positionId`/`id`, `instrumentId`, size, avg price, PnL fields, `accountId`, `updatedAt`.

### 7.11 Manifest contracts

`RunManifest` / `ScanManifestV1` existentes: deben listar closure `{ type, id, version, checksum }[]` incluyendo FeatureSet + Model + Strategy cuando aplique (refuerzo RFC-001/003).

---

## 8. Platform Events (contrato + lineage)

Catálogo [RFC-003 §6.3](./003-architecture.md). Cada `eventType` declara payload schema + lineage mínimo (§5.1).

Reglas runtime (target):

- Deserialización falla → **DLQ** / log estructurado; no procesar.
- Workers idempotentes por `eventId`.

Tipos legacy en `PlatformEventType` se **mapean** a nombres canónicos; rename gradual.

---

## 9. Trace IDs

| Campo | Alcance |
|-------|---------|
| `traceId` | Una cadena Hot/Research/AI path completa |
| `eventId` | Un hop |
| `span` (futuro) | OpenTelemetry opcional |

UI y API: aceptar/propagar header `X-Bolsa-Trace-Id` cuando exista.

---

## 10. Versionado y compatibilidad

| Cambio | Ejemplo | SemVer contrato |
|--------|---------|-----------------|
| Campo required nuevo | `compositionHash` mandatory | MAJOR |
| Campo optional nuevo | `probabilities` | MINOR |
| Rename kind | — | MAJOR |
| Doc-only | — | PATCH |

Reglas:

1. Nunca reutilizar `predictionId`/`signalId` con payload distinto.
2. Consumers ignoran campos desconocidos (forward compat) en MINOR.
3. Producers no eliminan campos required de N-1 en la ventana de convivencia.

---

## 11. Shared TS ↔ Python

| Capa | Ubicación |
|------|-----------|
| Fuente de nombres/campos | Este RFC + `@bolsa/shared` |
| Validación Python | Pydantic v2 en bordes API/application |
| Paridad | Golden JSON fixtures en `packages/shared/testdata/contracts/` (target) |
| CI | test que importa fixture → parse TS typecheck + Pydantic |

**Prohibido** divergir camelCase/snake sin alias explícito.

---

## 12. Data Products (visión operativa)

| Data Product | Owner Domain | Artefactos | Consumidores |
|--------------|--------------|------------|--------------|
| Market Prices | DATA | OHLCV, CORP-ACTION | FEATURE, RESEARCH, UI |
| Feature Sets | FEATURE | FEATURE-* | RUNTIME, STRATEGY, RESEARCH |
| Predictions | RUNTIME | PREDICTION, MODEL | PORTFOLIO, TRACK |
| Recommendations | PORTFOLIO | RECOMMENDATION | UI, POLICY |
| Execution Ledger | EXECUTION | INTENT, ORDER, TRADE, POSITION | PORTFOLIO, UI, OBS |
| Manifests | OBS | MANIFEST, EVENT | audit, UI |

---

## 13. Golden Contract Tests

Obligatorios al introducir/cambiar contrato:

1. Fixture JSON válido parsea en TS y Python.
2. Fixture inválido rechazado.
3. Cadena mínima: OHLCV fixture → FeatureSnap → Prediction → Signal → Recommendation → Intent → Order → Trade (synthetic).
4. IntentApproved sin lineage requerido → reject en modo Production auto.
5. SignalKind no se traduce silenciosamente a BUY sin Recommendation.

---

## 14. Migración desde código actual

| Contrato RFC-006 | Hoy | Acción |
|------------------|-----|--------|
| OhlcvBarV1 | bars DTO / entities | alias/documentar |
| FeatureSnapshotV1 | FeatureCache values | introducir tipos |
| PredictionV1 | scores heurísticos sin envelope | envolver `technical_rating_v1` como modelId |
| SignalEventV1 | ✅ shared | añadir lineage fields opcionales |
| RecommendationV1 | — (`Instrument.recommendation` ≠) | crear; no reutilizar XTB |
| OrderIntentV1 | — | crear antes F3/F4 |
| OrderV1 | PendingOrder | extender `intentId` |
| TradeFillV1 | Transaction / fills | aclarar naming |
| PositionV1 | PositionDto | ✅ |
| PlatformEventV1 | ✅ | enriquecer lineage |
| Run/Scan Manifest | ✅ | exigir compositionHash cuando features |

---

## 15. Relación con registries posteriores

| Registry | Usa contratos de |
|----------|------------------|
| Feature (RFC-005) | Feature* |
| Model / Prediction | ModelArtifactV1, PredictionV1 |
| Policy / Prompt | payloads + DraftV1 (RFC-007) |
| AIGovernanceProxy F1 | DraftV1 / StrategyDefinitionV1 **existing** schemas |

F1 **no** inventa DTOs de trading; solo produce Drafts validados contra schemas ya compartidos.

---

## 16. Criterios de aceptación

- [x] RFC en `docs/rfc/006-data-contracts-and-lineage.md`
- [x] DAG lineage E2E + LineageBlock + reglas de completitud
- [x] Catálogo de contratos + DTOs V1 (incl. Model/Prediction)
- [x] Events, trace, versionado, TS↔Python, Data Products
- [x] Golden tests plan + migración honesta
- [ ] (Impl) tipos nuevos en `@bolsa/shared`
- [ ] (Impl) Pydantic mirrors + CI contract tests
- [ ] (Impl) DLQ / reject Intent sin lineage en auto

---

## 17. Próximo paso

RFC-007 AI Governance → F1 (código Proxy + Ollama). Ajustes post-aprobación (§3 schemaVersion / causationId / producer / modelChecksum / featureSnapshotId) integrados.

---

## 18. Enmiendas

Nuevo contrato V1, campo required en LineageBlock, o cambio de SignalKind → PR a este RFC (+ shared).

---

*Síntesis A1 (alcance constitucional amplio) + A2 (Model/Prediction + lineage gate) + A3 (catálogo/Data Products); ART-TRADE no ART-FILL; SignalKind preservado.*
