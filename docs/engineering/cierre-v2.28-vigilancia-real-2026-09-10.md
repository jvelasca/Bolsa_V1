# Cierre V2.28 / A10 — Vigilancia Real desde Ejecución SIM (P1-02 real)

**Fecha:** 2026-09-10
**Alcance:** AUTO **estrictamente SIMULATED**. **LIVE real intacto.**
**Motivo:** cerrar el P1-02 de la auditoría de V2.26 — la vigilancia de la estrategia
ACTIVE se invocaba con `metrics={}` y no podía degradar con evidencia real.

> Continúa a `cierre-v2.27-a10-real-wiring-2026-09-10.md`.
> V2.27 cerró el **cableado** (universo ESTUDIO + LAB reales). V2.28 cierra la **señal**:
> la vigilancia ahora se alimenta de la ejecución SIM atribuida a cada versión.

---

## 1. El bloqueo estructural que había que resolver primero

La vigilancia pedía métricas, pero **no existía forma de atribuir un fill SIM a una
versión de estrategia**. El `version_id` vivía solo como string en memoria
(`DecisionPackage.source = "active-strategy:<version_id>"`) y el worker SIM lo
**descartaba**: solo leía `action` y `quantity`.

Ninguna tabla de fills/ejecuciones/posiciones tenía columna de estrategia:

| Superficie         | Tabla                                       | ¿`version_id`?    | ¿Fills/PnL?          |
| ------------------ | ------------------------------------------- | ----------------- | -------------------- |
| Intención (RAM)    | `DecisionPackage.source`                    | Sí                | No                   |
| Identidad de orden | `auto_venue_order_id`                       | No                | No                   |
| Contexto de fill   | `sim_fill_finance_context`                  | **No → ahora Sí** | Sí                   |
| Traza de ejecución | `execution_events`                          | No                | Sí                   |
| Posición abierta   | `sim_auto_positions`                        | No                | Solo abierta         |
| Dinero             | `positions`/`transactions`/`ledger_entries` | No                | Fees, sin atribución |

Sin atribución, cualquier métrica sería de la **cuenta**, no de la **estrategia**.
Además, `sim_auto_positions` **borra** las posiciones al cerrarse: no había histórico
de trades cerrados del que derivar PnL.

Y no existía ningún código que computara drawdown/Sharpe/win rate/profit factor desde
fills SIM: `compute_is_metrics` (analytics) opera sobre series de barras de backtest.

## 2. Decisión de diseño (acordada)

1. **Prerrequisito primero**: persistir la identidad de la estrategia por fill.
2. **Cambio mínimo y aditivo** en el motor SIM: columna nullable + propagación, **sin**
   alterar la identidad de ejecución (`venue_order_id`/`execution_id`), ni la PK, ni la
   semántica de settlement.
3. **Métricas observadas separadas de las predictivas**: `edge`/`wfe`/`dsr`/`credibility`
   (del LAB) y el bloque observado (`return`/`drawdown`/`win rate`/`profit factor`) tienen
   semántica distinta. No se fuerzan a un mapeo único.
4. **Guarda de muestra mínima**: el bloque observado **no degrada** por debajo de N
   round-trips cerrados (evita degradar por ruido de uno o dos trades).

## 3. Cambios

### 3.1 Migración y persistencia de la atribución

- `packages/py/infrastructure/alembic/versions/031_sim_fill_strategy_attr.py` (nueva):
  añade `strategy_version_id` **nullable** a `sim_fill_finance_context` + índice
  `(strategy_version_id, created_at)` para reconstruir la serie temporal de una versión.
  Sin backfill: `NULL` = sin atribución (spine determinista / filas previas). Guards
  idempotentes (`_table_exists`/`_column_exists`/`_index_exists`).
- `tables.py`: columna + índice en `SimFillFinanceContextRow`.
- `sim_durable_store.py`: campo en el dataclass `SimFillFinanceContext`, en el `save`
  PG, en el `get`, y **nuevo** `list_for_strategy_version(version_id, account_id, limit)`
  en el Protocol, el doble hermético y el store PG (ordenado por `created_at`).

### 3.2 Propagación por la cadena de settlement

`submit_simulated_order(..., strategy_version_id=)` →
`apply_simulated_order_once(..., strategy_version_id=)` → `persist_fill_finance_context`
→ fila durable. El resolver durable (`build_durable_finance_resolver`) y
`SimulatedFillFinance` también lo conservan: un apply tras crash **no pierde la
procedencia**.

### 3.3 Atribución en el worker SIM

- `_strategy_version_from_source(source)`: extrae `<version_id>` de
  `"active-strategy:<version_id>"`. Devuelve `None` para cualquier otro origen
  (`protection:*`, vacío): **no se inventa** una versión.
- `auto_turn` pasa la versión efectiva a `_settle`. Regla de herencia:
  **la apertura aporta la versión; el cierre (venta de protección) la hereda** de
  `_position_version[symbol]`. Sin esto, la serie de la versión tendría compras sin
  ventas y el PnL observado no cuadraría.
- `_position_version` se fija al abrir desde plano y se limpia al cerrar. Tras un crash,
  la proyección durable **no** guarda la versión: los cierres readoptados quedan sin
  atribución (`NULL`) en vez de inventarla — límite documentado.

### 3.4 Métricas observadas (cálculo puro)

