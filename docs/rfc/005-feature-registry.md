---
id: rfc-005
title: Feature Registry & IFeaturePort
status: approved
date: 2026-07-21
audience: development, data, ml, qa
complements:
  - docs/rfc/000-ubiquitous-language.md
  - docs/rfc/001-artifact-catalog.md
  - docs/rfc/002-capability-model.md
  - docs/rfc/003-architecture.md
  - docs/rfc/004-engineering-handbook.md
---

# RFC-005: Feature Registry & IFeaturePort

> **Propósito:** Especializar la constitución en el **primer registry real**: catálogo de features (`ART-FEATURE-*`), puerto de dominio (`IFeaturePort`), adapters online/offline, compute, lineage mínimo y migración desde `FeatureCache` / `IndicatorSpec`.  
> **Principio:** Una feature se **define una vez** (Registry); se **calcula** con un motor determinista; se **sirve** por adapters; se **consume** solo vía puerto.  
> **Alcance:** Caps `CAP-FEAT-CATALOG`, `CAP-FEAT-COMPUTE`, `CAP-FEAT-STORE`. No implementa Prediction Registry (RFC-006 / Model·Prediction) ni AIGovernanceProxy (F1).

---

## 1. Objetivos

| Objetivo | Significado |
|----------|-------------|
| **Single source of definition** | Feature Registry = verdad de defs; no listas sueltas `features.json` |
| **Zero train/serving skew** | Misma `ART-FEATURE-DEF` + compute para BT/train y radar/online |
| **Point-in-time (no leakage)** | Consultas históricas `as_of` / ASOF; nunca usar futuro |
| **Desacoplamiento** | STRATEGY / RUNTIME no conocen Redis/Parquet/PG |
| **Convivencia** | `IndicatorSpec` / chart indicators siguen válidos (RFC-000 §7); se proyectan a Feature |

---

## 2. Jerarquía de artefactos

```
ART-FEATURE-DEF   (definición versionada)
        ↓ compose
ART-FEATURE-SET   (receta + hash de composición)
        ↓ materialize (CAP-FEAT-COMPUTE + STORE)
ART-FEATURE-SNAP  (valores point-in-time / latest)
```

IDs alineados a [RFC-001](./001-artifact-catalog.md): `ART-FEATURE-DEF`, `ART-FEATURE-SET`, `ART-FEATURE-SNAP`.

Custodia: [RFC-002](./002-capability-model.md) — catalog → `CAP-FEAT-CATALOG`; compute → `CAP-FEAT-COMPUTE`; snap persist → `CAP-FEAT-STORE`.

---

## 3. Envelope + payload por tipo

Todos llevan el **Base Artifact Envelope** (RFC-001 §4). Campos específicos en `payload` (o documento YAML equivalente).

### 3.1 `ART-FEATURE-DEF`

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `feature_key` | string | ID estable (`rsi_14_close`) |
| `entity` | string | default `instrument` |
| `output_dtype` | string | `float64`, `float32`, `bool`, … |
| `compute_key` | string | clave del motor registrado (no string SQL arbitrario en hot path) |
| `engine` | enum | ver §6 |
| `params` | object | parámetros tipados (period, source, …) |
| `inputs` | string[] | deps lógicas (`ohlcv.close`, otras feature_keys) |
| `parity_ref` | string \| null | `definitionId` de `IndicatorSpec` / catálogo chart si aplica |
| `valid_range` | [min, max] \| null | sanity |
| `leakage_risk` | low\|medium\|high | documentación |
| `update_frequency` | string | p.ej. `1d`, `1h` (alineado timeframe kernel) |
| `serving.online_ttl_seconds` | int \| null | TTL online adapter |
| `normalization` | string \| null | hint research (`none`, `z_score`, …) — **no** muta compute canónico |

Ejemplo (ilustrativo):

