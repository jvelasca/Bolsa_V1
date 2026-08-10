# ADR 010: Platform Kernel — Radar, ejecución y escalado EU+US

## Estado

**Aceptado** — jul 2026 (contratos shared; persistencia e implementación en fases P1–P6)

## Contexto

Bolsa V1 evoluciona hacia una plataforma tipo ProRealTime / Composer:

- **Research** valida ideas (backtest, optimize).
- **Radar** (rastreadores) detecta oportunidades en mercado real.
- **Ejecución** manual, asistida o automática (paper → live).
- **Cartera** con políticas por posición.

H0 (SC-0…SC-6, BT-0…BT-7) implementó la **tubería de señales** y jobs async parciales, pero faltan entidades de producto (`Tracker`, `ExecutionPolicy`), manifest de scan, bus de eventos y límites de escala para **multi-mercado EU+US**.

Este ADR fija el **backend primero** — frontend compacto/flotante viene después (ADR-004).

### Decisiones de producto confirmadas (jul 2026)

| Tema | Decisión |
|------|----------|
| Mercados 12m | **EU + US pronto** — cientos/miles de símbolos por scan vía listas |
| Timeframes kernel | **`1d` y `1wk` únicamente** por ahora (sin intraday en radar/auto) |
| Separación UI | Backtesting ≠ Rastreadores (nav); mesa de trabajo = `/trading` (futuro paneles) |

### Asumido confirmado (jul 2026 — defaults producto)

| Tema | Decisión |
|------|----------|
| Ejecución live | Paper sólido primero; live vía **webhook** (SC-6) antes que broker nativo |
| Multi-usuario | `userId` nullable; scopes preparados (ADR-008) |
| Estrategias 6–12m | Reglas sobre indicadores; ML como jobs separados (ADR-003) |

## Principio rector

**Un motor de señales, cuatro planos, un kernel.**

```
                    ┌─────────────────────┐
                    │   Workspace (UI)    │  ← fase posterior
                    └──────────┬──────────┘
                               │
     ┌─────────────────────────┼─────────────────────────┐
     ▼                         ▼                         ▼
 Research Plane          Radar Plane            Execution Plane
 (backtest/optimize)     (trackers/scans)       (policies/orders)
     │                         │                         │
     └─────────────────────────┼─────────────────────────┘
                               ▼
              ┌────────────────────────────────┐
              │        PLATFORM KERNEL         │
              │ StrategyDefinitionV1           │
              │ SignalEngine.evaluate_*        │
              │ TrackerDefinitionV1            │
              │ ExecutionPolicyV1              │
              │ PositionPolicyV1               │
              │ PlatformJobSpecV1              │
              │ ScanManifestV1 / RunManifest   │
              │ PlatformEventV1 (bus)          │
              └────────────────────────────────┘
                               │
                               ▼
              Patrimony Plane (accounts, ledger, positions)
```

## Contratos shared (P0 — hecho)

Archivo: `packages/shared/src/platform-kernel.ts`

| Tipo | Rol |
|------|-----|
| `KERNEL_TIMEFRAMES` | `'1d' \| '1wk'` — validación API |
| `TrackerDefinitionV1` | Rastreador persistido (estrategia + universo + TF) |
| `ExecutionPolicyV1` | inform / alert / paper_auto / live_auto |
| `PositionPolicyV1` | Política sobre posición en cartera |
| `ScanManifestV1` | Artifact reproducible por scan |
| `PlatformJobSpecV1` | Unificación jobs (scan, backtest, optimize…) |
| `PlatformEventV1` | Bus interno (diseño; impl H2) |
| `KERNEL_SCALE_LIMITS` | Límites EU+US |

Réplica Pydantic en `bolsa_domain` / `bolsa_api/schemas` al implementar cada fase.

## Capas Python (packages/py)

```
bolsa_domain/          # entidades + ports (sin SQLAlchemy)
bolsa_application/     # use cases (EnqueueScan, ProcessTracker, RouteSignal…)
bolsa_analytics/       # SignalEngine, backtest, indicators (puro)
bolsa_infrastructure/  # repos, queue, cache, event publishers
bolsa_features/        # (H2) feature matrix, point-in-time
bolsa_research/        # (H2) walk-forward, PBO, validation
```

**Regla:** `bolsa_analytics` no conoce BD ni HTTP. Use cases orquestan.

## Persistencia (roadmap tablas)

| Tabla | Fase | Notas |
|-------|------|-------|
| `strategy_definitions` | ✅ | Ampliar versionado explícito |
| `scan_jobs` | ✅ | FK `tracker_definition_id` opcional (P3) |
| `optimization_runs` | ✅ | Tipo job `optimize` |
| `tracker_definitions` | ✅ P3 jul 2026 | JSON spec `TrackerDefinitionV1` |
| `scan_manifests` | ✅ P4 jul 2026 | Manifest + FK scan_job / scan run |
| `execution_policies` | ✅ P5 jul 2026 | JSON `ExecutionPolicyV1` |
| `position_policies` | ✅ P6 jul 2026 | Por account + instrument |
| `platform_events` | ✅ jul 2026 | Append-only audit / bus (PG + handlers) |
| `data_snapshots` | ✅ P4 jul 2026 | Snapshot lógico OHLCV (hash) |
| `platform_jobs` | **H2** | Vista unificada o reemplazo scan_jobs |