- `packages/py/application/src/bolsa_application/strategy_observed_metrics.py` (nuevo):
  contabilidad FIFO de round-trips sobre `(side, qty, price)` → `trades`,
  `realized_pnl`, `return_pct`, `max_drawdown_pct`, `win_rate`, `profit_factor`.
  - Ventas por encima de lo abierto se ignoran (no se fabrican cortos).
  - Drawdown normalizado contra el **capital comprometido total** (la curva parte de 0;
    usar el pico como denominador perdería la primera pérdida).
  - `as_metrics()` devuelve `{}` si no se alcanza la muestra mínima.

### 3.5 Vigilancia observada (dominio + aplicación)

- `StrategyHealth` (dominio) gana el bloque observado (`observed_return_pct`,
  `observed_max_drawdown_pct`, `observed_win_rate`, `observed_profit_factor`,
  `observed_trades`) y `observed_degraded`.
  - Semántica de umbral: retorno/win-rate/profit-factor son **mínimos**; el drawdown es
    un **techo** (degrada por encima).
  - **Guarda de muestra**: sin `observed_trades >= min_observed_trades`, el observado no
    decide.
- `HealthThresholds` gana los umbrales observados (`min_observed_trades`,
  `min_observed_return_pct`, `max_observed_drawdown_pct`, `min_observed_win_rate`,
  `min_observed_profit_factor`). Los `None` **se omiten** al serializar: un umbral no
  configurado no debe viajar como 0.
- `evaluate_active_health` puebla el bloque observado y añade los motivos concretos a
  `breaches` (auditable).
- `AutoOrchestrator`: nuevo puerto `observed_metrics` (opcional). `watch_active` calcula
  las métricas observadas de la versión activa y las fusiona con las del llamante (estas
  tienen prioridad). Un fallo del provider **no degrada ni aprueba**: se sigue con lo
  disponible (fail-closed).
- `strategy_observed_metrics_provider.py` (nuevo): `make_observed_metrics_provider`
  (sesión propia por invocación; `min_trades` por env
  `AUTO_ORCHESTRATOR_OBSERVED_MIN_TRADES`, default 10).
- `_default_orchestrator` cablea el provider.
- `auto_orchestrator_loop` ya **no** pasa `metrics={}`.
- `strategy_lifecycle_store.save_health/list_health`: el bloque observado se persiste en
  el JSON libre `thresholds` bajo el prefijo `value_` (sin migrar la tabla), filtrando
  valores no finitos.

## 4. Variables de entorno nuevas

| Variable                                | Default | Efecto                                                            |
| --------------------------------------- | ------- | ----------------------------------------------------------------- |
| `AUTO_ORCHESTRATOR_OBSERVED_MIN_TRADES` | 10      | Muestra mínima de round-trips para que el observado sea decisorio |

## 5. Dos bugs reales cazados por la verificación PG

1. **`revision` de Alembic > 32 caracteres.** `alembic_version.version_num` es
   `varchar(32)`; `031_sim_fill_strategy_attribution` (34) desbordaba y **dejaba la BD a
   medio migrar**, rompiendo en cascada tests no relacionados. Fix: `031_sim_fill_strategy_attr`.
2. **`profit_factor = inf` no es JSON-serializable.** Una racha sin pérdidas producía
   `float("inf")`, y el `INSERT` del snapshot de salud fallaba (`Token "Infinity" is
invalid`). Fix: sin pérdidas el profit factor es indefinido ⇒ `None`; y
   `_health_payload` filtra no finitos como defensa redundante.

Ambos son fallos que **solo** aparecen ejecutando contra PG real: los tests herméticos no
los detectan.

## 6. Verificación

- **Ruff** sobre los ficheros tocados → `All checks passed!`
- **Mypy** sobre los 10 módulos de aplicación/dominio tocados → `Success: no issues found`.
- **Suite consolidada** (application + domain + worker SIM + worker orquestador + seam +
  crash battery + PG) → **1328 passed**.
- **PG real** `test_strategy_lifecycle_pg.py` → **4 passed**, incluido el nuevo
  `test_observed_vigilance_end_to_end_pg`:
  promociona una activa real (versión + promoción), inserta 3 round-trips SIM con
  `strategy_version_id`, compone el orquestador **real** y certifica que el snapshot de
  salud persiste con `observed_trades == 3` y `observed_return_pct > 0`.

## 7. Fuera de alcance (P2 que siguen para V2.29)

- **COACH comparativo**: sigue evaluando solo `selection.top.candidate_ids[0]`.
- **StrategyDiscoveryEngine**: no existe selector sobre los 30+ indicadores.
- **SignalEvaluator real**: `active_strategy_decider` sigue delegando en `fallback(symbol)`.
- **Shadow automático**: `AUTO_ORCHESTRATOR_SHADOW_VALIDATED=1` certifica sin ejecutar.
- **Atribución tras crash**: los cierres de posiciones readoptadas quedan sin versión
  (la proyección durable no la guarda).

> **Actualización V2.29:** el **COACH comparativo** y el **SignalEvaluator real** se
> cerraron en `cierre-v2.29-coach-comparativo-signal-real-2026-09-10.md`, junto con el
> hueco de CI que dejaba estos tests fuera del tag. El **StrategyDiscoveryEngine**, el
> **shadow automático** y la **atribución tras crash** siguen diferidos a V2.30.

## 8. Barreras (sin cambios)

- AUTO → SIMULATED únicamente. LIVE real intacto.
- Sin LLM en el hot path.
- El motor SIM no cambia su identidad de ejecución ni la semántica de settlement: el
  cambio es una columna nullable y su propagación.
- Fail-closed en toda la cadena: sin atribución no hay métrica; sin muestra no hay
  degradación; sin evidencia no se promociona.