```yaml
id: feat_rsi_14_close
type: ART-FEATURE-DEF
version: "1.0.0"
status: Production
domain: FEATURE
capability: CAP-FEAT-CATALOG
name: RSI 14 close
payload:
  feature_key: rsi_14_close
  entity: instrument
  output_dtype: float64
  compute_key: rsi
  engine: bolsa_analytics
  params: { period: 14, source: close }
  inputs: [ohlcv.close]
  parity_ref: rsi
  valid_range: [0, 100]
  leakage_risk: low
  update_frequency: 1d
  serving: { online_ttl_seconds: 86400 }
```

### 3.2 `ART-FEATURE-SET`

| Campo | Descripción |
|-------|-------------|
| `members` | lista `{ feature_id, version }` o `feature_key@version` |
| `composition_hash` | hash canónico de members ordenados (equiv. a hash de `IndicatorSpec[]` actual) |
| `compatibility` | timeframe(s) / markets soportados |

El `composition_hash` es la clave de partición preferida para snapshots y cache (evoluciona el hash P8 actual).

### 3.3 `ART-FEATURE-SNAP`

| Campo | Descripción |
|-------|-------------|
| `instrument_id` | entidad |
| `as_of` / `timestamp` | instante point-in-time |
| `feature_set_id` + `composition_hash` | set usado |
| `values` | map `feature_key → number\|bool\|null` |
| `bar_index` \| `data_version` | opcional, para paridad BT |

Lifecycle de snaps: efímeros online (TTL); offline archivables. No requieren SemVer de producto; sí checksum.

---

## 4. Online vs Offline store

| Store | Latencia | Uso | Adapter típico |
|-------|----------|-----|----------------|
| **Online** | baja (ms) | Radar, latest para ranking | Redis / Memory / PG cache |
| **Offline** | batch | Train, BT, walk-forward PIT | Parquet / DuckDB / PG histórico |

Ambos implementan el mismo puerto de **lectura** (`IFeaturePort`). Escritura = `CAP-FEAT-STORE` (puede ser método de adapter o puerto `IFeatureWritePort` interno al Data Platform — no expuesto a STRATEGY).

**Prohibido:** STRATEGY/RUNTIME eligen Redis vs Parquet; solo piden snapshot/historical al puerto.

---

## 5. Contratos: `IFeaturePort` y `IFeatureAdapter`

### 5.1 Puerto de dominio (consumidores)

Ubicación target: `bolsa_domain` ports **o** módulo `bolsa_analytics.features.ports` hasta extracción (RFC-004 evolución gradual).

```python
from datetime import datetime
from typing import Any, Protocol

class FeatureSnapshotDTO(Protocol):
    instrument_id: str
    timestamp: datetime
    feature_set_id: str
    composition_hash: str
    values: dict[str, Any]

class IFeaturePort(Protocol):
    def get_latest(
        self,
        instrument_id: str,
        feature_set_id: str,
    ) -> FeatureSnapshotDTO | None: ...

    def get_as_of(
        self,
        instrument_id: str,
        feature_set_id: str,
        as_of: datetime,
        *,
        tolerance_seconds: int = 0,
    ) -> FeatureSnapshotDTO | None: ...

    def get_as_of_many(
        self,
        instrument_ids: list[str],
        feature_set_id: str,
        timestamps: list[datetime],
        *,
        tolerance_seconds: int = 0,
    ) -> list[FeatureSnapshotDTO]: ...
```

- **Online path:** `get_latest` (y `get_as_of` con tolerancia 0 si hay clave exacta).
- **Offline / BT path:** `get_as_of` / `get_as_of_many` con semántica PIT (§7).

### 5.2 Adapter (infra)

```python
class IFeatureAdapter(Protocol):
    """Implementación de almacenamiento; satisface IFeaturePort (+ write interno)."""

    def get_latest(...) -> FeatureSnapshotDTO | None: ...
    def get_as_of(...) -> FeatureSnapshotDTO | None: ...
    def put_snapshot(self, snap: FeatureSnapshotDTO) -> None: ...  # solo Data Platform
```