Todas con `user_id TEXT NULL` hasta auth multi-usuario.

## Escalado EU+US (corto plazo)

### Scan masivo

1. **Universo por listas** — listas de 500–5000 IDs; no un solo request monolítico sin chunking.
2. **Particionado** — job padre → chunks de `KERNEL_SCALE_LIMITS.maxInstrumentsPerScanChunk` (250).
3. **Cola** — Redis + Arq (RD-2 ✅); worker horizontal.
4. **Cache features** — `PresetFeatureCache` → generalizar a `FeatureCache` por `IndicatorSpec` hash (Redis H1).
5. **OHLCV** — sync queue prioriza listas activas en trackers; ADR-007 daily/weekly.

### Timeframes `1d` / `1wk`

- API valida `timeframe in KERNEL_TIMEFRAMES` en trackers y scans programados.
- Intraday (`1h`, `1m`…) permanece en chart cache; **no** en radar hasta ADR dedicado.
- Motor `evaluate_strategy_last_bar` recibe TF; datos desde `ohlcv_bars` con índice `(instrument_id, timeframe, timestamp)`.

### Límites actuales a elevar

| Límite hoy | Objetivo P2 |
|------------|-------------|
| ~500 instrumentos / scan request | 5000 vía chunk jobs |
| Presets hardcoded | `Rule` tipadas en StrategyDefinition |
| scan_jobs sin tracker_id | FK opcional + manifest |

## Event bus (diseño P5)

```
SignalEngine → PlatformEvent signal.emitted
                    ├─► AlertDispatcher (existente)
                    ├─► ToastMonitor (existente)
                    ├─► ExecutionRouter (nuevo → orders)
                    └─► ScanManifestWriter
```

Implementación incremental: handlers en `bolsa_application/events/` sin microservicios.

## Execution loop (P5 — paper)

1. Tracker schedule o manual → scan job.
2. Hit → `SignalEvent` + optional `ExecutionPolicy`.
3. `ExecutionRouter` valida guardrails (`requireValidatedBacktest`, account paper).
4. `PlaceOrder` use case → ledger (ADR-008).

Live: mismo router; adapter `webhook` (SC-6) o broker (H3+).

## Fases backend (sin UI bonita)

| Fase | Entregable | Depende de |
|------|------------|------------|
| **P0** | ADR-010 + `platform-kernel.ts` | — |
| **P1** | Validación TF kernel en API scans; límites sync/async | P0 ✅ jul 2026 |
| **P2** | Scan chunking (parent/child jobs) | P1 ✅ jul 2026 |
| **P3** | `tracker_definitions` CRUD + link scan_jobs | P2 ✅ jul 2026 |
| **P4** | `scan_manifests` + `data_snapshots` hash | P3 ✅ jul 2026 |
| **P5** | `execution_policies` + ExecutionRouter paper | P4 ✅ jul 2026 |
| **P6** | `position_policies` | P5 ✅ jul 2026 |
| **P7** | Rules engine v1 (salir presets Python) | P6 ✅ jul 2026 |
| **P8** | Feature cache Redis generalizado | P2 ✅ jul 2026 |
| **P9** | Tracker schedule worker (bar close 1d/1wk) | P3, P5 ✅ jul 2026 |
| **P10** | `platform_events` bus + audit API | P5 ✅ jul 2026 |

Frontend (panel flotante) **no antes de P3** — gestor de trackers necesita API.

## Relación con ADRs previos

| ADR | Relación |
|-----|----------|
| ADR-003 | Orden IA/ML; kernel no ejecuta LLM |
| ADR-008 | ExecutionRouter escribe ledger |
| ADR-009 | RunManifest; ScanManifest análogo |
| SCREENERS_SIGNALS_ALIGNMENT | Implementado SC-*; este ADR extiende entidades |

## Consecuencias

- Prohibido añadir lógica de scan ad-hoc fuera de use cases + SignalEngine.
- Nuevos timeframes en radar requieren amend ADR + `KERNEL_TIMEFRAMES`.
- UI de rastreadores consume `TrackerDefinitionV1`, no duplica payload scan.
- Crecimiento rápido de prestaciones se absorbe en jobs + cache + manifests, no en endpoints sync sin cola.

## Referencias

- [platform-kernel.ts](../../packages/shared/src/platform-kernel.ts)
- [RESEARCH_RADAR/SCREENERS y señales](./011-quantitative-research-platform.md) *(histórico: `SCREENERS_SIGNALS_ALIGNMENT.md` eliminado; pendiente de borrar definitivamente cuando se confirme libre de uso)*
- [BACKTESTING_DATA_ARCHITECTURE.md](../BACKTESTING_DATA_ARCHITECTURE.md)
