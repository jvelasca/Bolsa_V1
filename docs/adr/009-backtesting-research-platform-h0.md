# ADR 009: Hub de backtesting y plataforma de research (H0)

## Estado

**Aceptado** — jul 2026 (BT-0 + BT-1 implementados)

## Contexto

Bolsa V1 necesita backtesting como **base de la app** (ver [BACKTESTING_AUDIT.md](../BACKTESTING_AUDIT.md)). En paralelo, ADR-003 define evolución hacia IA/ML con orden obligatorio: backtest fiable antes de LLM.

Este ADR acota la **fase H0** (implementación inmediata) y fija **contratos de datos** que no deben rehacerse cuando llegue procesamiento masivo e IA ([BACKTESTING_DATA_ARCHITECTURE.md](../BACKTESTING_DATA_ARCHITECTURE.md)).

## Decisiones

### 1. Navegación

- Añadir **Backtesting ▼** en `MAIN_NAV` después de Alertas.
- Eliminar botón **Indicadores** de top bar `/trading` y entrada duplicada en ⋯.
- Mantener catálogo indicadores en **barra global del workspace** (`ChartIndicatorsBar`).

### 2. Contratos shared (crear en H0, usar progresivamente)

| Tipo | Paquete | Uso H0 |
|------|---------|--------|
| `StrategyDefinitionV1` | `@bolsa/shared` | Presets + futuro builder |
| `DataSnapshotRef` | `@bolsa/shared` | Hash en cada run |
| `RunManifest` | `@bolsa/shared` | JSONB en `backtest_runs` |
| `ResearchJobSpec` | `@bolsa/shared` | Shape stub (sync) |
| `IndicatorSpec` | formalizar desde runtime | Bridge chart ↔ backtest |

Réplica Pydantic en `bolsa_domain` / `bolsa_api/schemas`.

### 3. Motor de simulación H0

- Evolucionar **event-driven** existente (`bolsa_analytics/backtest.py`).
- Añadir: timeframe, rango fechas, comisiones, slippage, `RunManifest`.
- **No** VectorBT en H0 — preparar interfaz `BacktestEngine` para swap H1.

### 4. Indicadores — dirección paridad

- **Canónico:** Python `bolsa_analytics/indicators/compute.py` (nuevo, multi-spec).
- Chart TS: transitorio local + golden tests; migrar a `POST /indicators/compute` en BT-3.
- Prohibido añadir indicadores solo en TS para uso en backtest.

### 5. Persistencia H0

Ampliar `backtest_runs`:

- `manifest JSONB`
- `timeframe`, `data_snapshot_id` (nullable H0)
- `strategy_definition_id` (nullable hasta BT-2)
- `commission_bps`, `slippage_bps`

Tablas `strategy_definitions`, `data_snapshots`, `research_jobs`: **H1** (tipos shared ya definidos).

### 6. IA — explícitamente fuera de H0

- Sin LLM, sin ML train, sin MCP en esta fase.
- UI hub incluye secciones **deshabilitadas** («Optimización», «Asistente IA») para coherencia visual.
- `StrategyDefinitionV1.origin` y `sourcePrompt` reservados para H2.

### 7. Orden de implementación

| ID | Entregable |
|----|------------|
| BT-0 | Nav + dropdown hub + limpieza Indicadores top bar |
| BT-1 | Motor extensible + manifest + snapshot hash |
| BT-2 | CRUD `StrategyDefinitionV1` + UI presets |
| BT-3 | IndicatorSpec compute + golden parity tests |
| BT-4 | Equity curve en chart + export trades |

## Consecuencias

### Positivas

- BT-0…BT-4 alimentan directamente RD-* (VectorBT) y AI-* sin rework de schema.
- Un manifest por run habilita auditoría y agentes MCP futuros.
- Separación event/vectorized evita cuellos de botella.

### Negativas

- Más schema upfront antes de features visibles.
- Paridad indicadores requiere esfuerzo de tests golden.

## Criterios de aceptación H0

- [x] Backtesting visible en nav principal con dropdown funcional.
- [x] Indicadores top bar eliminado; catálogo workspace intacto.
- [x] Cada `backtest_run` incluye `manifest` con engine version + data hash.
- [x] Tipos `StrategyDefinitionV1`, `RunManifest` en shared exportados.
- [x] Documentación BACKTESTING_* actualizada.

## Referencias

- [BACKTESTING_AUDIT.md](../BACKTESTING_AUDIT.md)
- [BACKTESTING_DATA_ARCHITECTURE.md](../BACKTESTING_DATA_ARCHITECTURE.md)
- [ADR-003](./003-python-backend-ai-platform.md)
- **Evolución post-H0:** [ADR-011 Quantitative Research Operating System](./011-quantitative-research-platform.md) (hipótesis, Belief, landscape, Knowledge temprano).