| Adapter | Rol |
|---------|-----|
| `MemoryFeatureAdapter` | tests / process-local (hoy `InMemoryFeatureCache`) |
| `RedisFeatureAdapter` | online (hoy cache Redis infra) |
| `PostgresFeatureAdapter` | online/offline ligero |
| `ParquetFeatureAdapter` | offline lake |
| `DuckDbFeatureAdapter` | PIT joins offline |

Facade opcional: `CompositeFeaturePort` (online first, offline fallback) **dentro** de FEATURE, no en STRATEGY.

---

## 6. Compute engine (`CAP-FEAT-COMPUTE`)

| `engine` | Uso en Bolsa V1 |
|----------|-----------------|
| `bolsa_analytics` | **Default** — compute existente (paridad chart/BT) |
| `pandas` / `polars` | batch research / exports |
| `numpy` | vectorizado ligero |
| `custom` | función registrada por `compute_key` |

**No** se exige TA-Lib ni VectorBT en el hot path. VectorBT/Optuna siguen en RESEARCH (`CAP-QUANT-*`), no como motor de features de serving.

Registro:

```text
compute_key → Callable[[OHLCV bars, params], series|scalar]
```

Pipeline canónico:

```
MarketUpdated / job feature_build
  → load OHLCV (DATA)
  → resolve FeatureSet members
  → for each DEF: compute_key(engine)
  → put_snapshot (online + offline según config)
  → FeaturesReady (RFC-003)
```

**Prohibido:** matrices pesadas multi-universo en request HTTP síncrono (RFC-004); usar worker/job.

Latencia objetivo online P99: **≤ 5 ms** por lectura de snapshot ya materializado (no incluye compute completo).

---

## 7. Point-in-time / anti-leakage

Regla: valor en `T` solo con datos con `computed_at ≤ T` (y barras `≤ T`).

Offline (DuckDB/Polars) debe usar **ASOF join**:

```sql
SELECT e.event_timestamp, e.instrument_id, f.values
FROM observation_events e
ASOF LEFT JOIN feature_snapshots f
  ON e.instrument_id = f.instrument_id
 AND f.as_of <= e.event_timestamp;
```

Golden tests de BT deben fallar si un compute usa barra futura.

---

## 8. Lineage mínimo (hacia RFC-006)

Cadena documentada por refs en envelope/manifest:

```
ART-DATASOURCE / ART-OHLCV (+ dataVersion)
  → ART-FEATURE-DEF
  → ART-FEATURE-SET (composition_hash)
  → ART-FEATURE-SNAP
  → ART-PREDICTION | ART-SIGNAL (consumidores)
```

Cada `RunManifest` / `ScanManifest` debe poder citar `composition_hash` + `dataVersion` (ya parcialmente en kernel).

---

## 9. Registry API (lógica)

Operaciones del catálogo (`CAP-FEAT-CATALOG`):

| Operación | Descripción |
|-----------|-------------|
| `register_definition` | alta/versión DEF |
| `get_definition` | por id@version |
| `register_feature_set` | alta SET + composition_hash |
| `list_production` | defs/sets `Production` |
| `register_compute` | bind `compute_key` → callable |
| `resolve_parity` | IndicatorSpec → FeatureDef (si `parity_ref`) |

Persistencia del catálogo: YAML/JSON en repo (bootstrap) y/o tabla PG — decisión de implementación vía ADR menor; el **contrato** es este RFC.

---

## 10. Integración con Prediction / Strategy

| Consumidor | Cómo usa features |
|------------|-------------------|
| `CAP-QUANT-INFER` | FeatureSet del Model → `IFeaturePort` → Prediction |
| `CAP-STRAT-EVAL` | FeatureSnap o series alineadas a rules (hoy via compute in-process) |
| `CAP-STRAT-TRACK` | latest snaps + optional predictions |
| `CAP-QUANT-TRAIN` | offline PIT matrix desde FeatureSet + Dataset |

Prediction Registry **no** se define aquí; solo exige que un Model declare `feature_set_id` + `composition_hash` (RFC-001 payload MODEL).

---

## 11. Migración desde código actual

| Hoy | Target RFC-005 |
|-----|----------------|
| `IndicatorSpec` (`@bolsa/shared`) | Proyección ↔ `ART-FEATURE-DEF` vía `parity_ref` / `definitionId`+params |
| Hash `IndicatorSpec[]` (P8) | `ART-FEATURE-SET.composition_hash` |
| `FeatureCache` Protocol + in-memory/Redis | `IFeaturePort` + `Memory*` / `RedisFeatureAdapter` |
| `get_or_build_preset_features` | `CAP-FEAT-COMPUTE` + store |
| Chart `IndicatorSpec` UI | **Permanece**; no renombrar frontend de golpe (RFC-000) |

### Fases de migración

1. **Documentar** registry (este RFC) + tipos/envelope en shared (opcional stub).
2. **Envolver** `FeatureCache` como `OnlineFeatureAdapter` que implementa `IFeaturePort`.
3. **Catálogo** bootstrap: mapear indicadores del catálogo → DEF Production.
4. **Consumidores nuevos** (infer LightGBM, etc.) solo vía puerto.
5. Deprecar acceso directo al cache fuera de FEATURE (lint RFC-004).

---

## 12. Golden tests (obligatorio al implementar)

Suite mínima:

| Test | Verifica |
|------|----------|
| Paridad IndicatorSpec ↔ FeatureDef | mismos valores en N barras fixture |
| PIT | `as_of` no ve barra futura |
| Composition hash estable | mismo set → mismo hash |
| Online/offline parity | latest online == última fila offline para T |
| Train/serving | misma DEF en BT slice y “online” simulado |

Al menos **10 features base** (SMA, EMA, RSI, MACD hist, BB position, ATR, …) cuando se implemente el registry ejecutable.

---

## 13. Reglas de import (refuerzo)

- `CAP-FEAT-*` **no** importa execution/OMS ni `llm_*`.
- STRATEGY/RUNTIME importan solo `IFeaturePort` (Protocol), no adapters.
- Compute puede vivir en `bolsa_analytics`; adapters Redis en `bolsa_infrastructure`.

---

## 14. Criterios de aceptación

- [x] RFC en `docs/rfc/005-feature-registry.md`
- [x] Schemas DEF / SET / SNAP
- [x] `IFeaturePort` / `IFeatureAdapter` + dual store
- [x] Compute engines + pipeline + PIT
- [x] Lineage mínimo + migración FeatureCache/IndicatorSpec
- [x] Golden test plan
- [x] (Implementación) Protocol Python + modelos (`bolsa_analytics.features`)
- [x] (Implementación) `OnlineFeatureAdapter` + catálogo bootstrap (≥10 DEFs)
- [x] (Implementación) golden parity FeatureDef ↔ compute_spec + HTTP catalog/latest
- [x] (Opcional) tipos shared TS (`@bolsa/shared` feature-registry)
- [ ] (Opcional) offline adapters Redis tipado / Parquet

---

## 15. Próximo paso

Pirámide constitucional (sin redefinir arquitectura):

1. **RFC-006 — Data Contracts & Lineage** (contratos OHLCV→…→Trade + eventos tipados; Prediction/Model schemas como contratos de datos).
2. **RFC-007 — AI Governance** (Proxy, Prompt Registry).
3. **F1 (paralelo suave):** AIGovernanceProxy + Ollama — autorizado; no bloquea a 005/006.

Registries Policy/Prompt/Model detallados pueden ser secciones de 006/007 o ADRs de implementación **sin** mover la pirámide bloqueada.

---

## 16. Enmiendas

Cambios a `IFeaturePort`, nuevos `engine` canónicos o semántica PIT requieren PR a este RFC.

---

*Síntesis A1 (alcance completo registry) + A2 (PIT, dual-store, IFeaturePort) + A3 (migración, pipeline); ART-* alineados a RFC-001; anclado a FeatureCache/IndicatorSpec reales.*
